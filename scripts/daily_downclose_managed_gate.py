#!/usr/bin/env python3
"""Run frozen Trial 255 on daily causal detections."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from closing_low_lifecycle_gate import DISCOVERY, HOLDOUT, assess
from csv_client import CSVClient
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import compact, filter_detections, run_cell, slice_prices


def run(detections: dict, prices: dict, iterations: int) -> dict:
    return compact(run_cell(
        detections, prices, entry_rule="down_close_pivot_hold",
        down_close_window=10, exit_rule="followthrough_sma",
        followthrough_early_days=5, followthrough_min_gain_pct=2.0,
        followthrough_arm_gain_pct=8.0, followthrough_sma_period=20,
        iterations=iterations,
    ))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--output-dir", default="backtests/daily_downclose_managed_v2/results")
    ap.add_argument("--iterations", type=int, default=1000)
    args = ap.parse_args()
    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/benchmark gate failed")
    payload = json.loads(Path(args.backtest_json).read_text())
    detections = payload.get("detections_by_ticker") or {}
    membership = load_membership(args.membership_csv)
    client = CSVClient(args.price_csv)
    prices_all = {
        row["symbol"]: list(reversed(client.get_historical_prices(
            row["symbol"], days=100_000,
        )["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]
    }
    discovery_dets, discovery_drops = filter_detections(
        detections, membership, *DISCOVERY,
    )
    discovery_cell = run(
        discovery_dets, slice_prices(prices_all, *DISCOVERY), args.iterations,
    )
    discovery_gate = assess(discovery_cell)
    internal = None
    if discovery_gate["passed"]:
        holdout_dets, holdout_drops = filter_detections(
            detections, membership, *HOLDOUT,
        )
        holdout_cell = run(
            holdout_dets, slice_prices(prices_all, *HOLDOUT), args.iterations,
        )
        internal = {
            "period": HOLDOUT, "membership_drops": holdout_drops,
            "cell": holdout_cell, "gate": assess(holdout_cell, holdout=True),
        }
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "frozen_spec": "backtests/daily_downclose_managed_v2/frozen_spec.md",
        "formal_validation_accessed": False, "untouched_oos_accessed": False,
        "coverage": coverage, "trials_declared": 255,
        "discovery": {
            "period": DISCOVERY, "membership_drops": discovery_drops,
            "cell": discovery_cell, "gate": discovery_gate,
        },
        "internal_holdout": internal,
        "open_formal_validation": bool(internal and internal["gate"]["passed"]),
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = out / f"daily_downclose_managed_{stamp}.json"
    md_path = out / f"daily_downclose_managed_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    cell = discovery_cell
    adjusted = (cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = [
        "# Trial 255 — Daily Refreshed Pivot-Hold / Managed Winner Exit", "",
        f"Generated: {report['generated_at']}", "",
        "Formal validation accessed: **NO**", "",
        "## Discovery", "",
        f"Signals {cell['summary']['signals']}; trades {cell['trade_stats']['trades']}; "
        f"CAGR {cell['summary']['cagr_pct']:.2f}%; Sharpe {(adjusted.get('sharpe') or 0):.3f}; "
        f"PF {(cell['trade_stats']['profit_factor'] or 0):.3f}; "
        f"MDD {cell['summary']['max_drawdown_pct']:.2f}%; "
        f"trim-5 expectancy {(cell['drop_top_5']['expectancy_pct'] or 0):.2f}%.", "",
        f"Discovery gate: **{'PASS' if discovery_gate['passed'] else 'FAIL'}**", "",
    ]
    for check, passed in discovery_gate["checks"].items():
        lines.append(f"- {'PASS' if passed else 'FAIL'} — {check}")
    if internal:
        h = internal["cell"]
        ha = (h.get("robustness") or {}).get("risk_adjusted") or {}
        lines += [
            "", "## Internal holdout", "",
            f"Trades {h['trade_stats']['trades']}; CAGR {h['summary']['cagr_pct']:.2f}%; "
            f"Sharpe {(ha.get('sharpe') or 0):.3f}; PF {(h['trade_stats']['profit_factor'] or 0):.3f}.", "",
            f"Holdout gate: **{'PASS' if internal['gate']['passed'] else 'FAIL'}**", "",
        ]
    else:
        lines += ["", "Discovery failed; internal holdout remained unread.", ""]
    lines += ["Formal validation and untouched OOS remain sealed.", ""]
    md_path.write_text("\n".join(lines))
    print(json.dumps({
        "discovery_summary": discovery_cell["summary"],
        "discovery_gate": discovery_gate,
        "internal_holdout_opened": internal is not None,
        "open_formal_validation": report["open_formal_validation"],
    }, indent=2))
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
