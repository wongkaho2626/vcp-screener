#!/usr/bin/env python3
"""Prespecified Trial 313-315 p70 prove-it/reset lifecycle discovery."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from csv_client import CSVClient
from linear_timing_discovery import (
    CALIBRATION, CALIBRATION_PRICE_END, FIT, FIT_PRICE_END, HOLDOUT,
    build_rows, compact, evaluate, fit_ridge, score_features, threshold_from_rows,
)
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import filter_detections, slice_prices
from undercut_reclaim_discovery import gate


def lifecycle_signals(rows: list[dict], model: dict, prices: dict[str, list[dict]],
                      entry_threshold: float, reset_threshold: float,
                      cooldown: int = 5, max_attempts: int = 3) -> list[dict]:
    by_setup: dict[str, list[dict]] = {}
    for row in rows:
        by_setup.setdefault(row["setup_id"], []).append(row)
    signals = []
    for setup_rows in by_setup.values():
        ordered = sorted(setup_rows, key=lambda row: row["signal_date"])
        cursor = 0; last_entry_idx = -10**9
        for attempt in range(1, max_attempts + 1):
            entry_pos = next((j for j in range(cursor, len(ordered))
                              if ordered[j]["fill_idx"] - last_entry_idx >= cooldown
                              and score_features(ordered[j]["features"], model)
                              >= entry_threshold), None)
            if entry_pos is None:
                break
            entry = ordered[entry_pos]
            later = list(range(entry_pos + 1, len(ordered)))
            decay_pos = next((j for j in later
                              if score_features(ordered[j]["features"], model)
                              <= reset_threshold), None)
            exit_candidates = []
            if decay_pos is not None:
                exit_candidates.append(ordered[decay_pos]["fill_idx"])
            bars = prices.get(entry["symbol"]) or []
            checkpoint_idx = entry["fill_idx"] + 4
            if checkpoint_idx + 1 < len(bars):
                checkpoint_close = float(bars[checkpoint_idx].get("close") or 0)
                if checkpoint_close < float(entry["fill_open"]):
                    exit_candidates.append(checkpoint_idx + 1)
            signal = {key: entry[key] for key in (
                "symbol", "sector", "signal_date", "fill_date", "fill_idx",
                "edge_rank", "pattern_stop", "pivot",
            )}
            signal["attempt"] = attempt
            planned_exit = min(exit_candidates) if exit_candidates else None
            if planned_exit is not None:
                signal["model_exit_idx"] = planned_exit
            signals.append(signal); last_entry_idx = entry["fill_idx"]
            if planned_exit is None:
                break
            reset_pos = next((j for j in later
                              if ordered[j]["fill_idx"] >= planned_exit
                              and score_features(ordered[j]["features"], model)
                              <= reset_threshold), None)
            if reset_pos is None:
                break
            cursor = reset_pos + 1
    return sorted(signals, key=lambda row: (
        row["fill_date"], -row["edge_rank"], row["symbol"],
    ))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--output-dir", default="backtests/prove_it_lifecycle_v2/results")
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
    fit_dets, fit_drops = filter_detections(detections, membership, *FIT)
    fit_rows = build_rows(fit_dets, slice_prices(prices_all, FIT[0], FIT_PRICE_END),
                          with_labels=True, label_mode="forward20")
    model = fit_ridge(fit_rows)
    cal_dets, cal_drops = filter_detections(detections, membership, *CALIBRATION)
    cal_rows = build_rows(cal_dets, slice_prices(prices_all, CALIBRATION[0],
                                                CALIBRATION_PRICE_END), with_labels=False)
    entry_threshold = threshold_from_rows(cal_rows, model, 70)
    reset_threshold = threshold_from_rows(cal_rows, model, 50)
    discovery_dets, discovery_drops = filter_detections(detections, membership, *HOLDOUT)
    prices = slice_prices(prices_all, *HOLDOUT)
    rows = build_rows(discovery_dets, prices, with_labels=False)
    signals = lifecycle_signals(rows, model, prices, entry_threshold, reset_threshold)
    raw = evaluate(signals, prices, args.iterations, exit_rule="model_decay",
                   trials_declared=315)
    cell = compact(raw); discovery_gate = gate(cell, 80, 10)
    report = {"generated_at": datetime.now().isoformat(timespec="seconds"),
              "family_spec": "backtests/prove_it_lifecycle_v2/frozen_spec.md",
              "formal_validation_accessed": False, "untouched_oos_accessed": False,
              "period": HOLDOUT, "period_role": "recycled discovery",
              "coverage": coverage, "trials_before": 312,
              "new_multiplicity_units": 3, "trials_after": 315,
              "membership_drops": {"fit": fit_drops, "calibration": cal_drops,
                                   "discovery": discovery_drops},
              "model": model,
              "parameters": {"entry_percentile": 70, "entry_threshold": entry_threshold,
                             "reset_percentile": 50, "reset_threshold": reset_threshold,
                             "underwater_checkpoint_sessions": 5,
                             "cooldown_sessions": 5, "max_attempts": 3},
              "discovery": {"candidate_rows": len(rows), "signals": signals,
                            "cell": cell, "gate": discovery_gate},
              "open_formal_validation": discovery_gate["passed"]}
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    jp = out / f"prove_it_lifecycle_{stamp}.json"
    mp = out / f"prove_it_lifecycle_{stamp}.md"
    jp.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 313–315 — P70 Prove-It Lifecycle", "",
             "Formal validation accessed: **NO**", "",
             f"Signals {len(signals)}; trades {cell['trade_stats']['trades']}; "
             f"CAGR {cell['summary']['cagr_pct']:.2f}%; "
             f"Sharpe {(adjusted.get('sharpe') or 0):.3f}; "
             f"PF {(cell['trade_stats'].get('profit_factor') or 0):.3f}; "
             f"MDD {cell['summary']['max_drawdown_pct']:.2f}%; "
             f"trim-5 expectancy {(cell['drop_top_5'].get('expectancy_pct') or 0):.2f}%.", "",
             f"Discovery gate: **{'PASS' if discovery_gate['passed'] else 'FAIL'}**", ""]
    lines.extend(f"- {'PASS' if passed else 'FAIL'} — {name}"
                 for name, passed in discovery_gate["checks"].items())
    lines += ["", "Formal validation and untouched OOS remain sealed.", ""]
    mp.write_text("\n".join(lines))
    if raw["trades"]:
        pd.DataFrame(raw["trades"]).to_csv(out / f"prove_it_lifecycle_{stamp}_trades.csv",
                                             index=False)
    if raw["equity_curve"]:
        pd.DataFrame(raw["equity_curve"]).to_csv(out / f"prove_it_lifecycle_{stamp}_daily.csv",
                                                  index=False)
    print(json.dumps({"signals": len(signals), "summary": cell["summary"],
                      "trade_stats": cell["trade_stats"], "gate": discovery_gate,
                      "open_formal_validation": discovery_gate["passed"]}, indent=2))
    print(jp); print(mp)


if __name__ == "__main__":
    main()
