#!/usr/bin/env python3
"""CSV-backed price client — a drop-in replacement for ``YFClient`` that reads
daily OHLCV from a local CSV instead of hitting yfinance (no network, no rate
limits).

Expected CSV columns (header required):
    Ticker,Date,Open,High,Low,Close,Adj Close,Volume
with Date as ``YYYY-MM-DD`` and one row per ticker-day.

Two deliberate choices for multi-decade data:
- **Adjusted OHLC**: every bar's O/H/L is scaled by ``AdjClose/Close`` and its
  close set to Adj Close, so the series is split/dividend-continuous. Raw prices
  would put fake gaps at splits and wreck SMAs and contraction detection.
- **Synthetic benchmark**: the file carries constituents but no index, so a
  request for ``SPY`` returns an equal-weight index built from the constituents'
  daily returns — good enough for relative strength.

Caveat: a constituents-only file is **survivorship-biased** (delisted/removed
names are absent). Prefer a point-in-time universe when that matters.

Interface parity with ``YFClient`` (duck-typed): ``get_historical_prices``,
``get_constituents``, ``get_api_stats``.
"""

from __future__ import annotations

import collections
import csv
import sys
from typing import Optional

BENCHMARK_SYMBOL = "SPY"


def _adjust_bar(o: float, h: float, low: float, c: float, adj: float) -> tuple:
    """Scale OHLC by AdjClose/Close so the series is split-continuous."""
    factor = (adj / c) if c else 1.0
    return (round(o * factor, 4), round(h * factor, 4), round(low * factor, 4),
            round(adj, 4))


class CSVClient:
    """Reads a whole OHLCV CSV once, grouped by ticker, most-recent-first."""

    def __init__(self, csv_path: str) -> None:
        self._path = csv_path
        self.requests_made = 0
        # ticker -> ascending list of bar dicts
        raw: dict[str, list[dict]] = collections.defaultdict(list)
        # for the synthetic benchmark: date -> [sum of daily returns, count]
        ret_accum: dict[str, list[float]] = collections.defaultdict(lambda: [0.0, 0])
        prev_adj: dict[str, float] = {}

        with open(csv_path, newline="") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header or header[:2] != ["Ticker", "Date"]:
                raise ValueError(
                    f"{csv_path}: expected header 'Ticker,Date,Open,High,Low,"
                    f"Close,Adj Close,Volume', got {header}"
                )
            for row in reader:
                if len(row) < 8:
                    continue
                sym, date = row[0].strip().upper(), row[1].strip()
                try:
                    o, h, low = float(row[2]), float(row[3]), float(row[4])
                    c, adj, vol = float(row[5]), float(row[6]), int(float(row[7]))
                except ValueError:
                    continue
                ao, ah, al, ac = _adjust_bar(o, h, low, c, adj)
                raw[sym].append({"date": date, "open": ao, "high": ah, "low": al,
                                 "close": ac, "adjClose": ac, "volume": vol})
                pa = prev_adj.get(sym)
                if pa and pa > 0:
                    ret_accum[date][0] += adj / pa - 1
                    ret_accum[date][1] += 1
                prev_adj[sym] = adj

        # Store most-recent-first (pipeline assumes descending).
        self._bars: dict[str, list[dict]] = {
            sym: list(reversed(bars)) for sym, bars in raw.items()
        }
        self._bars[BENCHMARK_SYMBOL] = self._build_benchmark(ret_accum)

    def _build_benchmark(self, ret_accum: dict[str, list[float]]) -> list[dict]:
        """Equal-weight index from constituent daily returns, most-recent-first."""
        level = 100.0
        asc: list[dict] = []
        for date in sorted(ret_accum):
            s, n = ret_accum[date]
            if n > 0:
                level *= 1 + s / n
            lv = round(level, 4)
            asc.append({"date": date, "open": lv, "high": lv, "low": lv,
                        "close": lv, "adjClose": lv, "volume": 0})
        return list(reversed(asc))

    def get_historical_prices(self, symbol: str, days: int = 365) -> Optional[dict]:
        sym = (symbol or "").strip().upper()
        bars = self._bars.get(sym)
        if not bars:
            return None
        self.requests_made += 1
        return {"symbol": sym, "historical": bars[:days]}

    def get_constituents(self, index: str = "sp500") -> list[dict]:
        """All tickers in the CSV (the file defines the universe; ``index`` is
        ignored). Benchmark symbol excluded."""
        return [{"symbol": s} for s in sorted(self._bars) if s != BENCHMARK_SYMBOL]

    def get_api_stats(self) -> dict:
        return {
            "cache_entries": len(self._bars),
            "api_calls_made": self.requests_made,
            "rate_limit_reached": False,
            "data_source": f"csv:{self._path}",
        }


def main() -> None:
    """Quick self-check: python3 scripts/csv_client.py <csv> [TICKER]."""
    if len(sys.argv) < 2:
        print("usage: csv_client.py <csv_path> [ticker]", file=sys.stderr)
        sys.exit(1)
    client = CSVClient(sys.argv[1])
    tickers = client.get_constituents()
    print(f"Loaded {len(tickers)} tickers + synthetic {BENCHMARK_SYMBOL}")
    sym = sys.argv[2].upper() if len(sys.argv) > 2 else tickers[0]["symbol"]
    h = client.get_historical_prices(sym, days=5)
    print(f"{sym}: {len(client._bars.get(sym, []))} bars; latest 5:")
    for b in (h or {}).get("historical", []):
        print(" ", b)
    spy = client.get_historical_prices(BENCHMARK_SYMBOL, days=3)
    print(f"{BENCHMARK_SYMBOL} (synthetic EW) latest 3:")
    for b in (spy or {}).get("historical", []):
        print(" ", b)


if __name__ == "__main__":
    main()
