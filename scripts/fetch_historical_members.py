#!/usr/bin/env python3
"""Fetch point-in-time S&P 500 membership intervals (fja05680/sp500 dataset).

Downloads ``sp500_ticker_start_end.csv`` — one row per membership interval
(``ticker,start_date,end_date``; blank end = still a member) — and stores it
as ``scripts/data/sp500_membership.csv`` for use by ``membership.py`` and the
trade simulator.

Optionally emits a universe file (one ticker per line) containing every
symbol that was an S&P 500 member at any point in a date range — the
survivorship-aware input for ``backtest_vcp.py --universe-file``.

Usage:
    python3 scripts/fetch_historical_members.py
    python3 scripts/fetch_historical_members.py \
        --start 2016-07-08 --end 2026-07-08 --emit-universe backtests/universe_pit.txt
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from membership import DEFAULT_MEMBERSHIP_CSV, load_membership, union_members  # noqa: E402

SOURCE_URL = (
    "https://raw.githubusercontent.com/fja05680/sp500/master/sp500_ticker_start_end.csv"
)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch historical S&P 500 membership intervals"
    )
    parser.add_argument(
        "--output", default=DEFAULT_MEMBERSHIP_CSV, help="Where to store the CSV"
    )
    parser.add_argument("--start", help="Union range start (YYYY-MM-DD)")
    parser.add_argument("--end", help="Union range end (YYYY-MM-DD)")
    parser.add_argument(
        "--emit-universe",
        help="Write the union of members over [--start, --end] to this file "
        "(one ticker per line)",
    )
    args = parser.parse_args()
    if args.emit_universe and not (args.start and args.end):
        parser.error("--emit-universe requires --start and --end")
    for label, value in (("--start", args.start), ("--end", args.end)):
        if value and not _DATE_RE.match(value):
            parser.error(f"{label} must be YYYY-MM-DD")
    return args


def download_membership_csv(output_path: str) -> int:
    """Download the dataset, validate the header, write it. Returns row count."""
    print(f"Downloading {SOURCE_URL} ...", end=" ", flush=True)
    try:
        with urllib.request.urlopen(SOURCE_URL, timeout=60) as resp:
            text = resp.read().decode("utf-8")
    except Exception as e:  # noqa: BLE001
        print("FAILED")
        print(f"ERROR: download failed: {e}", file=sys.stderr)
        sys.exit(1)

    lines = text.strip().splitlines()
    if not lines or lines[0].strip() != "ticker,start_date,end_date":
        print("FAILED")
        print(
            f"ERROR: unexpected header {lines[0]!r} — dataset format changed?",
            file=sys.stderr,
        )
        sys.exit(1)
    if len(lines) < 500:
        print("FAILED")
        print(
            f"ERROR: only {len(lines)} rows — dataset looks truncated", file=sys.stderr
        )
        sys.exit(1)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(text if text.endswith("\n") else text + "\n")
    print(f"OK ({len(lines) - 1} intervals)")
    return len(lines) - 1


def main() -> None:
    args = parse_arguments()
    download_membership_csv(args.output)

    if args.emit_universe:
        intervals = load_membership(args.output)
        symbols = union_members(intervals, args.start, args.end)
        os.makedirs(os.path.dirname(args.emit_universe) or ".", exist_ok=True)
        with open(args.emit_universe, "w") as f:
            f.write(
                f"# S&P 500 point-in-time union {args.start} .. {args.end} "
                f"({len(symbols)} tickers)\n"
            )
            f.write("\n".join(symbols) + "\n")
        print(f"Universe file: {args.emit_universe} ({len(symbols)} tickers)")


if __name__ == "__main__":
    main()
