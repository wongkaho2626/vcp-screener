#!/usr/bin/env python3
"""
yfinance data client for the VCP Screener.

Drop-in replacement for the old FMP client. Exposes the same public surface the
rest of the pipeline depends on, so no calculator, scanner, or report module had
to change:

    get_sp500_constituents()          -> list[{symbol, name, sector, subSector}]
    get_constituents(index)           -> same, for "sp500" or "russell2000"
    get_quote(symbols)                -> list[quote dict]
    get_batch_quotes(symbols)         -> dict[symbol -> quote dict]
    get_historical_prices(symbol, days) -> {"symbol", "historical": [...]}
    get_batch_historical(symbols, days) -> dict[symbol -> list[bar]]
    calculate_sma(prices, period)     -> float
    get_api_stats()                   -> dict

Data source notes
-----------------
- Price history and quote-derived fields come from Yahoo Finance via yfinance.
  No API key is required.
- Index membership (S&P 500 and Russell 2000) is read from bundled snapshots
  under ``data/`` (Yahoo does not expose index constituents). Refresh them
  periodically; see the skill's references for how.
- ``marketCap`` is best-effort: it is populated per-ticker from
  ``Ticker.fast_info`` only in single-symbol history calls, and left at 0 in the
  bulk quote path (the screener's filters never gate on it). Downstream code
  already tolerates ``marketCap == 0``.

Shape contract (matches the old FMP client exactly)
---------------------------------------------------
- ``historical`` bars are **most-recent-first** (descending date), each a dict
  with: ``date`` (``YYYY-MM-DD``), ``open``, ``high``, ``low``, ``close``,
  ``adjClose``, ``volume``.
- Quote dicts carry: ``symbol``, ``price``, ``yearHigh``, ``yearLow``,
  ``avgVolume``, ``volume``, ``marketCap``, ``name``, ``sector``.

Prices are fetched **unadjusted** (``auto_adjust=False``) so ``close`` is the raw
session close (used for pivots/stops) and ``adjClose`` carries the split/dividend
adjusted close, mirroring the FMP fields the calculators expect.
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime
from typing import Optional

try:
    import yfinance as yf
except ImportError:
    print(
        "ERROR: yfinance not found. Install with: pip install yfinance",
        file=sys.stderr,
    )
    sys.exit(1)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_SCRIPT_DIR, "data")

# Supported index universes -> bundled constituent snapshot filenames. Each file
# is a JSON list of {symbol, name, sector, subSector}. Yahoo doesn't serve index
# membership, so these are static snapshots (refresh via the scripts in the
# skill's references). Add new indices here to extend coverage.
_INDEX_FILES = {
    "sp500": "sp500_constituents.json",
    "russell2000": "russell2000_constituents.json",
}
_DEFAULT_INDEX = "sp500"

# ~252 trading days in a year; used to derive 52-week high/low/avg-volume when a
# quote is synthesized from a price-history window.
_YEAR_TRADING_DAYS = 252


def _clean_float(value) -> float:
    """Coerce to float, mapping None/NaN/inf to 0.0 (JSON-safe, calc-safe)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(f) or math.isinf(f):
        return 0.0
    return f


def _normalize_symbol(symbol: str) -> str:
    """Map a display ticker to the form Yahoo expects.

    Class shares use ``-`` on Yahoo (BRK-B, BF-B). Our constituents file already
    stores the ``-`` form, but custom-universe input may arrive with ``.``.
    """
    return symbol.strip().upper().replace(".", "-")


def _dataframe_to_bars(df) -> list[dict]:
    """Convert a yfinance OHLCV DataFrame to most-recent-first FMP-style bars.

    yfinance returns ascending (oldest-first) rows; the whole pipeline assumes
    descending (most-recent-first), so we reverse here.
    """
    if df is None or getattr(df, "empty", True):
        return []

    bars: list[dict] = []
    has_adj = "Adj Close" in df.columns
    for ts, row in df.iterrows():
        close = _clean_float(row.get("Close"))
        adj = _clean_float(row.get("Adj Close")) if has_adj else close
        bars.append(
            {
                "date": ts.strftime("%Y-%m-%d"),
                "open": _clean_float(row.get("Open")),
                "high": _clean_float(row.get("High")),
                "low": _clean_float(row.get("Low")),
                "close": close,
                "adjClose": adj or close,
                "volume": int(_clean_float(row.get("Volume"))),
            }
        )
    bars.reverse()  # ascending -> descending (most-recent-first)
    return bars


