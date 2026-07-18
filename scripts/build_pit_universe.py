#!/usr/bin/env python3
"""Assemble a delisted-inclusive point-in-time (PIT) price CSV.

Merges the survivors price CSV with recovered-delisted OHLCV files (long
format: Ticker,Date,Open,High,Low,Close,Adj Close,Volume) into one PIT CSV
restricted to tickers with S&P 500 membership overlapping the window
(``scripts/data/sp500_membership.csv``). Protections, in order:

1. Per membership interval, bars are trimmed to [start - 730d, end + 130d]
   (leading buffer for indicator lookback; trailing grace for exits) — this
   expels wrong-entity bars from reused tickers (new DELL/DOW/CEG...).
2. Same-entity rename aliases relabel a successor's rows to the historical
   ticker (e.g. ANTM <- ELV); the alias table is explicit and curated.
3. A scale-break screen drops any series with an adjacent-bar adjusted-close
   move beyond +/-150% (catches corrupt mixed-instrument series like
   TIE/CFC; spares genuine crisis bounces which top out near +100%).
4. Series with fewer than ``--min-inside`` bars inside membership-and-window
   are dropped (junk stubs).

Outputs the PIT CSV plus a coverage JSON (member-trading-day coverage,
per-year, per-ticker gaps). Coverage arithmetic treats the union of kept
bar dates as the trading calendar.

Usage:
    python3 scripts/build_pit_universe.py \
        --survivors-csv SP500_Historical_Data.csv \
        --recovered scratch/yf_recovered.csv scratch/yf_retry.csv \
        --out SP500_PIT_2006_2015.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from membership import DEFAULT_MEMBERSHIP_CSV, load_membership, union_members  # noqa: E402

LEAD_BUFFER_DAYS = 730
EXIT_GRACE_DAYS = 130
SIM_TAIL_DAYS = 366
SCALE_BREAK_RATIO = 1.5
EARLIEST_BAR = "1999-01-01"

# Same-entity renames: historical ticker <- successor ticker whose Yahoo/CSV
# series carries the continuous share line. Curated; do not add merger
# acquirers (e.g. CB is ACE Ltd, NOT old Chubb).
IN_CSV_ALIASES = {"ANTM": "ELV", "BLL": "BALL", "HRS": "LHX", "UTX": "RTX"}


def _shift(d: str, days: int) -> str:
    y, m, dd = map(int, d.split("-"))
    return str(date(y, m, dd) + timedelta(days=days))


def allowed_ranges(
    ticker: str, mem: dict[str, list[tuple[str, str]]],
    win_start: str, win_end: str,
) -> list[tuple[str, str]]:
    """Trimmed keep-ranges for a ticker's bars: one per membership interval
    overlapping the window, buffered for lookback and exit simulation."""
    sim_end = _shift(win_end, SIM_TAIL_DAYS)
    return [
        (_shift(s, -LEAD_BUFFER_DAYS),
         _shift(min(e, sim_end) if e < "9999" else sim_end, EXIT_GRACE_DAYS))
        for s, e in mem.get(ticker, [])
        if s <= win_end and e >= win_start
    ]


def in_ranges(d: str, rngs: list[tuple[str, str]]) -> bool:
    return any(a <= d <= b for a, b in rngs)


def find_scale_break(rows: list[list]) -> str | None:
    """First data-corruption signal in date-sorted rows, or None if clean."""
    prev = None
    for row in rows:
        try:
            adj = float(row[6])
        except (ValueError, IndexError):
            return "unparsable"
        if adj <= 0:
            return "nonpositive"
        if prev is not None and abs(adj / prev - 1) > SCALE_BREAK_RATIO:
            return f"scale-break@{row[1]}"
        prev = adj
    return None


def membership_windows(
    ticker: str, mem: dict[str, list[tuple[str, str]]],
    win_start: str, win_end: str,
) -> list[tuple[str, str]]:
    return [
        (max(s, win_start), min(e if e < "9999" else win_end, win_end))
        for s, e in mem.get(ticker, [])
        if s <= win_end and e >= win_start
    ]


def bars_inside_membership(
    ticker: str, rows: list[list], mem: dict[str, list[tuple[str, str]]],
    win_start: str, win_end: str,
) -> int:
    wins = membership_windows(ticker, mem, win_start, win_end)
    return sum(1 for row in rows if any(a <= row[1] <= b for a, b in wins))


def build(args: argparse.Namespace) -> None:
    mem = load_membership(args.membership_csv)
    uni = set(union_members(mem, args.win_start, args.win_end))
    bars: dict[str, list[list]] = {}

    def add_row(t: str, row: list) -> None:
        bars.setdefault(t, []).append(row)

    rev = {v: k for k, v in IN_CSV_ALIASES.items()}
    with open(args.survivors_csv, newline="") as f:
        r = csv.reader(f)
        next(r)
        for row in r:
            t = row[0]
            if t in uni:
                add_row(t, row)
            if t in rev:
                add_row(rev[t], [rev[t]] + row[1:])
    for path in args.recovered:
        with open(path, newline="") as f:
            r = csv.reader(f)
            next(r)
            for row in r:
                if row[0] in uni:
                    add_row(row[0], row)

    kept: dict[str, list[list]] = {}
    dropped: list[tuple[str, str]] = []
    for t, rows in bars.items():
        rngs = allowed_ranges(t, mem, args.win_start, args.win_end)
        if not rngs:
            dropped.append((t, "no-membership-in-window"))
            continue
        seen: dict[str, list] = {}
        for row in rows:
            if row[1] >= EARLIEST_BAR and in_ranges(row[1], rngs) and row[1] not in seen:
                seen[row[1]] = row
        rows2 = sorted(seen.values(), key=lambda r: r[1])
        flaw = find_scale_break(rows2)
        if flaw:
            dropped.append((t, flaw))
            continue
        inside = bars_inside_membership(t, rows2, mem, args.win_start, args.win_end)
        if inside < args.min_inside:
            dropped.append((t, f"only-{inside}-bars-in-membership"))
            continue
        kept[t] = rows2

    cal = sorted({row[1] for rows in kept.values() for row in rows
                  if args.win_start <= row[1] <= args.win_end})
    total_md = covered_md = 0
    per_year: dict[str, list[int]] = {}
    for t in uni:
        have = {row[1] for row in kept.get(t, [])}
        for a, b in membership_windows(t, mem, args.win_start, args.win_end):
            for d in cal:
                if a <= d <= b:
                    total_md += 1
                    py = per_year.setdefault(d[:4], [0, 0])
                    py[0] += 1
                    if d in have:
                        covered_md += 1
                        py[1] += 1
    cov = covered_md / total_md * 100 if total_md else 0.0

    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Ticker", "Date", "Open", "High", "Low", "Close",
                    "Adj Close", "Volume"])
        for t in sorted(kept):
            for row in kept[t]:
                w.writerow(row)
    coverage = {
        "universe": len(uni),
        "kept": len(kept),
        "coverage_pct": round(cov, 2),
        "per_year": {y: round(c / n * 100, 1) for y, (n, c) in sorted(per_year.items())},
        "dropped": dropped,
    }
    with open(args.coverage_json, "w") as f:
        json.dump(coverage, f, indent=1)
    print(f"kept={len(kept)} coverage={cov:.2f}% -> {args.out}")
    print(f"coverage detail -> {args.coverage_json}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--survivors-csv", required=True)
    ap.add_argument("--recovered", nargs="*", default=[],
                    help="Recovered-delisted long-format CSV file(s)")
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--win-start", default="2006-01-01")
    ap.add_argument("--win-end", default="2015-12-31")
    ap.add_argument("--min-inside", type=int, default=100)
    ap.add_argument("--out", required=True)
    ap.add_argument("--coverage-json", default="backtests/pullback_oos/pit/coverage.json")
    build(ap.parse_args())


if __name__ == "__main__":
    main()
