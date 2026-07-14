#!/usr/bin/env python3
"""Download daily price history for the current S&P 500 into one CSV.

The constituent universe comes from ``scripts/data/sp500_constituents.json``.
By default Yahoo Finance's maximum available daily history is requested and
written to ``SP500_Historical_Data.csv`` in this shape::

    Ticker,Date,Open,High,Low,Close,Adj Close,Volume

Examples:
    python3 scripts/download_sp500_history.py
    python3 scripts/download_sp500_history.py --output data/sp500_history.csv
    python3 scripts/download_sp500_history.py --start 2010-01-01
    python3 scripts/download_sp500_history.py --symbols AAPL MSFT --start 2024-01-01

The download is batched to reduce rate-limit pressure. Missing symbols are
retried individually, and the destination is replaced only after the run has
finished so an interrupted run cannot leave a half-written target file.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from typing import Callable, Iterable

import yfinance as yf


COLUMNS = ["Ticker", "Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"]
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONSTITUENTS = SCRIPT_DIR / "data" / "sp500_constituents.json"
DEFAULT_OUTPUT = Path("SP500_Historical_Data.csv")
PRICE_FIELDS = {"Open", "High", "Low", "Close", "Adj Close", "Volume"}
TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,14}$")


def _iso_date(value: str) -> str:
    """Argparse validator for ISO calendar dates."""
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date {value!r}; use YYYY-MM-DD") from exc


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download current S&P 500 daily OHLCV history to a combined CSV."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Destination CSV (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--constituents",
        type=Path,
        default=DEFAULT_CONSTITUENTS,
        help="S&P 500 constituent JSON file",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Optional ticker override, useful for a small test download",
    )
    parser.add_argument("--start", type=_iso_date, help="First date, YYYY-MM-DD")
    parser.add_argument(
        "--end",
        type=_iso_date,
        help="Exclusive end date, YYYY-MM-DD (Yahoo Finance convention)",
    )
    parser.add_argument("--batch-size", type=int, default=25, help="Tickers per request")
    parser.add_argument("--retries", type=int, default=3, help="Attempts per request")
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=2.0,
        help="Initial retry delay in seconds (doubles after each failure)",
    )
    parser.add_argument(
        "--sleep-secs",
        type=float,
        default=0.5,
        help="Pause between successful batches",
    )
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")
    if args.retries < 1:
        parser.error("--retries must be at least 1")
    if args.retry_delay < 0 or args.sleep_secs < 0:
        parser.error("delay values cannot be negative")
    if args.start and args.end and args.start >= args.end:
        parser.error("--start must be earlier than --end")
    return args


def normalize_symbol(symbol: str) -> str:
    """Normalize class-share tickers to Yahoo's dash form."""
    return symbol.strip().upper().replace(".", "-")


def load_symbols(path: Path) -> list[str]:
    """Read and validate unique symbols from a constituent JSON snapshot."""
    try:
        with path.open() as file:
            rows = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read constituent file {path}: {exc}") from exc
    if not isinstance(rows, list):
        raise ValueError(f"constituent file {path} must contain a JSON list")

    symbols = []
    for row in rows:
        raw = row.get("symbol", "") if isinstance(row, dict) else ""
        symbol = normalize_symbol(raw)
        if symbol and TICKER_RE.fullmatch(symbol):
            symbols.append(symbol)
    symbols = sorted(set(symbols))
    if not symbols:
        raise ValueError(f"no valid ticker symbols found in {path}")
    return symbols


def _download_kwargs(start: str | None, end: str | None) -> dict:
    kwargs = {
        "auto_adjust": False,
        "actions": False,
        "group_by": "ticker",
        "threads": True,
        "progress": False,
    }
    if start or end:
        # Yahoo does not accept period="max" together with an end date.
        kwargs["start"] = start or "1900-01-01"
        if end:
            kwargs["end"] = end
    else:
        kwargs["period"] = "max"
    return kwargs


