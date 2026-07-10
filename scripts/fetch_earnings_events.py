#!/usr/bin/env python3
"""Fetch and cache historical Yahoo earnings events for a backtest universe.

The output deliberately stores only event-time fields returned by Yahoo:
EPS estimate, reported EPS, and surprise. It does not backfill current analyst
recommendations into history.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yfinance as yf


FIELDS = ["symbol", "event_date", "eps_estimate", "reported_eps", "surprise_pct"]


def fetch_symbol(symbol: str, limit: int, attempts: int = 3) -> list[dict]:
    frame = None
    for attempt in range(attempts):
        try:
            frame = yf.Ticker(symbol).get_earnings_dates(limit=limit)
            break
        except Exception:
            if attempt + 1 == attempts:
                raise
            time.sleep(1.0 * (attempt + 1))
    if frame is None or frame.empty:
        return []
    rows = []
    for timestamp, row in frame.iterrows():
        estimate = row.get("EPS Estimate")
        reported = row.get("Reported EPS")
        surprise = row.get("Surprise(%)")
        if estimate != estimate or reported != reported or surprise != surprise:
            continue
        rows.append({
            "symbol": symbol,
            "event_date": timestamp.date().isoformat(),
            "eps_estimate": float(estimate),
            "reported_eps": float(reported),
            "surprise_pct": float(surprise),
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--retry-failures",
        help="Retry symbols listed in a prior failures JSON and merge into the existing output",
    )
    args = parser.parse_args()
    if args.limit < 1 or args.workers < 1:
        parser.error("--limit and --workers must be positive")

    payload = json.loads(Path(args.backtest_json).read_text())
    symbols = sorted((payload.get("detections_by_ticker") or {}).keys())
    output = Path(args.output)
    rows, failures = [], {}
    if args.retry_failures:
        symbols = sorted(json.loads(Path(args.retry_failures).read_text()).keys())
        if output.exists():
            with output.open(newline="") as handle:
                rows.extend(csv.DictReader(handle))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch_symbol, symbol, args.limit): symbol for symbol in symbols}
        for number, future in enumerate(as_completed(futures), 1):
            symbol = futures[future]
            try:
                rows.extend(future.result())
            except Exception as exc:  # keep partial cache usable and disclose failures
                failures[symbol] = str(exc)
            if number % 50 == 0 or number == len(symbols):
                print(f"completed {number}/{len(symbols)}; events={len(rows)}; failures={len(failures)}")

    rows.sort(key=lambda row: (row["symbol"], row["event_date"]))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    failure_path = output.with_suffix(".failures.json")
    failure_path.write_text(json.dumps(failures, indent=2, sort_keys=True))
    print(f"wrote {len(rows)} events to {output}")
    print(f"wrote {len(failures)} failures to {failure_path}")


if __name__ == "__main__":
    main()
