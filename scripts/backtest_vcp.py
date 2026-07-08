#!/usr/bin/env python3
"""Multi-ticker VCP backtest — walk N years of history for a universe of
tickers, detect every VCP that formed, and aggregate forward outcomes.

Builds on the single-ticker historical scanner (``historical_scanner.py``):
for each ticker it fetches a long history once, sweeps the as-of cursor,
labels each detection with its forward outcome, then pools everything into
portfolio-level statistics (overall / per-year / per-rating-band / per-ticker).

Usage:
    # 10-year backtest on a custom universe
    python3 scripts/backtest_vcp.py --years 10 --universe AAPL NVDA MSFT

    # 10-year backtest on the first 50 S&P 500 names in the snapshot
    python3 scripts/backtest_vcp.py --years 10 --index sp500 --limit 50

    # Tickers from a file (one symbol per line, '#' comments allowed)
    python3 scripts/backtest_vcp.py --years 10 --universe-file tickers.txt

Output (timestamped, in --output-dir):
    vcp_backtest_<YYYY-MM-DD_HHMMSS>.json  — metadata + summary + timelines
    vcp_backtest_<YYYY-MM-DD_HHMMSS>.md    — human-readable report
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest_aggregator import build_backtest_summary  # noqa: E402
from backtest_report import write_backtest_reports  # noqa: E402
from historical_scanner import sanitize_ticker, scan_history  # noqa: E402
from yf_client import YFClient  # noqa: E402

TRADING_DAYS_PER_YEAR = 252


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Multi-ticker VCP historical backtest (Minervini VCP)"
    )
    parser.add_argument(
        "--years",
        type=float,
        default=10.0,
        help="Years of history to scan per ticker (default: 10)",
    )
    universe = parser.add_mutually_exclusive_group()
    universe.add_argument(
        "--universe", nargs="+", help="Explicit ticker symbols to backtest"
    )
    universe.add_argument(
        "--universe-file",
        help="Path to a text file with one ticker per line ('#' comments allowed)",
    )
    parser.add_argument(
        "--index",
        choices=["sp500", "russell2000", "both"],
        default="sp500",
        help="Index universe when --universe/--universe-file not given (default: sp500)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max tickers taken from the index universe (default: 50; 0 = all)",
    )
    parser.add_argument(
        "--stride-days",
        type=int,
        default=5,
        help="Trading-day step for the as-of cursor (default: 5)",
    )
    parser.add_argument(
        "--outcome-days",
        type=int,
        default=60,
        help="Forward window for outcome evaluation (default: 60)",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=120,
        help="VCP pattern lookback window in days (default: 120)",
    )
    parser.add_argument(
        "--min-contractions", type=int, default=2, help="Min contractions (default: 2)"
    )
    parser.add_argument(
        "--t1-depth-min", type=float, default=10.0, help="Min T1 depth %% (default: 10.0)"
    )
    parser.add_argument(
        "--contraction-ratio",
        type=float,
        default=0.70,
        help="Max successive contraction ratio (default: 0.70)",
    )
    parser.add_argument(
        "--atr-multiplier",
        type=float,
        default=1.5,
        help="ATR multiplier for swing detection (default: 1.5)",
    )
    parser.add_argument(
        "--min-contraction-days",
        type=int,
        default=5,
        help="Min days per contraction (default: 5)",
    )
    parser.add_argument(
        "--breakout-volume-ratio",
        type=float,
        default=1.5,
        help="Breakout volume ratio vs 50d avg (default: 1.5)",
    )
    parser.add_argument(
        "--output-dir", default="backtests/", help="Output directory (default: backtests/)"
    )
    parser.add_argument(
        "--sleep-secs",
        type=float,
        default=0.5,
        help="Pause between ticker fetches to be polite to Yahoo (default: 0.5)",
    )

    args = parser.parse_args()
    if not (0.5 <= args.years <= 20):
        parser.error("--years must be between 0.5 and 20")
    if not (1 <= args.stride_days <= 60):
        parser.error("--stride-days must be 1-60")
    if not (5 <= args.outcome_days <= 252):
        parser.error("--outcome-days must be 5-252")
    if not (30 <= args.lookback_days <= 365):
        parser.error("--lookback-days must be 30-365")
    return args


def read_universe_file(path: str) -> list[str]:
    """Read one-ticker-per-line file; ignores blanks and '#' comments."""
    if not os.path.isfile(path):
        print(f"ERROR: universe file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        raw = [line.split("#")[0].strip() for line in f]
    return [sym for sym in raw if sym]


def resolve_universe(args: argparse.Namespace, client: YFClient) -> tuple[list[str], str]:
    """Determine the ticker list and a description string for reports."""
    if args.universe:
        return args.universe, f"Custom ({len(args.universe)} tickers)"
    if args.universe_file:
        symbols = read_universe_file(args.universe_file)
        return symbols, f"File: {os.path.basename(args.universe_file)} ({len(symbols)} tickers)"

    indices = ["sp500", "russell2000"] if args.index == "both" else [args.index]
    merged: list[str] = []
    seen: set[str] = set()
    for idx in indices:
        constituents = client.get_constituents(idx) or []
        for c in constituents:
            if c["symbol"] not in seen:
                seen.add(c["symbol"])
                merged.append(c["symbol"])
    if args.limit and args.limit > 0:
        merged = merged[: args.limit]
    label = " + ".join(indices)
    return merged, f"{label} (first {len(merged)} of snapshot order)"


def validate_symbols(symbols: list[str]) -> list[str]:
    """Sanitize all symbols up front; exits with a clear message on bad input."""
    clean: list[str] = []
    for sym in symbols:
        try:
            clean.append(sanitize_ticker(sym))
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
    return clean


def run_backtest(args: argparse.Namespace) -> None:
    client = YFClient()
    symbols, universe_desc = resolve_universe(args, client)
    symbols = validate_symbols(symbols)
    if not symbols:
        print("ERROR: empty universe — nothing to backtest", file=sys.stderr)
        sys.exit(1)

    scan_days = int(args.years * TRADING_DAYS_PER_YEAR)
    # Extra bars: lookback at the oldest offset + outcome window + safety buffer.
    fetch_days = scan_days + args.lookback_days + args.outcome_days + 60

    print("=" * 70)
    print(f"VCP Historical Backtest — {len(symbols)} tickers, ~{args.years:g} years")
    print("=" * 70)
    print(f"Universe: {universe_desc}")
    print(f"Scan window: {scan_days} trading days | stride {args.stride_days}d | "
          f"outcome {args.outcome_days}d")
    print()

    print("Fetching SPY benchmark history...", end=" ", flush=True)
    spy_data = client.get_historical_prices("SPY", days=fetch_days)
    sp500_history = spy_data.get("historical", []) if spy_data else []
    if not sp500_history:
        print("FAILED")
        print("ERROR: SPY history unavailable — cannot compute relative strength",
              file=sys.stderr)
        sys.exit(1)
    print(f"OK ({len(sp500_history)} bars)")

    analyzer_kwargs = {
        "min_contractions": args.min_contractions,
        "t1_depth_min": args.t1_depth_min,
        "contraction_ratio": args.contraction_ratio,
        "atr_multiplier": args.atr_multiplier,
        "min_contraction_days": args.min_contraction_days,
        "breakout_volume_ratio": args.breakout_volume_ratio,
    }

    per_ticker: dict[str, list[dict]] = {}
    failures: list[str] = []
    for i, sym in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] {sym}...", end=" ", flush=True)
        try:
            data = client.get_historical_prices(sym, days=fetch_days)
        except Exception as e:  # noqa: BLE001 — one bad ticker must not kill the run
            print(f"FETCH ERROR ({e})")
            failures.append(sym)
            continue
        historical = data.get("historical", []) if data else []
        if len(historical) < args.lookback_days + 30:
            print(f"skipped (only {len(historical)} bars)")
            failures.append(sym)
            continue

        detections = scan_history(
            sym,
            historical,
            sp500_history,
            stride_days=args.stride_days,
            outcome_days=args.outcome_days,
            lookback_days=args.lookback_days,
            analyzer_kwargs=analyzer_kwargs,
        )
        per_ticker[sym] = detections
        print(f"{len(detections)} detections ({len(historical)} bars)")
        if args.sleep_secs > 0 and i < len(symbols):
            time.sleep(args.sleep_secs)

    if not per_ticker:
        print("ERROR: no ticker produced usable history — nothing to report",
              file=sys.stderr)
        sys.exit(1)

    summary = build_backtest_summary(per_ticker)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    metadata = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "universe_description": universe_desc,
        "years": args.years,
        "scan_days": scan_days,
        "stride_days": args.stride_days,
        "outcome_days": args.outcome_days,
        "lookback_days": args.lookback_days,
        "tuning_params": analyzer_kwargs,
        "failed_tickers": failures,
        "api_stats": client.get_api_stats(),
    }
    json_path, md_path = write_backtest_reports(
        summary, metadata, args.output_dir, timestamp, detections_by_ticker=per_ticker
    )

    overall = summary["overall"]
    print()
    print("=" * 70)
    print("Backtest complete")
    print("=" * 70)
    print(f"  Tickers scanned:   {summary['tickers_scanned']} "
          f"({len(failures)} failed/skipped)")
    print(f"  Total detections:  {overall['total_detections']}")
    if overall["breakout_rate_pct"] is not None:
        print(f"  Breakout rate:     {overall['breakout_rate_pct']}% "
              f"(of {overall['resolved']} resolved)")
        print(f"  Stop-hit rate:     {overall['stop_hit_rate_pct']}%")
        print(f"  Timeout rate:      {overall['timeout_rate_pct']}%")
    print(f"  JSON report:       {json_path}")
    print(f"  Markdown report:   {md_path}")
    print()


def main() -> None:
    run_backtest(parse_arguments())


if __name__ == "__main__":
    main()
