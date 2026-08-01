#!/usr/bin/env python3
"""Train gate for corrected-scale frozen-pivot limit-on-open entry."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from csv_client import CSVClient
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
import pivot_retest_experiment
from pivot_retest_experiment import compact, filter_detections, run_cell, slice_prices
from five_day_low_train_gate import assess

START, END = "2016-07-01", "2021-12-31"
TRIALS_DECLARED = 215


def main() -> None:
    pivot_retest_experiment.TRIALS_DECLARED = TRIALS_DECLARED
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--output-dir", default="backtests/pivot_open_limit_v2/results")
    ap.add_argument("--iterations", type=int, default=1000)
    args = ap.parse_args()
    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/benchmark gate failed")
    payload = json.loads(Path(args.backtest_json).read_text())
    detections, dropped = filter_detections(
        payload.get("detections_by_ticker") or {}, load_membership(args.membership_csv), START, END,
    )
    client = CSVClient(args.price_csv)
    prices = slice_prices({
        row["symbol"]: list(reversed(client.get_historical_prices(row["symbol"], days=100_000)["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]
    }, START, END)
    detection = compact(run_cell(
        detections, prices, entry_rule="detection_entry", iterations=args.iterations,
    ))
    pivot = compact(run_cell(
        detections, prices, entry_rule="pivot_retest", iterations=args.iterations,
    ))
    candidate = compact(run_cell(
        detections, prices, entry_rule="pivot_open_limit",
        pivot_open_window=60, iterations=args.iterations,
    ))
    gate = assess(candidate, detection, pivot)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "frozen_spec": "backtests/pivot_open_limit_v2/frozen_spec.md",
        "train_period": [START, END], "validation_accessed": False,
        "trials_declared": TRIALS_DECLARED, "coverage": coverage,
        "membership_drops": dropped,
        "baselines": {"detection_entry": detection, "pivot_retest": pivot},
        "candidate": candidate, "train_gate": gate,
    }
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = out / f"pivot_open_limit_train_{stamp}.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(gate, indent=2)); print(path)


if __name__ == "__main__":
    main()
