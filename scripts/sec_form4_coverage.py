#!/usr/bin/env python3
"""Outcome-free Form 4 filing coverage on active PIT VCP setup rows."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from csv_client import CSVClient
from linear_timing_discovery import CALIBRATION, FIT, HOLDOUT, build_rows
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import filter_detections, slice_prices

PERIODS = {"fit": FIT, "calibration": CALIBRATION, "internal_holdout": HOLDOUT}


def filing_rows(payload: dict) -> list[dict]:
    columns = (payload.get("filings") or {}).get("recent") or payload
    if not isinstance(columns, dict):
        return []
    count = len(columns.get("accessionNumber") or [])
    return [{key: (values[i] if i < len(values) else None)
             for key, values in columns.items() if isinstance(values, list)}
            for i in range(count)]


def load_form4_events(symbol: str, submissions_dir: Path) -> list[dict]:
    main_path = submissions_dir / f"{symbol}.json"
    if not main_path.exists():
        return []
    main = json.loads(main_path.read_text())
    cik = str(main["cik"])
    payloads = [main]
    payloads.extend(json.loads(path.read_text()) for path in
                    (submissions_dir / "history").glob(f"{symbol}__*.json"))
    events = []
    for payload in payloads:
        for row in filing_rows(payload):
            if row.get("form") != "4" or not row.get("filingDate"):
                continue
            accession = row.get("accessionNumber") or ""
            primary = row.get("primaryDocument") or ""
            events.append({
                "symbol": symbol, "cik": cik, "filed": row["filingDate"],
                "accession": accession, "primary_document": primary,
                "url": (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                        f"{accession.replace('-', '')}/{primary}?output=1"),
            })
    return sorted(events, key=lambda event: (event["filed"], event["accession"]))


def latest_before(events: list[dict], signal_date: str) -> dict | None:
    eligible = [event for event in events if event["filed"] < signal_date]
    return max(eligible, key=lambda event: event["filed"]) if eligible else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("detections_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--submissions-dir", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--output-dir", default="backtests/sec_pit_audit")
    args = ap.parse_args()
    detections = json.loads(Path(args.detections_json).read_text())["detections_by_ticker"]
    membership = load_membership(args.membership_csv)
    client = CSVClient(args.price_csv)
    prices_all = {row["symbol"]: list(reversed(client.get_historical_prices(
        row["symbol"], days=100_000)["historical"])) for row in client.get_constituents()}
    submissions_dir = Path(args.submissions_dir)
    events = {symbol: load_form4_events(symbol, submissions_dir) for symbol in detections}
    summary = {}; candidates: dict[tuple[str, str], dict] = {}
    for period, dates in PERIODS.items():
        period_dets, drops = filter_detections(detections, membership, *dates)
        rows = build_rows(period_dets, slice_prices(prices_all, *dates), with_labels=False)
        setups = set(); qualifying_rows = 0
        for row in rows:
            signal_day = date.fromisoformat(row["signal_date"])
            window = [event for event in events.get(row["symbol"], [])
                      if 0 < (signal_day - date.fromisoformat(event["filed"])).days <= 30]
            if not window:
                continue
            setups.add(row["setup_id"]); qualifying_rows += 1
            for event in window:
                candidates[(event["symbol"], event["accession"])] = event
        summary[period] = {"active_rows": len(rows), "setups": len({r['setup_id'] for r in rows}),
                           "recent_form4_rows": qualifying_rows,
                           "recent_form4_setups": len(setups), "membership_drops": drops}
    report = {"generated_at": datetime.now().isoformat(timespec="seconds"),
              "outcomes_accessed": False, "strict_filed_before_signal": True,
              "window_days": 30, "periods": summary,
              "symbols_with_form4": sum(bool(value) for value in events.values()),
              "form4_filings": sum(len(value) for value in events.values()),
              "unique_candidate_filings": len(candidates)}
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    (out / "sec_form4_coverage.json").write_text(json.dumps(report, indent=2) + "\n")
    with (out / "sec_form4_candidate_filings.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("symbol", "cik", "filed", "accession",
                                                    "primary_document", "url"))
        writer.writeheader(); writer.writerows(sorted(candidates.values(),
                                                      key=lambda row: (row["filed"], row["symbol"])))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
