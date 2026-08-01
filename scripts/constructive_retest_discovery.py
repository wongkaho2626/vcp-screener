#!/usr/bin/env python3
"""Train-only selector for the prespecified constructive-retest family."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from csv_client import CSVClient
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import compact, filter_detections, run_cell, slice_prices

TRAIN_START = "2016-07-01"
TRAIN_END = "2021-12-31"
TRIALS = 202
VARIANTS = (
    "baseline",
    "breakout_no_gap_1pct",
    "bullish_retest",
    "strong_close_clv60",
    "retest_high_confirm3",
)


def eligible(cell: dict, baseline_sharpe: float | None) -> tuple[bool, list[str]]:
    summary = cell["summary"]
    stats = cell["trade_stats"]
    trim = cell["drop_top_5"]
    sharpe = (cell["robustness"] or {}).get("risk_adjusted", {}).get("sharpe")
    checks = {
        "trades>=25": stats["trades"] >= 25,
        "cagr>0": summary["cagr_pct"] > 0,
        "sharpe>baseline": (
            sharpe is not None and baseline_sharpe is not None and sharpe > baseline_sharpe
        ),
        "pf>1.2": (stats.get("profit_factor") or 0) > 1.2,
        "drop_top_5_expectancy>0": (trim.get("expectancy_pct") or 0) > 0,
    }
    return all(checks.values()), [name for name, passed in checks.items() if not passed]


def select(cells: dict) -> dict:
    baseline_sharpe = cells["baseline"]["robustness"]["risk_adjusted"]["sharpe"]
    assessed = {}
    candidates = []
    for order, name in enumerate(VARIANTS[1:], 1):
        ok, failed = eligible(cells[name], baseline_sharpe)
        sharpe = cells[name]["robustness"]["risk_adjusted"]["sharpe"]
        assessed[name] = {"eligible": ok, "failed": failed, "sharpe": sharpe, "order": order}
        if ok:
            candidates.append((name, sharpe, order))
    if not candidates:
        return {"selected": None, "assessment": assessed, "open_validation": False}
    candidates.sort(key=lambda row: (-row[1], row[2]))
    best = candidates[0]
    # A Sharpe tie within .05 resolves to simpler numbered order.
    tied = [row for row in candidates if best[1] - row[1] <= .05]
    selected = min(tied, key=lambda row: row[2])[0]
    return {"selected": selected, "assessment": assessed, "open_validation": True}


def markdown(report: dict) -> str:
    lines = [
        "# Constructive Pivot-Retest — Train-Only Discovery Report", "",
        f"Generated: {report['generated_at']}", "",
        "Validation data inspected by selector: **NO**", "",
        "| Variant | Trades | CAGR | Sharpe | PF | Drop-top-5 expectancy | Eligible |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for name in VARIANTS:
        c = report["cells"][name]
        assessment = report["selection"]["assessment"].get(name)
        flag = "baseline" if assessment is None else ("yes" if assessment["eligible"] else "no")
        lines.append(
            f"| {name} | {c['trade_stats']['trades']} | {c['summary']['cagr_pct']:.2f}% | "
            f"{c['robustness']['risk_adjusted']['sharpe']:.3f} | "
            f"{(c['trade_stats']['profit_factor'] or 0):.3f} | "
            f"{(c['drop_top_5']['expectancy_pct'] or 0):.2f}% | {flag} |"
        )
    sel = report["selection"]["selected"]
    lines += ["", "## Selection", ""]
    if sel:
        lines.append(f"Selected and eligible for a separately frozen validation: **{sel}**.")
    else:
        lines.append("No non-baseline cell passed every prespecified gate. Family closes; validation remains unread.")
    for name, row in report["selection"]["assessment"].items():
        lines.append(f"- {name}: " + ("PASS" if row["eligible"] else "FAIL — " + ", ".join(row["failed"])))
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--output-dir", default="backtests/constructive_retest_discovery/results")
    ap.add_argument("--iterations", type=int, default=1000)
    args = ap.parse_args()

    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/benchmark gate failed")
    payload = json.loads(Path(args.backtest_json).read_text())
    membership = load_membership(args.membership_csv)
    detections, dropped = filter_detections(
        payload.get("detections_by_ticker") or {}, membership, TRAIN_START, TRAIN_END,
    )
    client = CSVClient(args.price_csv)
    prices_all = {
        row["symbol"]: list(reversed(client.get_historical_prices(row["symbol"], days=100_000)["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]
    }
    prices = slice_prices(prices_all, TRAIN_START, TRAIN_END)
    cells = {
        name: compact(run_cell(
            detections, prices, entry_rule="pivot_retest", pivot_mode=name,
            iterations=args.iterations,
        ))
        for name in VARIANTS
    }
    selection = select(cells)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/constructive_retest_discovery/family_spec.md",
        "train_period": [TRAIN_START, TRAIN_END],
        "validation_accessed": False,
        "coverage": coverage,
        "membership_drops": dropped,
        "trials_declared_after_family": TRIALS,
        "cells": cells,
        "selection": selection,
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = out / f"constructive_retest_discovery_{stamp}.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    md = out / f"constructive_retest_discovery_{stamp}.md"
    md.write_text(markdown(report))
    print(json.dumps(selection, indent=2))
    print(path)
    print(md)


if __name__ == "__main__":
    main()
