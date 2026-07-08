#!/usr/bin/env python3
"""Point-in-time S&P 500 membership lookups.

Backed by a CSV of membership intervals (``ticker,start_date,end_date``,
dates ``YYYY-MM-DD``, blank ``end_date`` = still a member), as published by
the fja05680/sp500 dataset. A ticker may have multiple disjoint intervals
(left and rejoined the index).

Used to (a) build a survivorship-aware backtest universe (every ticker that
was a member at any point in a date range) and (b) filter detections to those
made while the ticker was actually in the index.
"""

from __future__ import annotations

import csv
import os

DEFAULT_MEMBERSHIP_CSV = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "sp500_membership.csv"
)

# Far-future sentinel for open-ended memberships; ISO date strings compare
# correctly lexicographically so plain string comparison is safe throughout.
_OPEN_END = "9999-12-31"


def load_membership(csv_path: str = DEFAULT_MEMBERSHIP_CSV) -> dict[str, list[tuple[str, str]]]:
    """Load membership intervals: symbol -> [(start_date, end_date), ...].

    Symbols are normalized to Yahoo form ('.' -> '-'). Raises FileNotFoundError
    with a pointer to the fetch script if the snapshot is missing.
    """
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(
            f"Membership snapshot not found: {csv_path}. "
            "Run: python3 scripts/fetch_historical_members.py"
        )
    intervals: dict[str, list[tuple[str, str]]] = {}
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            sym = (row.get("ticker") or "").strip().upper().replace(".", "-")
            start = (row.get("start_date") or "").strip()
            end = (row.get("end_date") or "").strip() or _OPEN_END
            if not sym or not start:
                continue
            intervals = {**intervals, sym: [*intervals.get(sym, []), (start, end)]}
    return intervals


def is_member(
    intervals: dict[str, list[tuple[str, str]]], symbol: str, date: str
) -> bool:
    """True if ``symbol`` was an index member on ``date`` (YYYY-MM-DD)."""
    return any(start <= date <= end for start, end in intervals.get(symbol, []))


def union_members(
    intervals: dict[str, list[tuple[str, str]]], start_date: str, end_date: str
) -> list[str]:
    """All symbols whose membership overlaps [start_date, end_date], sorted."""
    return sorted(
        sym
        for sym, spans in intervals.items()
        if any(s <= end_date and e >= start_date for s, e in spans)
    )