def download_with_retries(
    symbols: list[str],
    start: str | None,
    end: str | None,
    retries: int,
    retry_delay: float,
    downloader: Callable = yf.download,
):
    """Download one batch, retrying exceptions and empty responses."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            frame = downloader(symbols, **_download_kwargs(start, end))
            if frame is not None and not frame.empty:
                return frame
            last_error = RuntimeError("Yahoo Finance returned no rows")
        except Exception as exc:  # noqa: BLE001 - network/library errors vary
            last_error = exc
        if attempt < retries:
            delay = retry_delay * (2 ** (attempt - 1))
            print(
                f"    attempt {attempt}/{retries} failed: {last_error}; retrying in {delay:g}s",
                file=sys.stderr,
            )
            if delay:
                time.sleep(delay)
    print(f"    request failed after {retries} attempt(s): {last_error}", file=sys.stderr)
    return None


def extract_symbol_frame(frame, symbol: str, batch_size: int):
    """Extract a ticker's columns across yfinance's possible column layouts."""
    if frame is None or frame.empty:
        return None
    columns = frame.columns
    if getattr(columns, "nlevels", 1) == 1:
        return frame if batch_size == 1 else None

    for level in range(columns.nlevels):
        values = {str(value) for value in columns.get_level_values(level)}
        if symbol in values:
            result = frame.xs(symbol, axis=1, level=level, drop_level=True)
            while getattr(result.columns, "nlevels", 1) > 1:
                result.columns = result.columns.droplevel(0)
            return result

    # Some yfinance releases retain a one-ticker MultiIndex whose ticker label
    # differs only in punctuation. If the other level is clearly OHLCV, unwrap it.
    if batch_size == 1:
        for level in range(columns.nlevels):
            values = {str(value) for value in columns.get_level_values(level)}
            if PRICE_FIELDS.intersection(values):
                other_levels = [i for i in range(columns.nlevels) if i != level]
                result = frame.copy()
                if other_levels:
                    result.columns = result.columns.droplevel(other_levels)
                return result
    return None


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def iter_csv_rows(symbol: str, frame) -> Iterable[list]:
    """Yield clean, ascending-date CSV rows from a ticker DataFrame."""
    if frame is None or frame.empty:
        return
    frame = frame.sort_index()
    for timestamp, row in frame.iterrows():
        prices = [_finite(row.get(field)) for field in ("Open", "High", "Low", "Close")]
        if any(value is None for value in prices):
            continue
        adjusted = _finite(row.get("Adj Close"))
        volume = _finite(row.get("Volume"))
        yield [
            symbol,
            timestamp.strftime("%Y-%m-%d"),
            *(round(value, 6) for value in prices),
            round(adjusted if adjusted is not None else prices[3], 6),
            int(volume) if volume is not None else 0,
        ]


def download_to_csv(
    symbols: list[str],
    output: Path,
    *,
    start: str | None = None,
    end: str | None = None,
    batch_size: int = 25,
    retries: int = 3,
    retry_delay: float = 2.0,
    sleep_secs: float = 0.5,
    downloader: Callable = yf.download,
) -> tuple[int, list[str]]:
    """Download symbols and atomically write a combined OHLCV CSV."""
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".part", dir=output.parent
    )
    os.close(fd)
    row_count = 0
    failed: list[str] = []

    try:
        with open(temp_name, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(COLUMNS)
            for offset in range(0, len(symbols), batch_size):
                batch = symbols[offset : offset + batch_size]
                print(f"[{offset + 1}-{offset + len(batch)}/{len(symbols)}] {', '.join(batch)}")
                frame = download_with_retries(
                    batch, start, end, retries, retry_delay, downloader
                )
                missing: list[str] = []
                batch_rows = 0
                for symbol in batch:
                    symbol_frame = extract_symbol_frame(frame, symbol, len(batch))
                    rows = list(iter_csv_rows(symbol, symbol_frame))
                    if not rows:
                        missing.append(symbol)
                        continue
                    writer.writerows(rows)
                    row_count += len(rows)
                    batch_rows += len(rows)

                # Bulk responses can omit one ticker even though the request as
                # a whole succeeds. Retry only those omissions individually.
                for symbol in missing:
                    single = download_with_retries(
                        [symbol], start, end, retries, retry_delay, downloader
                    )
                    rows = list(iter_csv_rows(symbol, extract_symbol_frame(single, symbol, 1)))
                    if rows:
                        writer.writerows(rows)
                        row_count += len(rows)
                        batch_rows += len(rows)
                    else:
                        failed.append(symbol)
                print(f"    wrote {batch_rows:,} rows ({row_count:,} total)")
                if sleep_secs and offset + batch_size < len(symbols):
                    time.sleep(sleep_secs)

        if row_count == 0:
            raise RuntimeError("download produced no price rows; destination was not changed")
        os.replace(temp_name, output)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
    return row_count, failed


def main() -> int:
    args = parse_arguments()
    try:
        if args.symbols:
            invalid = [item for item in args.symbols if not TICKER_RE.fullmatch(item.upper())]
            if invalid:
                raise ValueError(f"invalid ticker symbol(s): {', '.join(invalid)}")
            symbols = sorted({normalize_symbol(item) for item in args.symbols})
        else:
            symbols = load_symbols(args.constituents)

        period = f"{args.start or 'earliest available'} to {args.end or 'today'}"
        print(f"Downloading {len(symbols)} ticker(s), {period}")
        rows, failed = download_to_csv(
            symbols,
            args.output,
            start=args.start,
            end=args.end,
            batch_size=args.batch_size,
            retries=args.retries,
            retry_delay=args.retry_delay,
            sleep_secs=args.sleep_secs,
        )
        print(f"\nSaved {rows:,} rows to {args.output.expanduser().resolve()}")
        if failed:
            print(
                f"WARNING: no data for {len(failed)} ticker(s): {', '.join(failed)}",
                file=sys.stderr,
            )
            return 1
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
