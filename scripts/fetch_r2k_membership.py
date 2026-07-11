#!/usr/bin/env python3
"""Build point-in-time Russell 2000 membership intervals from historical
IWM (iShares Russell 2000 ETF) holdings snapshots.

Source: BlackRock's product-data document API, which serves the fund's
holdings CSV for a historical ``asOfDate`` (verified back to 2011-06-30):

    https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data
        /api/v1/get-fund-document?...&portfolioId=239710&asOfDate=YYYYMMDD
        &component=holdings

Quarterly snapshots are fetched (last business day of each quarter, walking
back from the calendar quarter-end until a valid CSV appears) and stitched
into ``ticker,start_date,end_date`` intervals compatible with
``membership.load_membership``. Interval edges are CONSERVATIVE for PIT
filtering: an interval starts at the first snapshot where the name appears
and ends at the last snapshot where it appears, so a name is never counted
as a member on a date we did not actually observe it (at the cost of up to
one quarter of true membership at each edge).

Usage:
    python3 scripts/fetch_r2k_membership.py                # -> scripts/data/r2k_membership.csv
    python3 scripts/fetch_r2k_membership.py --start-year 2012 --sleep-secs 2
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT_OUTPUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "r2k_membership.csv"
)
API_URL = (
    "https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data"
    "/api/v1/get-fund-document?appType=PRODUCT_PAGE&appSubType=ISHARES"
    "&targetSite=us-ishares&locale=en_US&portfolioId=239710"
    "&userType=individual&component=holdings&asOfDate={yyyymmdd}"
)
QUARTER_END_MONTH_DAY = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
MIN_VALID_TICKERS = 500  # a real R2K snapshot carries ~2,000 equity rows


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def parse_holdings_csv(text: str) -> list[str]:
    """Equity tickers from an iShares holdings CSV (preamble + table).
    Non-equity rows (cash, futures, money market) are dropped; '.' class
    suffixes are normalized to '-' (Yahoo form). HTML responses yield []."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith("Ticker,")), None)
    if start is None:
        return []
    out: list[str] = []
    for row in csv.reader(io.StringIO("\n".join(lines[start + 1 :]))):
        if len(row) < 4:
            continue
        sym = row[0].strip().upper().replace(".", "-")
        if not sym or sym in {"-", "--"} or row[3].strip() != "Equity":
            continue
        out.append(sym)
    return out


def build_intervals(
    snapshots: list[tuple[str, list[str]]],
) -> list[tuple[str, str, str]]:
    """Stitch (date, tickers) snapshots into (ticker, start, end) intervals.
    End = last snapshot date where present; '' = present in the final
    snapshot (still a member). Re-entries yield separate intervals."""
    open_start: dict[str, str] = {}
    last_seen: dict[str, str] = {}
    rows: list[tuple[str, str, str]] = []
    for snap_date, syms in snapshots:
        present = set(syms)
        for sym in present:
            if sym not in open_start:
                open_start[sym] = snap_date
            last_seen[sym] = snap_date
        for sym in sorted(set(open_start) - present):
            rows.append((sym, open_start.pop(sym), last_seen.pop(sym)))
    rows.extend((sym, start, "") for sym, start in sorted(open_start.items()))
    return rows


def quarter_end_candidates(year: int, quarter: int, max_back: int = 7) -> list[str]:
    """asOfDate candidates for a quarter: the calendar quarter-end and up to
    ``max_back - 1`` preceding days (YYYYMMDD, newest first)."""
    month, day = QUARTER_END_MONTH_DAY[quarter]
    end = date(year, month, day)
    return [(end - timedelta(days=k)).strftime("%Y%m%d") for k in range(max_back)]


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_snapshot(yyyymmdd: str, timeout: float = 30.0) -> list[str]:
    req = urllib.request.Request(
        API_URL.format(yyyymmdd=yyyymmdd),
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return parse_holdings_csv(resp.read().decode("utf-8-sig", errors="replace"))


def quarters(start_year: int, today: date) -> list[tuple[int, int]]:
    out = []
    for year in range(start_year, today.year + 1):
        for q in (1, 2, 3, 4):
            month, day = QUARTER_END_MONTH_DAY[q]
            if date(year, month, day) <= today:
                out.append((year, q))
    return out


def run(args: argparse.Namespace) -> None:
    snaps: list[tuple[str, list[str]]] = []
    todo = quarters(args.start_year, datetime.now().date())
    for year, q in todo:
        got = None
        for cand in quarter_end_candidates(year, q):
            try:
                syms = fetch_snapshot(cand)
            except Exception as err:  # noqa: BLE001 — log and try the prior day
                print(f"  {cand}: {err}")
                syms = []
            if len(syms) >= MIN_VALID_TICKERS:
                got = (f"{cand[:4]}-{cand[4:6]}-{cand[6:]}", syms)
                break
            time.sleep(args.sleep_secs)
        if got is None:
            print(f"WARN: no valid snapshot for {year}Q{q} — skipped")
        else:
            snaps.append(got)
            print(f"{year}Q{q}: {got[0]} — {len(got[1])} equity tickers")
        time.sleep(args.sleep_secs)

    if len(snaps) < 2:
        sys.exit("FATAL: fewer than 2 snapshots fetched; no intervals written")

    rows = build_intervals(snaps)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ticker", "start_date", "end_date"])
        writer.writerows(sorted(rows))
    print(f"\n{len(snaps)} snapshots -> {len(rows)} intervals -> {args.output}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Fetch quarterly IWM holdings and build R2K PIT membership")
    ap.add_argument("--output", default=DEFAULT_OUTPUT)
    ap.add_argument("--start-year", type=int, default=2011)
    ap.add_argument("--sleep-secs", type=float, default=1.0)
    run(ap.parse_args())


if __name__ == "__main__":
    main()
