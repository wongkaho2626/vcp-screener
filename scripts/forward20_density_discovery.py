#!/usr/bin/env python3
"""Prespecified p70/p75/p80 density discovery for Trial 289-291."""

from __future__ import annotations

import argparse, json
from datetime import datetime
from pathlib import Path

from csv_client import CSVClient
from linear_timing_discovery import (
    CALIBRATION, CALIBRATION_PRICE_END, FIT, FIT_PRICE_END, HOLDOUT,
    build_rows, compact, evaluate, fit_ridge, signals_with_decay,
    threshold_from_rows,
)
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import filter_detections, slice_prices

PERCENTILES = (70, 75, 80)


def assess(cell: dict) -> dict:
    stats = cell["trade_stats"]
    adjusted = (cell.get("robustness") or {}).get("risk_adjusted") or {}
    checks = {
        "trades>=40": stats["trades"] >= 40,
        "cagr>=10pct": cell["summary"]["cagr_pct"] >= 10,
        "sharpe>=0.75": (adjusted.get("sharpe") or 0) >= .75,
        "pf>1.20": (stats.get("profit_factor") or 0) > 1.20,
        "mdd>-15pct": cell["summary"]["max_drawdown_pct"] > -15,
        "drop_top_5_expectancy>0": (cell["drop_top_5"].get("expectancy_pct") or 0) > 0,
    }
    return {"eligible": all(checks.values()), "checks": checks}


def select(cells: dict) -> dict:
    assessment = {name: assess(cell) for name, cell in cells.items()}
    eligible = [name for name, row in assessment.items() if row["eligible"]]
    if not eligible:
        return {"selected": None, "assessment": assessment}
    best = max(cells[name]["summary"]["cagr_pct"] for name in eligible)
    tied = [name for name in eligible if best - cells[name]["summary"]["cagr_pct"] <= .25]
    return {"selected": max(tied, key=lambda name: int(name[1:])), "assessment": assessment}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--output-dir", default="backtests/forward20_density_v2/results")
    ap.add_argument("--iterations", type=int, default=1000)
    args = ap.parse_args()
    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/benchmark gate failed")
    detections = json.loads(Path(args.backtest_json).read_text())["detections_by_ticker"]
    membership = load_membership(args.membership_csv)
    client = CSVClient(args.price_csv)
    prices_all = {
        row["symbol"]: list(reversed(client.get_historical_prices(row["symbol"], days=100_000)["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]
    }
    fit_dets, _ = filter_detections(detections, membership, *FIT)
    fit_rows = build_rows(
        fit_dets, slice_prices(prices_all, FIT[0], FIT_PRICE_END),
        with_labels=True, label_mode="forward20",
    )
    model = fit_ridge(fit_rows)
    cal_dets, _ = filter_detections(detections, membership, *CALIBRATION)
    cal_rows = build_rows(
        cal_dets, slice_prices(prices_all, CALIBRATION[0], CALIBRATION_PRICE_END),
        with_labels=False,
    )
    exit_threshold = threshold_from_rows(cal_rows, model, 50)
    discovery_dets, dropped = filter_detections(detections, membership, *HOLDOUT)
    prices = slice_prices(prices_all, *HOLDOUT)
    rows = build_rows(discovery_dets, prices, with_labels=False)
    cells, thresholds = {}, {}
    for percentile in PERCENTILES:
        threshold = threshold_from_rows(cal_rows, model, percentile)
        thresholds[f"p{percentile}"] = threshold
        signals = signals_with_decay(rows, model, threshold, exit_threshold)
        cells[f"p{percentile}"] = compact(evaluate(
            signals, prices, args.iterations, exit_rule="model_decay",
            trials_declared=291,
        ))
    selection = select(cells)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/forward20_density_v2/family_spec.md",
        "formal_validation_accessed": False, "untouched_oos_accessed": False,
        "period": HOLDOUT, "membership_drops": dropped, "coverage": coverage,
        "trials_before": 288, "new_cells": 3, "trials_after": 291,
        "model": model, "exit_threshold_p50": exit_threshold,
        "entry_thresholds": thresholds, "cells": cells, "selection": selection,
        "open_refit_freeze": selection["selected"] is not None,
    }
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    jp = out / f"forward20_density_{stamp}.json"
    mp = out / f"forward20_density_{stamp}.md"
    jp.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    lines = ["# Forward-20 Entry-Density Discovery", "", "Formal validation accessed: **NO**", "",
             "| Cell | Trades | CAGR | Sharpe | PF | Trim-5 expectancy | Eligible |", "|---|---:|---:|---:|---:|---:|---|"]
    for name, cell in cells.items():
        a = (cell.get("robustness") or {}).get("risk_adjusted") or {}
        ok = selection["assessment"][name]["eligible"]
        lines.append(f"| {name} | {cell['trade_stats']['trades']} | {cell['summary']['cagr_pct']:.2f}% | {(a.get('sharpe') or 0):.3f} | {(cell['trade_stats']['profit_factor'] or 0):.3f} | {(cell['drop_top_5']['expectancy_pct'] or 0):.2f}% | {'yes' if ok else 'no'} |")
    lines += ["", f"Selected: **{selection['selected'] or 'NONE'}**", "", "Untouched OOS remains sealed.", ""]
    mp.write_text("\n".join(lines))
    print(json.dumps({"selection": selection, "summaries": {k:v["summary"] for k,v in cells.items()}}, indent=2))
    print(jp); print(mp)


if __name__ == "__main__":
    main()
