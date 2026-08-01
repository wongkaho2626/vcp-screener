#!/usr/bin/env python3
"""Prespecified Trial 478-482 month-start flow lifecycle."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from anchored_vwap_reclaim_discovery import _period_rows, _score_table
from cross_sectional_leadership_discovery import discovery_backtest_score
from csv_client import CSVClient
from dmi_crossover_lifecycle_discovery import (
    VALIDATION,
    VALIDATION_PRICE_END,
    VALIDATION_PRICE_START,
)
from linear_timing_discovery import FIT, FIT_PRICE_END, compact, evaluate
from macd_crossover_lifecycle_discovery import DENSITY_MAX, DENSITY_MIN
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import slice_prices
from undercut_reclaim_discovery import gate

HOLD_SESSIONS = 3
MAX_ATTEMPTS = 3
TRIALS_BEFORE = 477
TRIALS_AFTER = 482


def first_session_dates(benchmark_bars: list[dict]) -> set[str]:
    """Return observed month transitions from the benchmark calendar.

    The first bar of a truncated benchmark slice is deliberately ineligible:
    without a preceding benchmark session, the slice cannot prove that it is
    the market's first session of that month.
    """
    dates: set[str] = set()
    previous_month: str | None = None
    for bar in benchmark_bars:
        value = str(bar["date"])
        month = value[:7]
        if previous_month is not None and month != previous_month:
            dates.add(value)
        previous_month = month
    return dates


def month_start_signals(
    rows: list[dict], prices: dict[str, list[dict]],
    benchmark_bars: list[dict], hold_sessions: int = HOLD_SESSIONS,
    max_attempts: int = MAX_ATTEMPTS,
) -> list[dict]:
    """Emit non-overlapping next-open entries from completed month-start bars."""
    if hold_sessions <= 0 or max_attempts <= 0:
        raise ValueError("lifecycle parameters must be positive")
    month_starts = first_session_dates(benchmark_bars)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["setup_id"]].append(row)
    signals: list[dict] = []
    for setup_rows in grouped.values():
        ordered = sorted(setup_rows, key=lambda item: int(item["fill_idx"]))
        symbol = ordered[0]["symbol"] if ordered else ""
        bars = prices.get(symbol) or []
        attempts = 0
        eligible_fill_idx = -1
        for row in ordered:
            if attempts >= max_attempts:
                break
            if int(row["fill_idx"]) < eligible_fill_idx:
                continue
            if row["signal_date"] not in month_starts:
                continue
            close = float(row.get("close") or 0)
            if close <= float(row["pivot"]) or close < float(row["pattern_stop"]):
                continue
            attempts += 1
            signal = {key: row[key] for key in (
                "symbol", "sector", "signal_date", "fill_date", "fill_idx",
                "edge_rank", "pattern_stop", "pivot",
            )}
            signal["attempt"] = attempts
            model_exit_idx = int(row["fill_idx"]) + hold_sessions
            if model_exit_idx < len(bars):
                signal["model_exit_idx"] = model_exit_idx
            eligible_fill_idx = model_exit_idx
            signals.append(signal)
    return sorted(signals, key=lambda row: (
        row["fill_date"], -row["edge_rank"], row["symbol"], row["attempt"],
    ))


def _density_report(output: Path, stamp: str, coverage: dict,
                    rows: list[dict], signals: list[dict], drops: int) -> None:
    density = {
        "active_setup_rows": len(rows), "signals": len(signals),
        "symbols": len({row["symbol"] for row in signals}),
        "minimum": DENSITY_MIN, "maximum": DENSITY_MAX, "passed": False,
    }
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/month_start_flow_lifecycle_v2/frozen_spec.md",
        "classification": "outcome_free_density_only",
        "return_evaluation_accessed": False,
        "validation_accessed": False,
        "best_available_oos_accessed": False,
        "coverage": coverage, "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": TRIALS_AFTER - TRIALS_BEFORE,
        "trials_after": TRIALS_AFTER,
        "parameters": {"calendar": "first completed SPY session of month",
                       "pivot": "strict close above frozen pivot",
                       "hold_sessions": HOLD_SESSIONS,
                       "max_attempts": MAX_ATTEMPTS},
        "density": density, "membership_drops": drops,
        "permission_to_evaluate_returns": False,
    }
    json_path = output / f"month_start_flow_{stamp}.json"
    md_path = output / f"month_start_flow_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    md_path.write_text(
        "# Trial 478–482 — Month-Start Flow Density Audit\n\n"
        "Return evaluation accessed: **NO**\n\n"
        f"Signals: **{len(signals)}** across {density['symbols']} symbols; "
        f"required {DENSITY_MIN}–{DENSITY_MAX}.\n\n"
        "Density gate: **FAIL**. The family is closed outcome-free; validation "
        "and best-available OOS remain sealed.\n"
    )
    print(json.dumps(density, indent=2)); print(json_path); print(md_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--output-dir",
                        default="backtests/month_start_flow_lifecycle_v2/results")
    parser.add_argument("--iterations", type=int, default=1000)
    args = parser.parse_args()
    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/benchmark gate failed")
    detections = json.loads(Path(args.backtest_json).read_text())["detections_by_ticker"]
    membership = load_membership(args.membership_csv)
    client = CSVClient(args.price_csv)
    prices_all = {row["symbol"]: list(reversed(client.get_historical_prices(
        row["symbol"], days=100_000)["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]}

    train_prices = slice_prices(prices_all, FIT[0], FIT_PRICE_END)
    train_rows, train_drops = _period_rows(
        detections, membership, train_prices, *FIT)
    train_signals = month_start_signals(
        train_rows, train_prices, train_prices.get("SPY") or [])
    output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    if not DENSITY_MIN <= len(train_signals) <= DENSITY_MAX:
        _density_report(output, stamp, coverage, train_rows, train_signals,
                        train_drops)
        return

    train_raw = evaluate(train_signals, train_prices, args.iterations,
                         exit_rule="model_decay", trials_declared=TRIALS_AFTER)
    train_cell = compact(train_raw)
    train_gate = gate(train_cell, 60, 10)
    train_score = discovery_backtest_score(train_cell)

    validation = validation_raw = validation_drops = None
    if train_gate["passed"]:
        validation_prices = slice_prices(
            prices_all, VALIDATION_PRICE_START, VALIDATION_PRICE_END)
        validation_rows, validation_drops = _period_rows(
            detections, membership, validation_prices, *VALIDATION)
        validation_signals = month_start_signals(
            validation_rows, validation_prices, validation_prices.get("SPY") or [])
        validation_raw = evaluate(
            validation_signals, validation_prices, args.iterations,
            exit_rule="model_decay", trials_declared=TRIALS_AFTER)
        validation_cell = compact(validation_raw)
        validation = {
            "candidate_rows": len(validation_rows),
            "signals": validation_signals, "cell": validation_cell,
            "score": discovery_backtest_score(validation_cell),
            "gate": gate(validation_cell, 60, 15),
        }

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/month_start_flow_lifecycle_v2/frozen_spec.md",
        "backtest_score": train_score,
        "formal_validation_accessed": validation is not None,
        "best_available_oos_accessed": False,
        "coverage": coverage, "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": TRIALS_AFTER - TRIALS_BEFORE,
        "trials_after": TRIALS_AFTER,
        "parameters": {"calendar": "first completed SPY session of month",
                       "pivot": "strict close above frozen pivot",
                       "hold_sessions": HOLD_SESSIONS,
                       "max_attempts": MAX_ATTEMPTS},
        "density": {"active_setup_rows": len(train_rows),
                    "signals": len(train_signals), "minimum": DENSITY_MIN,
                    "maximum": DENSITY_MAX, "passed": True},
        "chronology": {"train": FIT, "embargo": ["2018-07-01", "2018-12-31"],
                       "validation": VALIDATION,
                       "best_available_frozen_oos": ["2022-01-01", "2026-03-31"]},
        "membership_drops": {"train": train_drops,
                             "validation": validation_drops},
        "train": {"signals": train_signals, "cell": train_cell,
                  "gate": train_gate},
        "validation": validation,
        "open_best_available_oos": bool(validation and validation["gate"]["passed"]),
    }
    json_path = output / f"month_start_flow_{stamp}.json"
    md_path = output / f"month_start_flow_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (train_cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 478–482 — Month-Start Institutional-Flow Lifecycle", "",
             "Best-available frozen OOS accessed: **NO**", "",
             *_score_table(train_score),
             f"Train signals {len(train_signals)}; trades "
             f"{train_cell['trade_stats']['trades']}; CAGR "
             f"{train_cell['summary']['cagr_pct']:.2f}%; Sharpe "
             f"{(adjusted.get('sharpe') or 0):.3f}; PF "
             f"{(train_cell['trade_stats'].get('profit_factor') or 0):.3f}; "
             f"MDD {train_cell['summary']['max_drawdown_pct']:.2f}%; trim-5 "
             f"expectancy {(train_cell['drop_top_5'].get('expectancy_pct') or 0):.2f}%.", "",
             f"Train gate: **{'PASS' if train_gate['passed'] else 'FAIL'}**", ""]
    lines.extend(f"- {'PASS' if passed else 'FAIL'} — {name}"
                 for name, passed in train_gate["checks"].items())
    lines += ["", f"2019–2021 validation accessed: "
              f"**{'YES' if validation else 'NO'}**", "",
              "2022–2026Q1 best-available OOS remains sealed.", ""]
    md_path.write_text("\n".join(lines))
    if train_raw["trades"]:
        pd.DataFrame(train_raw["trades"]).to_csv(
            output / f"month_start_flow_{stamp}_train_trades.csv", index=False)
        pd.DataFrame(train_raw["equity_curve"]).to_csv(
            output / f"month_start_flow_{stamp}_train_daily.csv", index=False)
    if validation_raw and validation_raw["trades"]:
        pd.DataFrame(validation_raw["trades"]).to_csv(
            output / f"month_start_flow_{stamp}_validation_trades.csv", index=False)
        pd.DataFrame(validation_raw["equity_curve"]).to_csv(
            output / f"month_start_flow_{stamp}_validation_daily.csv", index=False)
    print(json.dumps({"train_signals": len(train_signals),
                      "train_summary": train_cell["summary"],
                      "train_gate": train_gate, "backtest_score": train_score,
                      "validation_accessed": validation is not None,
                      "open_best_available_oos": report["open_best_available_oos"]},
                     indent=2))
    print(json_path); print(md_path)


if __name__ == "__main__":
    main()
