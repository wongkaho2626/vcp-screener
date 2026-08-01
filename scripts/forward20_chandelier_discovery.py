#!/usr/bin/env python3
"""Prespecified Trial 297-299 dense timing with causal chandelier exit."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from csv_client import CSVClient
from linear_timing_discovery import (
    CALIBRATION, CALIBRATION_PRICE_END, FIT, FIT_PRICE_END, HOLDOUT,
    _atr_ratio, build_rows, compact, evaluate, fit_ridge, score_features,
    threshold_from_rows,
)
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import filter_detections, slice_prices
from pullback_followthrough_discovery import holdout_gate


def chandelier_signals(
    rows: list[dict], model: dict, prices: dict[str, list[dict]],
    entry_threshold: float, exit_threshold: float,
    arm_gain: float = .10, atr_multiple: float = 3.0,
) -> list[dict]:
    """Schedule only next-open exits from close-confirmed causal conditions."""
    by_setup: dict[str, list[dict]] = {}
    for row in rows:
        by_setup.setdefault(row["setup_id"], []).append(row)
    signals = []
    for setup_rows in by_setup.values():
        ordered = sorted(setup_rows, key=lambda value: value["signal_date"])
        entry_pos = next((j for j, row in enumerate(ordered)
                          if score_features(row["features"], model) >= entry_threshold), None)
        if entry_pos is None:
            continue
        entry = ordered[entry_pos]
        loss_decay = next((row for row in ordered[entry_pos + 1:]
                           if score_features(row["features"], model) <= exit_threshold
                           and float(row["close"]) < float(entry["fill_open"])), None)
        exit_indices = [loss_decay["fill_idx"]] if loss_decay is not None else []

        bars = prices.get(entry["symbol"]) or []
        highest_close = float(bars[entry["fill_idx"]].get("close") or 0)
        armed = False
        terminal = min(entry["fill_idx"] + 59, len(bars) - 2)
        for i in range(entry["fill_idx"], terminal + 1):
            close = float(bars[i].get("close") or 0)
            armed_before = armed
            highest_close = max(highest_close, close)
            if not armed and close >= float(entry["fill_open"]) * (1 + arm_gain):
                armed = True
            if armed_before:
                atr = _atr_ratio(bars, i) * close
                if atr > 0 and close <= highest_close - atr_multiple * atr:
                    exit_indices.append(i + 1)
                    break
        signal = {key: entry[key] for key in (
            "symbol", "sector", "signal_date", "fill_date", "fill_idx",
            "edge_rank", "pattern_stop", "pivot",
        )}
        if exit_indices:
            signal["model_exit_idx"] = min(exit_indices)
        signals.append(signal)
    return sorted(signals, key=lambda value: (
        value["fill_date"], -value["edge_rank"], value["symbol"],
    ))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--output-dir", default="backtests/forward20_chandelier_v2/results")
    ap.add_argument("--iterations", type=int, default=1000)
    args = ap.parse_args()
    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/benchmark gate failed")
    detections = json.loads(Path(args.backtest_json).read_text())["detections_by_ticker"]
    membership = load_membership(args.membership_csv)
    client = CSVClient(args.price_csv)
    prices_all = {
        row["symbol"]: list(reversed(client.get_historical_prices(
            row["symbol"], days=100_000,
        )["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]
    }
    fit_dets, fit_drops = filter_detections(detections, membership, *FIT)
    fit_rows = build_rows(fit_dets, slice_prices(prices_all, FIT[0], FIT_PRICE_END),
                          with_labels=True, label_mode="forward20")
    model = fit_ridge(fit_rows)
    cal_dets, cal_drops = filter_detections(detections, membership, *CALIBRATION)
    cal_rows = build_rows(cal_dets, slice_prices(prices_all, CALIBRATION[0],
                                                CALIBRATION_PRICE_END), with_labels=False)
    entry_threshold = threshold_from_rows(cal_rows, model, 70)
    exit_threshold = threshold_from_rows(cal_rows, model, 50)
    holdout_dets, holdout_drops = filter_detections(detections, membership, *HOLDOUT)
    holdout_prices = slice_prices(prices_all, *HOLDOUT)
    holdout_rows = build_rows(holdout_dets, holdout_prices, with_labels=False)
    signals = chandelier_signals(
        holdout_rows, model, holdout_prices, entry_threshold, exit_threshold,
    )
    raw_cell = evaluate(signals, holdout_prices, args.iterations,
                        exit_rule="model_decay", trials_declared=299)
    cell = compact(raw_cell)
    gate = holdout_gate(cell)
    gate["checks"].pop("trades>=25")
    gate["checks"]["trades>=40"] = cell["trade_stats"]["trades"] >= 40
    gate["passed"] = all(gate["checks"].values())
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/forward20_chandelier_v2/frozen_spec.md",
        "formal_validation_accessed": False, "untouched_oos_accessed": False,
        "coverage": coverage, "trials_before": 296,
        "new_multiplicity_units": 3, "trials_after": 299,
        "periods": {"fit": FIT, "calibration": CALIBRATION, "holdout": HOLDOUT},
        "membership_drops": {"fit": fit_drops, "calibration": cal_drops,
                             "holdout": holdout_drops},
        "model": model,
        "entry": {"percentile": 70, "threshold": entry_threshold},
        "exit": {"loss_decay_percentile": 50, "loss_decay_threshold": exit_threshold,
                 "arm_gain": .10, "atr_period": 20, "atr_multiple": 3.0,
                 "timeout_sessions": 60, "next_open": True},
        "internal_holdout": {"candidate_rows": len(holdout_rows),
                             "selected_signals": len(signals), "signals": signals,
                             "cell": cell, "gate": gate},
        "open_formal_validation": gate["passed"],
    }
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = out / f"forward20_chandelier_{stamp}.json"
    md_path = out / f"forward20_chandelier_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 297–299 — Dense Forward-20 Chandelier", "",
             "Formal validation accessed: **NO**", "",
             f"Signals {len(signals)}; trades {cell['trade_stats']['trades']}; "
             f"CAGR {cell['summary']['cagr_pct']:.2f}%; "
             f"Sharpe {(adjusted.get('sharpe') or 0):.3f}; "
             f"PF {(cell['trade_stats'].get('profit_factor') or 0):.3f}; "
             f"MDD {cell['summary']['max_drawdown_pct']:.2f}%; "
             f"trim-5 expectancy {(cell['drop_top_5'].get('expectancy_pct') or 0):.2f}%.", "",
             f"Gate: **{'PASS' if gate['passed'] else 'FAIL'}**", ""]
    lines.extend(f"- {'PASS' if passed else 'FAIL'} — {name}"
                 for name, passed in gate["checks"].items())
    lines += ["", "Formal validation and untouched OOS remain sealed.", ""]
    md_path.write_text("\n".join(lines))
    if raw_cell["trades"]:
        pd.DataFrame(raw_cell["trades"]).to_csv(
            out / f"forward20_chandelier_{stamp}_holdout_trades.csv", index=False,
        )
    if raw_cell["equity_curve"]:
        pd.DataFrame(raw_cell["equity_curve"]).to_csv(
            out / f"forward20_chandelier_{stamp}_holdout_daily.csv", index=False,
        )
    print(json.dumps({"signals": len(signals), "summary": cell["summary"],
                      "trade_stats": cell["trade_stats"], "gate": gate,
                      "open_formal_validation": gate["passed"]}, indent=2))
    print(json_path); print(md_path)


if __name__ == "__main__":
    main()
