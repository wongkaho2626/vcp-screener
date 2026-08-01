#!/usr/bin/env python3
"""Prespecified Trial 316-319 RSI(2) mean-reversion VCP lifecycle."""

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


def rsi2(bars: list[dict], index: int) -> float:
    if index < 2:
        return 50.0
    changes = [float(bars[i]["close"]) - float(bars[i - 1]["close"])
               for i in (index - 1, index)]
    gain = sum(max(change, 0) for change in changes) / 2
    loss = sum(max(-change, 0) for change in changes) / 2
    return 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)


def lifecycle_signals(rows: list[dict], prices: dict[str, list[dict]],
                      cooldown: int = 5, max_attempts: int = 3) -> list[dict]:
    by_setup: dict[str, list[dict]] = {}
    for row in rows:
        by_setup.setdefault(row["setup_id"], []).append(row)
    signals = []
    for setup_rows in by_setup.values():
        attempts = 0; last_entry = -10**9
        for row in sorted(setup_rows, key=lambda item: item["fill_idx"]):
            bars = prices.get(row["symbol"]) or []
            signal_idx = row["fill_idx"] - 1
            if row["fill_idx"] - last_entry < cooldown or rsi2(bars, signal_idx) >= 10:
                continue
            exit_idx = min(row["fill_idx"] + 5, len(bars) - 1)
            for i in range(row["fill_idx"], min(row["fill_idx"] + 5, len(bars) - 1)):
                if i < 4:
                    continue
                sma5 = sum(float(bar["close"]) for bar in bars[i - 4:i + 1]) / 5
                if float(bars[i]["close"]) > sma5:
                    exit_idx = i + 1
                    break
            signal = {key: row[key] for key in (
                "symbol", "sector", "signal_date", "fill_date", "fill_idx",
                "edge_rank", "pattern_stop", "pivot",
            )}
            attempts += 1; signal["attempt"] = attempts
            signal["model_exit_idx"] = exit_idx
            signal["rsi2"] = rsi2(bars, signal_idx)
            signals.append(signal); last_entry = row["fill_idx"]
            if attempts >= max_attempts:
                break
    return sorted(signals, key=lambda row: (
        row["fill_date"], -row["edge_rank"], row["symbol"],
    ))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--output-dir", default="backtests/rsi2_lifecycle_v2/results")
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
                         exit_rule="fixed_time", trials_declared=319)
    train_cell = compact(train_raw); train_gate = gate(train_cell, 120, 10)
    holdout = None; holdout_raw = None; holdout_drops = None
    if train_gate["passed"]:
        holdout_dets, holdout_drops = filter_detections(detections, membership, *HOLDOUT)
        holdout_prices = slice_prices(prices_all, *HOLDOUT)
        holdout_rows = build_rows(holdout_dets, holdout_prices, with_labels=False)
        holdout_signals = lifecycle_signals(holdout_rows, holdout_prices)
        holdout_raw = evaluate(holdout_signals, holdout_prices, args.iterations,
                               exit_rule="fixed_time", trials_declared=319)
        holdout_cell = compact(holdout_raw)
        holdout = {"signals": holdout_signals, "cell": holdout_cell,
                   "gate": gate(holdout_cell, 150, 15)}
    report = {"generated_at": datetime.now().isoformat(timespec="seconds"),
              "family_spec": "backtests/rsi2_lifecycle_v2/frozen_spec.md",
              "formal_validation_accessed": False, "untouched_oos_accessed": False,
              "internal_holdout_accessed": holdout is not None,
              "coverage": coverage, "trials_before": 315,
              "new_multiplicity_units": 4, "trials_after": 319,
              "parameters": {"rsi_period": 2, "entry_below": 10,
                             "exit_sma": 5, "max_hold_sessions": 5,
                             "cooldown_sessions": 5, "max_attempts": 3},
              "membership_drops": {"train": train_drops, "holdout": holdout_drops},
              "train": {"signals": train_signals, "cell": train_cell, "gate": train_gate},
              "internal_holdout": holdout,
              "open_formal_validation": bool(holdout and holdout["gate"]["passed"])}
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    jp = out / f"rsi2_lifecycle_{stamp}.json"; mp = out / f"rsi2_lifecycle_{stamp}.md"
    jp.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (train_cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 316–319 — RSI2 VCP Lifecycle", "",
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
        pd.DataFrame(train_raw["trades"]).to_csv(out / f"rsi2_lifecycle_{stamp}_train_trades.csv",
                                                  index=False)
        pd.DataFrame(train_raw["equity_curve"]).to_csv(out / f"rsi2_lifecycle_{stamp}_train_daily.csv",
                                                        index=False)
    if holdout_raw and holdout_raw["trades"]:
        pd.DataFrame(holdout_raw["trades"]).to_csv(out / f"rsi2_lifecycle_{stamp}_holdout_trades.csv",
                                                    index=False)
        pd.DataFrame(holdout_raw["equity_curve"]).to_csv(out / f"rsi2_lifecycle_{stamp}_holdout_daily.csv",
                                                          index=False)
    print(json.dumps({"train_signals": len(train_signals),
                      "train_summary": train_cell["summary"], "train_gate": train_gate,
                      "internal_holdout_accessed": holdout is not None,
                      "open_formal_validation": report["open_formal_validation"]}, indent=2))
    print(jp); print(mp)


if __name__ == "__main__":
    main()
