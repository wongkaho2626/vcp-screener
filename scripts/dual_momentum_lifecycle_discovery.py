#!/usr/bin/env python3
"""Prespecified Trial 320-323 dual-momentum VCP lifecycle."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from csv_client import CSVClient
from linear_timing_discovery import FIT, FIT_PRICE_END, HOLDOUT, build_rows, compact, evaluate
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import filter_detections, slice_prices
from undercut_reclaim_discovery import gate


def momentum(bars: list[dict], index: int, lag: int) -> float | None:
    """Close-to-close momentum using no bar later than ``index``."""
    if lag <= 0 or index - lag < 0:
        return None
    close = float(bars[index].get("close") or 0)
    prior = float(bars[index - lag].get("close") or 0)
    return close / prior - 1 if close > 0 and prior > 0 else None


def sma(bars: list[dict], index: int, period: int) -> float | None:
    """Causal simple moving average ending at ``index``."""
    if period <= 0 or index - period + 1 < 0:
        return None
    values = [float(row.get("close") or 0)
              for row in bars[index - period + 1:index + 1]]
    return sum(values) / period if all(value > 0 for value in values) else None


def entry_state(bars: list[dict], signal_idx: int) -> dict | None:
    """Return causal dual-momentum state when a fresh crossing occurs."""
    long_momentum = momentum(bars, signal_idx - 21, 231)
    short_momentum = momentum(bars, signal_idx, 5)
    prior_short = momentum(bars, signal_idx - 1, 5)
    if (long_momentum is None or short_momentum is None or prior_short is None
            or long_momentum <= 0 or prior_short > 0 or short_momentum <= 0):
        return None
    return {"momentum_12_1": long_momentum,
            "momentum_5": short_momentum,
            "prior_momentum_5": prior_short}


def next_sma20_exit(bars: list[dict], entry_idx: int) -> int | None:
    """Next-open exit index after a close below SMA20, capped at 60 sessions."""
    terminal = min(entry_idx + 59, len(bars) - 2)
    for index in range(entry_idx, terminal + 1):
        average = sma(bars, index, 20)
        if average is not None and float(bars[index].get("close") or 0) < average:
            return index + 1
    return None


def lifecycle_signals(rows: list[dict], prices: dict[str, list[dict]],
                      max_attempts: int = 3) -> list[dict]:
    """Emit non-overlapping momentum cycles for each frozen VCP setup."""
    by_setup: dict[str, list[dict]] = {}
    for row in rows:
        by_setup.setdefault(row["setup_id"], []).append(row)
    signals = []
    for setup_rows in by_setup.values():
        next_eligible = -1
        attempts = 0
        for row in sorted(setup_rows, key=lambda item: item["fill_idx"]):
            if attempts >= max_attempts or row["fill_idx"] < next_eligible:
                continue
            bars = prices.get(row["symbol"]) or []
            signal_idx = row["fill_idx"] - 1
            state = entry_state(bars, signal_idx)
            if state is None:
                continue
            exit_idx = next_sma20_exit(bars, row["fill_idx"])
            signal = {key: row[key] for key in (
                "symbol", "sector", "signal_date", "fill_date", "fill_idx",
                "edge_rank", "pattern_stop", "pivot",
            )}
            attempts += 1
            signal.update(state)
            signal["attempt"] = attempts
            if exit_idx is not None:
                signal["model_exit_idx"] = exit_idx
                next_eligible = exit_idx
            else:
                next_eligible = row["fill_idx"] + 60
            signals.append(signal)
    return sorted(signals, key=lambda row: (
        row["fill_date"], -row["edge_rank"], row["symbol"],
    ))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--output-dir", default="backtests/dual_momentum_lifecycle_v2/results")
    ap.add_argument("--iterations", type=int, default=1000)
    args = ap.parse_args()

    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/benchmark gate failed")
    detections = json.loads(Path(args.backtest_json).read_text())["detections_by_ticker"]
    membership = load_membership(args.membership_csv)
    client = CSVClient(args.price_csv)
    prices_all = {row["symbol"]: list(reversed(client.get_historical_prices(
        row["symbol"], days=100_000)["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]}

    train_dets, train_drops = filter_detections(detections, membership, *FIT)
    train_prices = slice_prices(prices_all, FIT[0], FIT_PRICE_END)
    train_rows = build_rows(train_dets, train_prices, with_labels=False)
    train_signals = lifecycle_signals(train_rows, train_prices)
    train_raw = evaluate(train_signals, train_prices, args.iterations,
                         exit_rule="model_decay", trials_declared=323)
    train_cell = compact(train_raw)
    train_gate = gate(train_cell, 60, 10)

    holdout = None
    holdout_raw = None
    holdout_drops = None
    if train_gate["passed"]:
        holdout_dets, holdout_drops = filter_detections(detections, membership, *HOLDOUT)
        holdout_prices = slice_prices(prices_all, *HOLDOUT)
        holdout_rows = build_rows(holdout_dets, holdout_prices, with_labels=False)
        holdout_signals = lifecycle_signals(holdout_rows, holdout_prices)
        holdout_raw = evaluate(holdout_signals, holdout_prices, args.iterations,
                               exit_rule="model_decay", trials_declared=323)
        holdout_cell = compact(holdout_raw)
        holdout = {"signals": holdout_signals, "cell": holdout_cell,
                   "gate": gate(holdout_cell, 60, 15)}

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/dual_momentum_lifecycle_v2/frozen_spec.md",
        "formal_validation_accessed": False,
        "untouched_oos_accessed": False,
        "internal_holdout_accessed": holdout is not None,
        "coverage": coverage,
        "trials_before": 319,
        "new_multiplicity_units": 4,
        "trials_after": 323,
        "parameters": {"long_lookback_sessions": 252,
                       "skip_recent_sessions": 21,
                       "short_momentum_sessions": 5,
                       "exit_sma_sessions": 20,
                       "max_attempts": 3,
                       "max_hold_sessions": 60},
        "membership_drops": {"train": train_drops, "holdout": holdout_drops},
        "train": {"signals": train_signals, "cell": train_cell, "gate": train_gate},
        "internal_holdout": holdout,
        "open_formal_validation": bool(holdout and holdout["gate"]["passed"]),
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    jp = out / f"dual_momentum_lifecycle_{stamp}.json"
    mp = out / f"dual_momentum_lifecycle_{stamp}.md"
    jp.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (train_cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 320–323 — Dual-Momentum VCP Lifecycle", "",
             "Formal validation accessed: **NO**", "",
             f"Train signals {len(train_signals)}; trades {train_cell['trade_stats']['trades']}; "
             f"CAGR {train_cell['summary']['cagr_pct']:.2f}%; "
             f"Sharpe {(adjusted.get('sharpe') or 0):.3f}; "
             f"PF {(train_cell['trade_stats'].get('profit_factor') or 0):.3f}; "
             f"MDD {train_cell['summary']['max_drawdown_pct']:.2f}%; "
             f"trim-5 expectancy {(train_cell['drop_top_5'].get('expectancy_pct') or 0):.2f}%.", "",
             f"Train gate: **{'PASS' if train_gate['passed'] else 'FAIL'}**", ""]
    lines.extend(f"- {'PASS' if passed else 'FAIL'} — {name}"
                 for name, passed in train_gate["checks"].items())
    lines += ["", f"Internal holdout accessed: **{'YES' if holdout else 'NO'}**", "",
              "Formal validation and untouched OOS remain sealed.", ""]
    mp.write_text("\n".join(lines))
    if train_raw["trades"]:
        pd.DataFrame(train_raw["trades"]).to_csv(
            out / f"dual_momentum_lifecycle_{stamp}_train_trades.csv", index=False)
        pd.DataFrame(train_raw["equity_curve"]).to_csv(
            out / f"dual_momentum_lifecycle_{stamp}_train_daily.csv", index=False)
    if holdout_raw and holdout_raw["trades"]:
        pd.DataFrame(holdout_raw["trades"]).to_csv(
            out / f"dual_momentum_lifecycle_{stamp}_holdout_trades.csv", index=False)
        pd.DataFrame(holdout_raw["equity_curve"]).to_csv(
            out / f"dual_momentum_lifecycle_{stamp}_holdout_daily.csv", index=False)
    print(json.dumps({"train_signals": len(train_signals),
                      "train_summary": train_cell["summary"],
                      "train_gate": train_gate,
                      "internal_holdout_accessed": holdout is not None,
                      "open_formal_validation": report["open_formal_validation"]}, indent=2))
    print(jp)
    print(mp)


if __name__ == "__main__":
    main()
