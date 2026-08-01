#!/usr/bin/env python3
"""Prespecified Trial 324-327 SMA20 opening-limit recovery lifecycle."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from csv_client import CSVClient
from dual_momentum_lifecycle_discovery import sma
from linear_timing_discovery import FIT, FIT_PRICE_END, HOLDOUT, build_rows, compact, evaluate
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import filter_detections, slice_prices
from undercut_reclaim_discovery import gate


def opening_limit_trigger(row: dict, bars: list[dict]) -> dict | None:
    """Return causal resting-limit details for the row's next-open fill."""
    signal_idx = int(row["fill_idx"]) - 1
    if signal_idx < 19 or row["fill_idx"] >= len(bars):
        return None
    average = sma(bars, signal_idx, 20)
    signal_close = float(bars[signal_idx].get("close") or 0)
    next_open = float(bars[row["fill_idx"]].get("open") or 0)
    stop = float(row["pattern_stop"])
    if (average is None or not signal_close > average > stop
            or next_open > average or next_open <= stop):
        return None
    return {"limit_price": average, "pre_gap_close": signal_close,
            "raw_entry_price": next_open}


def recovery_exit_index(bars: list[dict], entry_idx: int,
                        target_close: float, hold_sessions: int = 10) -> int:
    """Next-open gap-recovery exit or the prespecified ten-session timeout."""
    timeout = min(entry_idx + hold_sessions, len(bars) - 1)
    final_close_idx = min(entry_idx + hold_sessions - 1, len(bars) - 2)
    for index in range(entry_idx, final_close_idx + 1):
        if float(bars[index].get("close") or 0) >= target_close:
            return index + 1
    return timeout


def lifecycle_signals(rows: list[dict], prices: dict[str, list[dict]],
                      max_attempts: int = 3) -> list[dict]:
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
            trigger = opening_limit_trigger(row, bars)
            if trigger is None:
                continue
            exit_idx = recovery_exit_index(
                bars, row["fill_idx"], trigger["pre_gap_close"], 10,
            )
            signal = {key: row[key] for key in (
                "symbol", "sector", "signal_date", "fill_date", "fill_idx",
                "edge_rank", "pattern_stop", "pivot",
            )}
            attempts += 1
            signal.update(trigger)
            signal.update({"attempt": attempts, "model_exit_idx": exit_idx,
                           "entry_day_stop": True})
            signals.append(signal)
            next_eligible = exit_idx
    return sorted(signals, key=lambda row: (
        row["fill_date"], -row["edge_rank"], row["symbol"],
    ))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--output-dir", default="backtests/sma20_open_recovery_v2/results")
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
                         exit_rule="fixed_time", trials_declared=327)
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
                               exit_rule="fixed_time", trials_declared=327)
        holdout_cell = compact(holdout_raw)
        holdout = {"signals": holdout_signals, "cell": holdout_cell,
                   "gate": gate(holdout_cell, 60, 15)}

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/sma20_open_recovery_v2/frozen_spec.md",
        "formal_validation_accessed": False,
        "untouched_oos_accessed": False,
        "internal_holdout_accessed": holdout is not None,
        "coverage": coverage,
        "trials_before": 323,
        "new_multiplicity_units": 4,
        "trials_after": 327,
        "parameters": {"entry_limit_sma_sessions": 20,
                       "entry_requires_prior_close_above_limit": True,
                       "recovery_target": "pre_gap_close",
                       "max_hold_sessions": 10,
                       "max_attempts": 3,
                       "entry_day_stop_enabled": True},
        "membership_drops": {"train": train_drops, "holdout": holdout_drops},
        "train": {"signals": train_signals, "cell": train_cell, "gate": train_gate},
        "internal_holdout": holdout,
        "open_formal_validation": bool(holdout and holdout["gate"]["passed"]),
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    jp = out / f"sma20_open_recovery_{stamp}.json"
    mp = out / f"sma20_open_recovery_{stamp}.md"
    jp.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (train_cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 324–327 — SMA20 Opening-Limit Recovery", "",
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
            out / f"sma20_open_recovery_{stamp}_train_trades.csv", index=False)
        pd.DataFrame(train_raw["equity_curve"]).to_csv(
            out / f"sma20_open_recovery_{stamp}_train_daily.csv", index=False)
    if holdout_raw and holdout_raw["trades"]:
        pd.DataFrame(holdout_raw["trades"]).to_csv(
            out / f"sma20_open_recovery_{stamp}_holdout_trades.csv", index=False)
        pd.DataFrame(holdout_raw["equity_curve"]).to_csv(
            out / f"sma20_open_recovery_{stamp}_holdout_daily.csv", index=False)
    print(json.dumps({"train_signals": len(train_signals),
                      "train_summary": train_cell["summary"],
                      "train_gate": train_gate,
                      "internal_holdout_accessed": holdout is not None,
                      "open_formal_validation": report["open_formal_validation"]}, indent=2))
    print(jp)
    print(mp)


if __name__ == "__main__":
    main()
