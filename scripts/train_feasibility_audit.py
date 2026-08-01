#!/usr/bin/env python3
"""Train-only signal-density audit with an explicitly non-deployable oracle."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
import statistics
from datetime import datetime
from pathlib import Path

from csv_client import CSVClient
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
import portfolio_backtest
from portfolio_backtest import Config, _candidate_signals, run_portfolio
from pivot_retest_experiment import filter_detections, slice_prices, trade_stats

START, END = "2016-07-01", "2021-12-31"


def exposure_stats(portfolio: dict) -> dict:
    curve = portfolio["equity_curve"]
    exposures = [float(row["gross_exposure_pct"]) for row in curve]
    positions = [int(row["positions"]) for row in curve]
    average = statistics.fmean(exposures) if exposures else 0.0
    trades = int(portfolio["summary"]["trades"])
    position_days = sum(positions)
    return {
        "sessions": len(curve),
        "average_exposure_pct": average,
        "median_exposure_pct": statistics.median(exposures) if exposures else 0.0,
        "invested_sessions_pct": (
            100 * sum(value > 0 for value in exposures) / len(exposures)
            if exposures else 0.0
        ),
        "average_positions": statistics.fmean(positions) if positions else 0.0,
        "maximum_positions": max(positions, default=0),
        "average_position_sessions": position_days / trades if trades else 0.0,
        "approx_exposed_capital_return_needed_for_20pct_cagr_pct": (
            20 / (average / 100) if average > 0 else None
        ),
    }


def standalone_signal_return(
    signal: dict, bars: list[dict], cfg: Config,
) -> float | None:
    """Future-aware standalone return used only to label oracle winners."""
    entry_idx = int(signal["fill_idx"])
    if entry_idx >= len(bars):
        return None
    one_way_cost = (cfg.commission_bps + cfg.slippage_bps) / 10_000
    entry = float(bars[entry_idx]["open"]) * (1 + one_way_cost)
    stop = max(float(signal["pattern_stop"]), entry * (1 - cfg.max_risk_pct / 100))
    last_idx = min(entry_idx + cfg.max_hold_bars, len(bars) - 1)
    raw_exit = None
    for i in range(entry_idx + 1, last_idx + 1):
        bar = bars[i]
        if float(bar["low"]) <= stop:
            raw_exit = min(float(bar["open"]), stop)
            break
        if i - entry_idx >= cfg.max_hold_bars:
            raw_exit = float(bar["open"])
            break
    if raw_exit is None:
        raw_exit = float(bars[-1]["close"])
    exit_price = raw_exit * (1 - one_way_cost)
    return exit_price / entry - 1


def best_open_exit(
    signal: dict, bars: list[dict], cfg: Config,
) -> tuple[int, float] | None:
    """Lookahead-best next-open exit before hard stop/timeout, after costs."""
    entry_idx = int(signal["fill_idx"])
    if entry_idx + 1 >= len(bars):
        return None
    one_way_cost = (cfg.commission_bps + cfg.slippage_bps) / 10_000
    entry = float(bars[entry_idx]["open"]) * (1 + one_way_cost)
    stop = max(float(signal["pattern_stop"]), entry * (1 - cfg.max_risk_pct / 100))
    terminal = min(entry_idx + cfg.max_hold_bars, len(bars) - 1)
    for i in range(entry_idx + 1, terminal + 1):
        if float(bars[i]["low"]) <= stop:
            terminal = i
            break
    best_idx = max(
        range(entry_idx + 1, terminal + 1),
        key=lambda i: float(bars[i]["open"]),
    )
    exit_price = float(bars[best_idx]["open"]) * (1 - one_way_cost)
    return best_idx, exit_price / entry - 1


def best_timed_signal(
    base_signal: dict, bars: list[dict], cfg: Config,
    entry_window: int = 60,
) -> tuple[dict, float] | None:
    """Perfectly choose one next-open entry and later open exit per detection."""
    start = int(base_signal["fill_idx"])
    end = min(start + entry_window, len(bars))
    best = None
    for entry_idx in range(start, end):
        signal_idx = entry_idx - 1
        if signal_idx < 0:
            continue
        if float(bars[signal_idx].get("close") or 0) < float(base_signal["pattern_stop"]):
            break
        candidate = {
            **base_signal,
            "signal_date": bars[signal_idx]["date"],
            "fill_date": bars[entry_idx]["date"],
            "fill_idx": entry_idx,
        }
        planned = best_open_exit(candidate, bars, cfg)
        if planned is None:
            continue
        exit_idx, future_return = planned
        if best is None or future_return > best[1]:
            best = ({**candidate, "diagnostic_exit_idx": exit_idx}, future_return)
    return best


def best_timed_baseline_signal(
    base_signal: dict, bars: list[dict], cfg: Config,
    entry_window: int = 60,
) -> tuple[dict, float] | None:
    """Perfect entry-date choice, retaining the ordinary stop/timeout exit."""
    start = int(base_signal["fill_idx"])
    end = min(start + entry_window, len(bars))
    best = None
    for entry_idx in range(start, end):
        signal_idx = entry_idx - 1
        if signal_idx < 0:
            continue
        if float(bars[signal_idx].get("close") or 0) < float(base_signal["pattern_stop"]):
            break
        candidate = {
            **base_signal,
            "signal_date": bars[signal_idx]["date"],
            "fill_date": bars[entry_idx]["date"],
            "fill_idx": entry_idx,
        }
        future_return = standalone_signal_return(candidate, bars, cfg)
        if future_return is not None and (best is None or future_return > best[1]):
            best = (candidate, future_return)
    return best


def oracle_winner_portfolio(
    detections: dict, prices: dict[str, list[dict]], cfg: Config,
) -> tuple[dict, dict]:
    """Perfectly select positive standalone outcomes, then enforce portfolio rules."""
    signals = _candidate_signals(
        detections, prices, cfg, entry_rule="detection_entry",
    )
    labelled = []
    for signal in signals:
        future_return = standalone_signal_return(
            signal, prices[signal["symbol"]], cfg,
        )
        if future_return is not None and future_return > 0:
            labelled.append(signal)
    original = portfolio_backtest._candidate_signals
    try:
        portfolio_backtest._candidate_signals = lambda *args, **kwargs: labelled
        oracle = run_portfolio({}, prices, cfg)
    finally:
        portfolio_backtest._candidate_signals = original
    metadata = {
        "lookahead": True,
        "deployable": False,
        "purpose": (
            "winner-only ceiling diagnostic for detection-entry plus baseline "
            "exit; not a formal upper bound over other exits"
        ),
        "all_detection_signals": len(signals),
        "future_positive_signals": len(labelled),
    }
    return oracle, metadata


def oracle_entry_exit_portfolio(
    detections: dict, prices: dict[str, list[dict]], cfg: Config,
    max_hold_bars: int = 60,
) -> tuple[dict, dict]:
    """Perfectly skip losers and choose best feasible open before stop/timeout."""
    horizon_cfg = replace(cfg, max_hold_bars=max_hold_bars)
    signals = _candidate_signals(
        detections, prices, horizon_cfg, entry_rule="detection_entry",
    )
    selected = []
    for signal in signals:
        planned = best_open_exit(signal, prices[signal["symbol"]], horizon_cfg)
        if planned is None or planned[1] <= 0:
            continue
        selected.append({**signal, "diagnostic_exit_idx": planned[0]})
    original = portfolio_backtest._candidate_signals
    try:
        portfolio_backtest._candidate_signals = lambda *args, **kwargs: selected
        oracle = run_portfolio(
            {}, prices, horizon_cfg, exit_rule="diagnostic_oracle",
        )
    finally:
        portfolio_backtest._candidate_signals = original
    return oracle, {
        "lookahead": True, "deployable": False,
        "purpose": (
            "joint perfect entry selection and best next-open exit before the "
            f"unchanged hard stop/{max_hold_bars}-session limit; never a strategy score"
        ),
        "all_detection_signals": len(signals),
        "future_profitable_best_exit_signals": len(selected),
        "max_hold_bars": max_hold_bars,
    }


def oracle_timing_portfolio(
    detections: dict, prices: dict[str, list[dict]], cfg: Config,
    max_hold_bars: int, entry_window: int = 60,
) -> tuple[dict, dict]:
    """Perfectly choose one entry/exit pair per detected VCP opportunity."""
    horizon_cfg = replace(cfg, max_hold_bars=max_hold_bars)
    base_signals = _candidate_signals(
        detections, prices, horizon_cfg, entry_rule="detection_entry",
    )
    selected = []
    for base in base_signals:
        choice = best_timed_signal(
            base, prices[base["symbol"]], horizon_cfg,
            entry_window=entry_window,
        )
        if choice is not None and choice[1] > 0:
            selected.append(choice[0])
    selected.sort(
        key=lambda value: (
            value["fill_date"], -value["edge_rank"], value["symbol"],
        ),
    )
    original = portfolio_backtest._candidate_signals
    try:
        portfolio_backtest._candidate_signals = lambda *args, **kwargs: selected
        oracle = run_portfolio(
            {}, prices, horizon_cfg, exit_rule="diagnostic_oracle",
        )
    finally:
        portfolio_backtest._candidate_signals = original
    return oracle, {
        "lookahead": True, "deployable": False,
        "purpose": (
            "perfect one-entry timing and next-open exit per detection, with "
            "pattern-stop pre-entry invalidation and unchanged portfolio rules"
        ),
        "base_detection_signals": len(base_signals),
        "future_profitable_timed_signals": len(selected),
        "entry_window": entry_window, "max_hold_bars": max_hold_bars,
    }


def oracle_baseline_timing_portfolio(
    detections: dict, prices: dict[str, list[dict]], cfg: Config,
    entry_window: int = 60,
) -> tuple[dict, dict]:
    """Perfectly time one entry per detection but retain baseline exits."""
    base_signals = _candidate_signals(
        detections, prices, cfg, entry_rule="detection_entry",
    )
    selected = []
    for base in base_signals:
        choice = best_timed_baseline_signal(
            base, prices[base["symbol"]], cfg, entry_window=entry_window,
        )
        if choice is not None and choice[1] > 0:
            selected.append(choice[0])
    selected.sort(
        key=lambda value: (
            value["fill_date"], -value["edge_rank"], value["symbol"],
        ),
    )
    original = portfolio_backtest._candidate_signals
    try:
        portfolio_backtest._candidate_signals = lambda *args, **kwargs: selected
        oracle = run_portfolio({}, prices, cfg)
    finally:
        portfolio_backtest._candidate_signals = original
    return oracle, {
        "lookahead": True, "deployable": False,
        "purpose": "perfect one-entry timing per detection with baseline stop/60d exit",
        "base_detection_signals": len(base_signals),
        "future_profitable_timed_signals": len(selected),
        "entry_window": entry_window,
    }


def compact_portfolio(portfolio: dict) -> dict:
    return {
        "summary": portfolio["summary"],
        "trade_stats": trade_stats(portfolio["trades"]),
        "exposure": exposure_stats(portfolio),
    }


def report_markdown(report: dict) -> str:
    lines = [
        "# Train-Only Signal-Density and Oracle Feasibility Audit", "",
        "The oracle below uses future returns and is **not deployable, causal, or scoreable**. "
        "It is a winner-only ceiling diagnostic for the current baseline exit, "
        "not a formal upper bound over other exits.", "",
        "| Cell | Signals | Trades | Net CAGR | Avg exposure | Avg positions | Invested sessions | 20% hurdle on exposed capital |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, cell in report["cells"].items():
        s, e = cell["summary"], cell["exposure"]
        hurdle = e["approx_exposed_capital_return_needed_for_20pct_cagr_pct"]
        lines.append(
            f"| {name} | {s['signals']} | {s['trades']} | {s['cagr_pct']:.2f}% | "
            f"{e['average_exposure_pct']:.2f}% | {e['average_positions']:.2f} | "
            f"{e['invested_sessions_pct']:.1f}% | {hurdle:.1f}% |"
        )
    oracle = report["oracle_metadata"]
    lines += [
        "", "## Interpretation", "",
        f"The densest causal book generated {report['cells']['detection_entry']['summary']['signals']} "
        "signals but maintained low average capital exposure. The perfect-foresight oracle retained "
        f"{oracle['future_positive_signals']} of {oracle['all_detection_signals']} detection signals.",
        "", "If the oracle clears 20% CAGR, the fixed portfolio is capable of the target in-sample, "
        "but a strong causal selector/exit is still missing. If it does not, this entry/exit opportunity "
        "set is structurally insufficient and should not be refined further.", "",
        f"The joint entry/exit oracle reached {report['cells']['future_entry_exit_oracle_60']['summary']['cagr_pct']:.2f}% "
        "CAGR at 60 sessions; 120/252-session diagnostic horizons are reported separately.", "",
        f"Perfect entry timing with the ordinary hard-stop/60-session exit reached only "
        f"{report['cells']['future_timing_baseline_exit_oracle']['summary']['cagr_pct']:.2f}% CAGR. "
        "Therefore entry timing alone cannot reach the 20% target even with foresight; a causal "
        "timing rule and a materially better exit mechanism are both required.", "",
        "Validation and untouched OOS were not accessed by this audit.", "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--output-dir", default="backtests/train_feasibility_audit")
    args = ap.parse_args()
    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/benchmark gate failed")
    payload = json.loads(Path(args.backtest_json).read_text())
    detections, dropped = filter_detections(
        payload.get("detections_by_ticker") or {}, load_membership(args.membership_csv),
        START, END,
    )
    client = CSVClient(args.price_csv)
    prices = slice_prices({
        row["symbol"]: list(reversed(client.get_historical_prices(
            row["symbol"], days=100_000,
        )["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]
    }, START, END)
    cfg = Config()
    portfolios = {
        "detection_entry": run_portfolio(
            detections, prices, cfg, entry_rule="detection_entry",
        ),
        "pivot_retest": run_portfolio(
            detections, prices, cfg, entry_rule="pivot_retest",
        ),
        "down_close_pivot_hold": run_portfolio(
            detections, prices, cfg, entry_rule="down_close_pivot_hold",
            entry_params={"window": 10},
        ),
    }
    oracle, oracle_metadata = oracle_winner_portfolio(detections, prices, cfg)
    portfolios["future_winner_oracle"] = oracle
    entry_exit_oracles, entry_exit_oracle_metadata = {}, {}
    for horizon in (60, 120, 252):
        oracle_cell, metadata = oracle_entry_exit_portfolio(
            detections, prices, cfg, max_hold_bars=horizon,
        )
        portfolios[f"future_entry_exit_oracle_{horizon}"] = oracle_cell
        entry_exit_oracle_metadata[str(horizon)] = metadata
    timing_oracle_metadata = {}
    for horizon in (60, 120, 252):
        oracle_cell, metadata = oracle_timing_portfolio(
            detections, prices, cfg, max_hold_bars=horizon,
        )
        portfolios[f"future_timing_oracle_{horizon}"] = oracle_cell
        timing_oracle_metadata[str(horizon)] = metadata
    baseline_timing_oracle, baseline_timing_metadata = oracle_baseline_timing_portfolio(
        detections, prices, cfg,
    )
    portfolios["future_timing_baseline_exit_oracle"] = baseline_timing_oracle
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "period": [START, END], "validation_accessed": False,
        "untouched_oos_accessed": False, "coverage": coverage,
        "membership_drops": dropped,
        "cells": {name: compact_portfolio(value) for name, value in portfolios.items()},
        "oracle_metadata": oracle_metadata,
        "entry_exit_oracle_metadata": entry_exit_oracle_metadata,
        "timing_oracle_metadata": timing_oracle_metadata,
        "baseline_timing_oracle_metadata": baseline_timing_metadata,
    }
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    prefix = out / f"train_feasibility_{stamp}"
    prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n",
    )
    prefix.with_suffix(".md").write_text(report_markdown(report))
    print(json.dumps({
        "cells": {name: value["summary"] for name, value in report["cells"].items()},
        "oracle_metadata": oracle_metadata,
        "entry_exit_oracle_metadata": entry_exit_oracle_metadata,
        "timing_oracle_metadata": timing_oracle_metadata,
        "baseline_timing_oracle_metadata": baseline_timing_metadata,
    }, indent=2))
    print(prefix.with_suffix(".json")); print(prefix.with_suffix(".md"))


if __name__ == "__main__":
    main()
