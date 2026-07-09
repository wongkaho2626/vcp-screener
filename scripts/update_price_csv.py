#!/usr/bin/env python3
"""Append recent bars to a local OHLCV CSV using yfinance (bulk download).

Reads an existing ``Ticker,Date,Open,High,Low,Close,Adj Close,Volume`` CSV,
finds each ticker's last date, bulk-downloads only the missing tail from
yfinance, and appends the new rows in the same format. Idempotent: only rows
strictly newer than a ticker's existing last date are written.

Bulk ``yf.download`` (one request per batch of tickers) is used rather than
per-ticker calls to minimise rate-limit exposure.

Usage:
    python3 scripts/update_price_csv.py SP500_Historical_Data.csv
    python3 scripts/update_price_csv.py SP500_Historical_Data.csv \
        --batch-size 60 --sleep-secs 1.0
"""

from __future__ import annotations

import argparse
import collections
import csv
import sys
import time
from datetime import date, datetime, timedelta

import yfinance as yf

COLUMNS = ["Ticker", "Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"]


def parse_arguments() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Append recent bars to an OHLCV CSV")
    ap.add_argument("csv_path", help="Existing OHLCV CSV to extend in place")
    ap.add_argument("--end", help="End date YYYY-MM-DD (default: today)")
    ap.add_argument("--batch-size", type=int, default=60, help="Tickers per bulk request")
    ap.add_argument("--sleep-secs", type=float, default=1.0, help="Pause between batches")
    return ap.parse_args()


def read_last_dates(csv_path: str) -> dict[str, str]:
    """Map ticker -> its latest date string in the CSV. One streaming pass."""
    last: dict[str, str] = {}
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header or header[:2] != ["Ticker", "Date"]:
            print(f"ERROR: unexpected header {header}", file=sys.stderr)
            sys.exit(1)
        for row in reader:
            if len(row) < 2:
                continue
            sym, d = row[0].strip().upper(), row[1].strip()
            if d > last.get(sym, ""):
                last[sym] = d
    return last


def _fmt_rows(sym: str, frame, after: str) -> list[list]:
    """Frame (yfinance, oldest-first) -> CSV rows with date > ``after``."""
    rows = []
    for ts, row in frame.iterrows():
        d = ts.strftime("%Y-%m-%d")
        if d <= after:
            continue
        close = row.get("Close")
        adj = row.get("Adj Close", close)
        if close is None or close != close:  # NaN guard
            continue
        rows.append([
            sym, d,
            round(float(row.get("Open")), 4), round(float(row.get("High")), 4),
            round(float(row.get("Low")), 4), round(float(close), 4),
            round(float(adj), 4), int(row.get("Volume") or 0),
        ])
    return rows


def fetch_batch(symbols: list[str], start: str, end: str) -> dict:
    """Bulk-download a batch; return {symbol: DataFrame}. Empty on failure."""
    try:
        df = yf.download(symbols, start=start, end=end, auto_adjust=False,
                         actions=False, group_by="ticker", threads=True,
                         progress=False)
    except Exception as e:  # noqa: BLE001 — one bad batch must not kill the run
        print(f"  batch error: {e}", file=sys.stderr)
        return {}
    if df is None or df.empty:
        return {}
    out = {}
    for sym in symbols:
        try:
            sub = df[sym] if len(symbols) > 1 else df
            sub = sub.dropna(how="all")
            if not sub.empty:
                out[sym] = sub
        except (KeyError, TypeError):
            continue
    return out


def run(args: argparse.Namespace) -> None:
    end = args.end or (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    last_dates = read_last_dates(args.csv_path)
    if not last_dates:
        print("ERROR: no tickers found in CSV", file=sys.stderr)
        sys.exit(1)
    earliest = min(last_dates.values())
    start = (datetime.strptime(earliest, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    symbols = sorted(last_dates)
    print(f"CSV: {args.csv_path} | {len(symbols)} tickers | last date {max(last_dates.values())}")
    print(f"Fetching {start} → {end} in batches of {args.batch_size} ...")

    new_rows: list[list] = []
    per_ticker = collections.Counter()
    failed: list[str] = []
    for i in range(0, len(symbols), args.batch_size):
        batch = symbols[i:i + args.batch_size]
        frames = fetch_batch(batch, start, end)
        got = 0
        for sym in batch:
            frame = frames.get(sym)
            if frame is None:
                failed.append(sym)
                continue
            rows = _fmt_rows(sym, frame, last_dates[sym])
            if rows:
                new_rows.extend(rows)
                per_ticker[sym] = len(rows)
                got += len(rows)
        print(f"  [{i + len(batch)}/{len(symbols)}] +{got} rows "
              f"({sum(per_ticker.values())} total)")
        if args.sleep_secs > 0 and i + args.batch_size < len(symbols):
            time.sleep(args.sleep_secs)

    if not new_rows:
        print("\nNo new rows fetched (already up to date, or all requests failed).")
        if failed:
            print(f"Tickers with no data: {len(failed)} (e.g. {failed[:8]})")
        return

    new_rows.sort(key=lambda r: (r[0], r[1]))
    with open(args.csv_path, "a", newline="") as f:
        csv.writer(f).writerows(new_rows)

    latest = max(r[1] for r in new_rows)
    print(f"\nAppended {len(new_rows)} rows across {len(per_ticker)} tickers "
          f"(new latest date {latest}).")
    if failed:
        print(f"No new data for {len(failed)} tickers (e.g. {failed[:8]}).")


def main() -> None:
    run(parse_arguments())


if __name__ == "__main__":
    main()