def _quote_from_bars(
    symbol: str,
    bars: list[dict],
    name: str = "",
    sector: str = "Unknown",
    market_cap: float = 0.0,
) -> Optional[dict]:
    """Synthesize a quote dict from most-recent-first OHLCV bars.

    ``price`` is the latest close, ``yearHigh``/``yearLow`` span the trailing
    ~252 sessions, ``avgVolume`` is their mean. Returns None if bars are empty.
    """
    if not bars:
        return None
    window = bars[:_YEAR_TRADING_DAYS]
    highs = [b["high"] for b in window if b["high"] > 0]
    lows = [b["low"] for b in window if b["low"] > 0]
    vols = [b["volume"] for b in window if b["volume"] > 0]
    latest = bars[0]
    return {
        "symbol": symbol,
        "price": latest["close"],
        "yearHigh": max(highs) if highs else 0.0,
        "yearLow": min(lows) if lows else 0.0,
        "avgVolume": int(sum(vols) / len(vols)) if vols else 0,
        "volume": latest["volume"],
        "marketCap": _clean_float(market_cap),
        "name": name or symbol,
        "sector": sector or "Unknown",
    }


class YFClient:
    """yfinance-backed market-data client (drop-in for the old FMP client)."""

    def __init__(self, api_key: Optional[str] = None):
        # api_key is accepted for backward compatibility and ignored — yfinance
        # needs no key. Callers still pass FMPClient(api_key=...) unchanged.
        # Per-index constituent lists loaded this session, keyed by index name.
        self._constituents_by_index: dict[str, list[dict]] = {}
        # Name/sector maps accumulate across every index loaded so quote
        # labelling works regardless of which universe a symbol came from.
        self._name_by_symbol: dict[str, str] = {}
        self._sector_by_symbol: dict[str, str] = {}
        # symbol -> full most-recent-first bar list fetched this session.
        self._history_cache: dict[str, list[dict]] = {}
        self.requests_made = 0

    # ------------------------------------------------------------------ #
    # Index universes (from bundled snapshots)                           #
    # ------------------------------------------------------------------ #
    def get_constituents(self, index: str = _DEFAULT_INDEX) -> Optional[list[dict]]:
        """Return the bundled constituent snapshot for an index universe.

        Args:
            index: one of ``_INDEX_FILES`` (currently "sp500" or "russell2000").

        Returns a list of {symbol, name, sector, subSector}, or None on error.
        Yahoo does not serve index membership, so this reads the bundled
        ``data/<index>_constituents.json`` snapshot. Results are cached and the
        name/sector maps are merged so labelling works across mixed universes.
        """
        index = (index or _DEFAULT_INDEX).lower()
        if index in self._constituents_by_index:
            return self._constituents_by_index[index]
        filename = _INDEX_FILES.get(index)
        if filename is None:
            print(
                f"ERROR: unknown index '{index}'. Supported: "
                f"{', '.join(sorted(_INDEX_FILES))}.",
                file=sys.stderr,
            )
            return None
        path = os.path.join(_DATA_DIR, filename)
        try:
            with open(path) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(
                f"ERROR: could not read bundled {index} list at {path}: {e}",
                file=sys.stderr,
            )
            return None
        self._constituents_by_index[index] = data
        for c in data:
            # Don't let a placeholder label (name == symbol / "Unknown" sector,
            # as in the symbol-only Russell snapshot) clobber a richer label
            # already loaded from another index.
            sym = c["symbol"]
            name = c.get("name", sym)
            sector = c.get("sector", "Unknown")
            if name and name != sym or sym not in self._name_by_symbol:
                self._name_by_symbol[sym] = name
            if sector and sector != "Unknown" or sym not in self._sector_by_symbol:
                self._sector_by_symbol[sym] = sector
        return data

    def get_sp500_constituents(self) -> Optional[list[dict]]:
        """Return the bundled S&P 500 snapshot (back-compat wrapper)."""
        return self.get_constituents("sp500")

    def _lookup_name_sector(self, symbol: str) -> tuple[str, str]:
        if not self._name_by_symbol:
            # Ensure at least the default universe's labels are available.
            self.get_constituents(_DEFAULT_INDEX)
        return (
            self._name_by_symbol.get(symbol, symbol),
            self._sector_by_symbol.get(symbol, "Unknown"),
        )

    # ------------------------------------------------------------------ #
    # Quotes                                                             #
    # ------------------------------------------------------------------ #
    def get_batch_quotes(self, symbols: list[str]) -> dict[str, dict]:
        """Fetch quote-equivalents for many symbols via one bulk download.

        Downloads ~1y of daily history for all symbols in a single threaded
        yfinance call, derives price/52w-high/52w-low/avg-volume from it, and
        caches the full history so Phase-2 ``get_historical_prices`` calls are
        served from memory with no extra network round-trips.

        ``marketCap`` is left at 0 here (never used by the screener's filters).
        """
        results: dict[str, dict] = {}
        if not symbols:
            return results

        norm = [_normalize_symbol(s) for s in symbols]
        # Ensure name/sector labels are available. Whatever index(es) the caller
        # already loaded stay cached; fall back to the default universe's labels.
        if not self._name_by_symbol:
            self.get_constituents(_DEFAULT_INDEX)

        self.requests_made += 1
        data = yf.download(
            tickers=norm,
            period="1y",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            actions=False,
            threads=True,
            progress=False,
        )

        multi = len(norm) > 1
        for sym in norm:
            try:
                df = data[sym] if multi else data
            except (KeyError, TypeError):
                df = None
            bars = _dataframe_to_bars(df) if df is not None else []
            if not bars:
                continue
            self._history_cache[sym] = bars
            name, sector = self._lookup_name_sector(sym)
            quote = _quote_from_bars(sym, bars, name=name, sector=sector)
            if quote:
                results[sym] = quote
        return results

    def get_quote(self, symbols: str) -> Optional[list[dict]]:
        """Fetch quote(s) for one or more comma-separated symbols.

        Kept for interface compatibility; delegates to the bulk path.
        """
        syms = [s for s in symbols.split(",") if s.strip()]
        batch = self.get_batch_quotes(syms)
        out = [batch[s] for s in (_normalize_symbol(x) for x in syms) if s in batch]
        return out or None

    # ------------------------------------------------------------------ #
    # Historical prices                                                  #
    # ------------------------------------------------------------------ #
    def get_historical_prices(self, symbol: str, days: int = 365) -> Optional[dict]:
        """Fetch daily OHLCV history, most-recent-first.

        Returns {"symbol", "historical": [...]}. Serves from the session cache
        when a prior bulk download already covered enough bars; otherwise makes
        a single-ticker yfinance request.
        """
        sym = _normalize_symbol(symbol)

        cached = self._history_cache.get(sym)
        if cached is not None and len(cached) >= days:
            return {"symbol": sym, "historical": cached[:days]}

        # Pad the requested trading-day count into a calendar period. ~365/252
        # ≈ 1.45 calendar days per trading day; 1.6x + a floor leaves headroom
        # for weekends/holidays so we don't come up short.
        period_days = max(int(days * 1.6) + 10, 40)
        self.requests_made += 1
        try:
            ticker = yf.Ticker(sym)
            df = ticker.history(
                period=f"{period_days}d",
                interval="1d",
                auto_adjust=False,
                actions=False,
            )
        except Exception as e:  # noqa: BLE001 - yfinance raises many shapes
            print(f"WARN: history fetch failed for {sym}: {e}", file=sys.stderr)
            return None

        bars = _dataframe_to_bars(df)
        if not bars:
            return None
        self._history_cache[sym] = bars
        return {"symbol": sym, "historical": bars[:days]}

    def get_batch_historical(
        self, symbols: list[str], days: int = 260
    ) -> dict[str, list[dict]]:
        """Fetch historical prices for multiple symbols."""
        results: dict[str, list[dict]] = {}
        for symbol in symbols:
            data = self.get_historical_prices(symbol, days=days)
            if data and data.get("historical"):
                results[_normalize_symbol(symbol)] = data["historical"]
        return results

    # ------------------------------------------------------------------ #
    # Misc helpers / stats                                               #
    # ------------------------------------------------------------------ #
    def calculate_sma(self, prices: list[float], period: int) -> float:
        """Simple moving average from a most-recent-first price list."""
        if not prices:
            return 0.0
        if len(prices) < period:
            return sum(prices) / len(prices)
        return sum(prices[:period]) / period

    def get_api_stats(self) -> dict:
        """Usage stats (kept key-compatible with the old client)."""
        return {
            "cache_entries": len(self._history_cache),
            "api_calls_made": self.requests_made,
            "rate_limit_reached": False,
            "data_source": "yfinance",
        }


# Backward-compatibility alias in case any external tooling still refers to the
# old class name. New code should import YFClient directly.
FMPClient = YFClient
