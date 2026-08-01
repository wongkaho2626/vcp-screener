#!/usr/bin/env python3
"""Train-only gate for the frozen first post-breakout down-close entry."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from csv_client import CSVClient
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
import pivot_retest_experiment
from pivot_retest_experiment import compact, filter_detections, run_cell, slice_prices

START, END = "2016-07-01", "2021-12-31"
TRIALS_DECLARED = 205


def assess(candidate: dict, baseline: dict) -> dict:
    c_sr = candidate["robustness"]["risk_adjusted"]["sharpe"]
    b_sr = baseline["robustness"]["risk_adjusted"]["sharpe"]
    checks = {
        "trades>=30": candidate["trade_stats"]["trades"] >= 30,
        "cagr>baseline": candidate["summary"]["cagr_pct"] > baseline["summary"]["cagr_pct"],
        "sharpe>baseline": c_sr is not None and b_sr is not None and c_sr > b_sr,
        "pf>1.2": (candidate["trade_stats"].get("profit_factor") or 0) > 1.2,
        "drop_top_5_expectancy>0": (candidate["drop_top_5"].get("expectancy_pct") or 0) > 0,
    }
    passed = all(checks.values())
    return {"checks": checks, "pass": passed, "open_validation": passed}


def main() -> None:
    pivot_retest_experiment.TRIALS_DECLARED = TRIALS_DECLARED
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--output-dir", default="backtests/first_down_close_v2/results")
    ap.add_argument("--iterations", type=int, default=1000)
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
    baseline = compact(run_cell(
        detections, prices, entry_rule="pivot_retest",
        iterations=args.iterations,
    ))
    candidate = compact(run_cell(
        detections, prices, entry_rule="first_down_close",
        down_close_window=10, iterations=args.iterations,
    ))
    gate = assess(candidate, baseline)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "frozen_spec": "backtests/first_down_close_v2/frozen_spec.md",
        "train_period": [START, END], "validation_accessed": False,
        "trials_declared": TRIALS_DECLARED,
        "coverage": coverage, "membership_drops": dropped,
        "baseline": baseline, "candidate": candidate, "train_gate": gate,
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = out / f"first_down_close_train_{stamp}.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(gate, indent=2))
    print(path)


if __name__ == "__main__":
    main()
