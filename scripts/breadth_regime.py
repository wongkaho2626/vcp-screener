#!/usr/bin/env python3
"""S&P 500 breadth-regime lookups for the VCP backtest.

Backed by ``sp500_breadth_daily.csv`` (columns ``Date,breadth,source``; dates
``MM/DD/YYYY``; ``breadth`` = % of S&P 500 stocks above their 200-day MA),
copied from the spy500_history project. Daily, continuous 2002+.

Used to attach a market-breadth reading to each VCP trade's entry date and to
filter/segment trades by market regime. All functions are pure.
"""

from __future__ import annotations

import csv
import os
from bisect import bisect_right

DEFAULT_BREADTH_CSV = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "sp500_breadth_daily.csv"
)


def _to_iso(mmddyyyy: str) -> str:
    """Convert 'MM/DD/YYYY' -> 'YYYY-MM-DD' so dates sort/compare as strings."""
    m, d, y = mmddyyyy.strip().split("/")
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def load_breadth(csv_path: str = DEFAULT_BREADTH_CSV) -> list[tuple[str, float]]:
    """Load breadth as a date-sorted list of (iso_date, breadth_pct) tuples.

    Raises FileNotFoundError with a pointer if the snapshot is missing.
    """
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(
            f"Breadth snapshot not found: {csv_path}. "
            "Copy breadth_daily.csv from the spy500_history project."
        )
    series: list[tuple[str, float]] = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            raw_date = (row.get("Date") or "").strip()
            raw_val = (row.get("breadth") or "").strip()
            if not raw_date or not raw_val:
                continue
            try:
                series.append((_to_iso(raw_date), float(raw_val)))
            except ValueError:
                continue
    return sorted(series, key=lambda t: t[0])


def breadth_on_date(series: list[tuple[str, float]], date: str) -> float | None:
    """As-of breadth for an ISO date: the most recent reading on or before it.

    Weekend/holiday entry dates resolve to the last trading day (ffill). Returns
    None when the date precedes the series start.
    """
    dates = [d for d, _ in series]
    idx = bisect_right(dates, date) - 1
    return series[idx][1] if idx >= 0 else None


def breadth_change(
    series: list[tuple[str, float]], date: str, lookback: int = 20
) -> float | None:
    """Change in breadth (pts) vs `lookback` rows earlier (as-of `date`).

    Positive = participation expanding. None if not enough history.
    """
    dates = [d for d, _ in series]
    idx = bisect_right(dates, date) - 1
    if idx < lookback:
        return None
    return series[idx][1] - series[idx - lookback][1]
