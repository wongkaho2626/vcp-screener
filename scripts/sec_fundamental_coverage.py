#!/usr/bin/env python3
"""Audit causal SEC growth-event coverage on PIT VCP detections (no outcomes)."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from membership import DEFAULT_MEMBERSHIP_CSV, is_member, load_membership
from sec_companyfacts import as_filed_growth_events, latest_event_before

PERIODS = {
    "fit": ("2016-07-01", "2018-06-30"),
    "calibration": ("2019-01-01", "2019-06-30"),
    "internal_holdout": ("2020-01-01", "2021-12-31"),
}
FIELDS = (
    "symbol", "signal_date", "period", "pit_member", "facts_cached",
    "event_available", "filed", "event_age_days", "fresh_120d", "form",
    "accession", "eps_growth", "revenue_growth", "revenue_tag",
)


def period_for(signal_date: str) -> str:
    for name, (start, end) in PERIODS.items():
        if start <= signal_date <= end:
            return name
    return "outside_experiment"


def pct(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 2) if denominator else 0.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("detections_json")
    ap.add_argument("--companyfacts-dir", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--output-dir", default="backtests/sec_pit_audit")
    args = ap.parse_args()

    detections = json.loads(Path(args.detections_json).read_text())["detections_by_ticker"]
    membership = load_membership(args.membership_csv)
    facts_dir = Path(args.companyfacts_dir)
    rows: list[dict] = []
    events_by_symbol: dict[str, list[dict]] = {}
    symbol_stats = Counter()
    invalid_files: list[str] = []
    for symbol, symbol_detections in detections.items():
        if not symbol_detections:
            continue
        facts_path = facts_dir / f"{symbol}.json"
        events: list[dict] = []
        if facts_path.exists():
            try:
                events = as_filed_growth_events(json.loads(facts_path.read_text()))
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                invalid_files.append(symbol)
        if events:
            events_by_symbol[symbol] = events
            symbol_stats["symbols_with_comparable_events"] += 1
            symbol_stats["comparable_events"] += len(events)
        symbol_stats["symbols_with_detections"] += 1
        for detection in symbol_detections:
            signal_date = detection["as_of_date"]
            pit = is_member(membership, symbol, signal_date)
            event = latest_event_before(events, signal_date) if pit else None
            age = ((date.fromisoformat(signal_date) - date.fromisoformat(event["filed"])).days
                   if event else None)
            row = {
                "symbol": symbol, "signal_date": signal_date,
                "period": period_for(signal_date), "pit_member": pit,
                "facts_cached": facts_path.exists(), "event_available": event is not None,
                "filed": event.get("filed") if event else None,
                "event_age_days": age, "fresh_120d": age is not None and age <= 120,
                "form": event.get("form") if event else None,
                "accession": event.get("accession") if event else None,
                "eps_growth": event.get("eps_growth") if event else None,
                "revenue_growth": event.get("revenue_growth") if event else None,
                "revenue_tag": event.get("revenue_tag") if event else None,
            }
            rows.append(row)

    summaries = {}
    for name in [*PERIODS, "all_2016_2021"]:
        selected = [row for row in rows if (
            row["period"] == name if name != "all_2016_2021"
            else "2016-01-01" <= row["signal_date"] <= "2021-12-31"
        )]
        pit_rows = [row for row in selected if row["pit_member"]]
        cached = [row for row in pit_rows if row["facts_cached"]]
        comparable = [row for row in pit_rows if row["event_available"]]
        fresh = [row for row in comparable if row["fresh_120d"]]
        summaries[name] = {
            "detections": len(selected), "pit_detections": len(pit_rows),
            "facts_cached": len(cached), "comparable_event": len(comparable),
            "fresh_120d": len(fresh),
            "facts_cache_coverage_pct": pct(len(cached), len(pit_rows)),
            "comparable_event_coverage_pct": pct(len(comparable), len(pit_rows)),
            "fresh_120d_coverage_pct": pct(len(fresh), len(pit_rows)),
            "dual_growth_eps20_rev10": sum(
                row["eps_growth"] >= .20 and row["revenue_growth"] >= .10
                for row in fresh
            ),
            "positive_eps10_nonnegative_revenue": sum(
                row["eps_growth"] >= .10 and row["revenue_growth"] >= 0
                for row in fresh
            ),
        }

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": "SEC Company Facts cached from data.sec.gov",
        "causality": "latest comparable 10-Q/10-K event with filed < signal_date",
        "same_accession_comparison": True, "freshness_days": 120,
        "outcomes_accessed": False, "formal_validation_accessed": False,
        "untouched_oos_accessed": False,
        "symbols": dict(symbol_stats), "invalid_files": invalid_files,
        "periods": summaries,
    }
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    (out / "sec_fundamental_coverage.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    (out / "sec_growth_events.json").write_text(
        json.dumps(events_by_symbol, separators=(",", ":"), allow_nan=False) + "\n"
    )
    with (out / "sec_fundamental_signals.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(rows)
    lines = [
        "# SEC Point-in-Time Fundamental Coverage", "",
        "Outcome data accessed: **NO**", "",
        "A filing is usable only when `filed < signal_date`. EPS and revenue YoY",
        "comparisons use current and prior-period facts presented in the same",
        "10-Q/10-K accession. Fresh means no more than 120 calendar days old.", "",
        "| Period | PIT detections | Facts cache | Comparable | Fresh 120d | EPS>=20% & Rev>=10% |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, cell in summaries.items():
        lines.append(
            f"| {name} | {cell['pit_detections']} | {cell['facts_cached']} "
            f"({cell['facts_cache_coverage_pct']:.2f}%) | {cell['comparable_event']} "
            f"({cell['comparable_event_coverage_pct']:.2f}%) | {cell['fresh_120d']} "
            f"({cell['fresh_120d_coverage_pct']:.2f}%) | "
            f"{cell['dual_growth_eps20_rev10']} |"
        )
    lines += ["", f"Invalid cached JSON files: **{len(invalid_files)}**", ""]
    (out / "sec_fundamental_coverage.md").write_text("\n".join(lines))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
