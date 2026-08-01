#!/usr/bin/env python3
"""Parse SEC Form 4 open-market purchases and audit PIT VCP coverage."""

from __future__ import annotations

import argparse
import csv
import json
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from csv_client import CSVClient
from linear_timing_discovery import CALIBRATION, FIT, HOLDOUT, build_rows
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import filter_detections, slice_prices

PERIODS = {"fit": FIT, "calibration": CALIBRATION, "internal_holdout": HOLDOUT}


def _name(element: ET.Element) -> str:
    return element.tag.split("}")[-1]


def _value(transaction: ET.Element, tag: str) -> str:
    for element in transaction.iter():
        if _name(element) != tag:
            continue
        nested = next((child for child in element.iter() if _name(child) == "value"), None)
        return ((nested.text if nested is not None else element.text) or "").strip()
    return ""


def open_market_purchases(path: Path) -> list[dict]:
    """Non-derivative code P, acquired A transactions from one ownership XML."""
    root = ET.parse(path).getroot()
    purchases = []
    for transaction in root.iter():
        if _name(transaction) != "nonDerivativeTransaction":
            continue
        if (_value(transaction, "transactionCode") != "P"
                or _value(transaction, "transactionAcquiredDisposedCode") != "A"):
            continue
        shares = _value(transaction, "transactionShares")
        price = _value(transaction, "transactionPricePerShare")
        purchases.append({"shares": shares, "price": price})
    return purchases


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("detections_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--candidates-csv", required=True)
    ap.add_argument("--documents-dir", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--output-dir", default="backtests/sec_pit_audit")
    args = ap.parse_args()
    candidates = list(csv.DictReader(Path(args.candidates_csv).open()))
    documents = Path(args.documents_dir)
    purchase_events: dict[str, list[dict]] = {}
    parsed = invalid = missing = transactions = 0
    purchase_rows = []
    for row in candidates:
        path = documents / f"{row['symbol']}__{row['accession']}.xml"
        if not path.exists():
            missing += 1
            continue
        try:
            purchases = open_market_purchases(path)
            parsed += 1
        except (ET.ParseError, OSError, ValueError):
            invalid += 1
            continue
        if not purchases:
            continue
        transactions += len(purchases)
        dollar_value = 0.0
        for purchase in purchases:
            try:
                dollar_value += float(purchase["shares"]) * float(purchase["price"])
            except (TypeError, ValueError):
                pass
        event = {key: row[key] for key in ("symbol", "cik", "filed", "accession")}
        event.update({"transactions": len(purchases), "reported_dollar_value": dollar_value})
        purchase_events.setdefault(row["symbol"], []).append(event)
        purchase_rows.append(event)
    for events in purchase_events.values():
        events.sort(key=lambda event: (event["filed"], event["accession"]))

    detections = json.loads(Path(args.detections_json).read_text())["detections_by_ticker"]
    membership = load_membership(args.membership_csv)
    client = CSVClient(args.price_csv)
    prices_all = {row["symbol"]: list(reversed(client.get_historical_prices(
        row["symbol"], days=100_000)["historical"])) for row in client.get_constituents()}
    summaries = {}
    for name, dates in PERIODS.items():
        period_dets, drops = filter_detections(detections, membership, *dates)
        rows = build_rows(period_dets, slice_prices(prices_all, *dates), with_labels=False)
        setups = set(); used_events = set(); qualifying_rows = 0
        for row in rows:
            signal_day = date.fromisoformat(row["signal_date"])
            window = [event for event in purchase_events.get(row["symbol"], [])
                      if 0 < (signal_day - date.fromisoformat(event["filed"])).days <= 30]
            if not window:
                continue
            setups.add(row["setup_id"]); qualifying_rows += 1
            used_events.update((event["symbol"], event["accession"]) for event in window)
        summaries[name] = {"active_rows": len(rows),
                           "active_setups": len({row['setup_id'] for row in rows}),
                           "purchase_window_rows": qualifying_rows,
                           "purchase_window_setups": len(setups),
                           "independent_purchase_filings": len(used_events),
                           "membership_drops": drops}
    report = {"generated_at": datetime.now().isoformat(timespec="seconds"),
              "outcomes_accessed": False, "window_days": 30,
              "strict_filed_before_signal": True,
              "transaction_definition": "nonDerivative transactionCode=P and A/D=A",
              "documents": {"candidates": len(candidates), "parsed": parsed,
                            "missing": missing, "invalid": invalid},
              "purchases": {"filings": len(purchase_rows), "transactions": transactions,
                            "symbols": len(purchase_events),
                            "filings_by_year": dict(sorted(Counter(
                                row["filed"][:4] for row in purchase_rows).items()))},
              "periods": summaries}
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    (out / "sec_form4_purchase_coverage.json").write_text(json.dumps(report, indent=2) + "\n")
    with (out / "sec_form4_purchases.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("symbol", "cik", "filed", "accession",
                                                    "transactions", "reported_dollar_value"))
        writer.writeheader(); writer.writerows(sorted(purchase_rows,
                                                      key=lambda row: (row["filed"], row["symbol"])))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
