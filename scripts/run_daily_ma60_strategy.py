#!/usr/bin/env python3
"""Refresh prices and print the current MA60 strategy like qqq_backtest.py.

This is a daily research/paper-trading dashboard, not a broker integration.  It
atomically maintains a local PIT-plus-live price CSV, asks the sibling QQQ
breadth repository for its current state, causally replays the current
MA60/Slope10 portfolio, and prints performance, trades, open positions and
next-open candidate orders.

The current strategy is experimental and has a Backtest Score of 20/100
(Reject).  The dashboard does not promote it to a validated live strategy.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from csv_client import CSVClient
from current_ma60_candidate import (
    INITIAL_STOP_PCT,
    MA_PERIOD,
    SLOPE_SESSIONS,
    TRAILING_PCT,
    TRIGGER_R,
    calculate_current_buy_signal,
)
from download_sp500_history import (
    COLUMNS,
    download_with_retries,
    extract_symbol_frame,
    iter_csv_rows,
    load_symbols,
)
from ma60_only_experiment import _sector_map, build_standalone_signals
from ma60_period_gate_experiment import WINDOWS as FALLBACK_WINDOWS
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from portfolio_backtest import Config, run_portfolio


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_DATA_DIR = REPO_ROOT / "daily_data"
DEFAULT_SEED_CSV = REPO_ROOT / "SP500_PIT_2016_2026.csv"
DEFAULT_CONSTITUENTS = SCRIPT_DIR / "data" / "sp500_constituents.json"
DEFAULT_SECTORS = SCRIPT_DIR / "data" / "sp500_constituents.json"
DEFAULT_QQQ_REPO = REPO_ROOT.parent / "spy500-breadth-backtest"
ONE_WAY_COST = 10.0 / 10_000
SIMULATION_START = "2016-07-05"
SIGNAL_START = "2016-07-01"
QQQ_MARKER = "__QQQ_DAILY_STATE__"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--seed-csv", type=Path, default=DEFAULT_SEED_CSV)
    parser.add_argument("--constituents", type=Path, default=DEFAULT_CONSTITUENTS)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--sector-json", default=str(DEFAULT_SECTORS))
    parser.add_argument("--qqq-repo", type=Path, default=DEFAULT_QQQ_REPO)
    parser.add_argument("--qqq-python", default=os.environ.get("QQQ_PYTHON", "python3"))
    parser.add_argument(
        "--force-qqq-state", choices=("in", "out"),
        help="Skip the QQQ bridge and force only the current state (diagnostic).",
    )
    parser.add_argument("--no-fetch", action="store_true", help="Use the saved price CSV")
    parser.add_argument("--refresh-days", type=int, default=450)
    parser.add_argument("--batch-size", type=int, default=40)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-delay", type=float, default=2.0)
    parser.add_argument("--sleep-secs", type=float, default=0.5)
    parser.add_argument("--recent-trades", type=int, default=20)
    parser.add_argument("--all-trades", action="store_true")
    parser.add_argument("--as-of", help="Last completed signal date, YYYY-MM-DD")
    args = parser.parse_args()
    if args.refresh_days < 120:
        parser.error("--refresh-days must be at least 120")
    if args.batch_size < 1 or args.retries < 1:
        parser.error("batch size and retries must be positive")
    if args.recent_trades < 0:
        parser.error("--recent-trades must be non-negative")
    if args.as_of:
        try:
            date.fromisoformat(args.as_of)
        except ValueError:
            parser.error("--as-of must be YYYY-MM-DD")
    return args


def _fmt_number(value: object, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def ensure_price_store(data_dir: Path, seed_csv: Path) -> Path:
    """Create the live store from the PIT seed without modifying the seed."""
    data_dir.mkdir(parents=True, exist_ok=True)
    store = data_dir / "sp500_pit_live.csv"
    if store.exists():
        return store
    if not seed_csv.exists():
        raise FileNotFoundError(
            f"price seed not found: {seed_csv}. Supply --seed-csv or create it first.")
    print(f"Initialising live price store from {seed_csv} ...")
    fd, temp_name = tempfile.mkstemp(prefix=f".{store.name}.", dir=data_dir)
    os.close(fd)
    try:
        shutil.copyfile(seed_csv, temp_name)
        os.replace(temp_name, store)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return store


def download_price_tail(
    symbols: list[str], start: str, end: str, *, batch_size: int,
    retries: int, retry_delay: float, sleep_secs: float,
) -> tuple[dict[str, list[list]], list[str]]:
    """Fetch a recent OHLCV tail for current members plus real SPY."""
    import time as time_module

    downloaded: dict[str, list[list]] = {}
    failed: list[str] = []
    for offset in range(0, len(symbols), batch_size):
        batch = symbols[offset:offset + batch_size]
        frame = download_with_retries(
            batch, start, end, retries, retry_delay)
        batch_rows = 0
        missing: list[str] = []
        for symbol in batch:
            sub = extract_symbol_frame(frame, symbol, len(batch))
            rows = list(iter_csv_rows(symbol, sub))
            if rows:
                downloaded[symbol] = rows
                batch_rows += len(rows)
            else:
                missing.append(symbol)
        # Retry omissions individually; class-share tickers are frequent batch misses.
        for symbol in missing:
            frame = download_with_retries(
                [symbol], start, end, retries, retry_delay)
            sub = extract_symbol_frame(frame, symbol, 1)
            rows = list(iter_csv_rows(symbol, sub))
            if rows:
                downloaded[symbol] = rows
                batch_rows += len(rows)
            else:
                failed.append(symbol)
        print(
            f"  [{offset + len(batch):>3}/{len(symbols)}] "
            f"{len(batch) - len(missing):>2} batch hits, +{batch_rows} rows")
        if sleep_secs and offset + batch_size < len(symbols):
            time_module.sleep(sleep_secs)
    return downloaded, failed


def merge_price_tail(
    store: Path,
    downloaded: dict[str, list[list]],
    refresh_start: str,
    current_symbols: list[str],
    data_dir: Path,
) -> dict:
    """Atomically replace downloaded symbols' recent tails and save snapshots."""
    replace = set(downloaded)
    current = set(current_symbols)
    latest: dict[str, list] = {}
    fd, temp_name = tempfile.mkstemp(prefix=f".{store.name}.", dir=store.parent)
    try:
        with store.open(newline="") as source, os.fdopen(
                fd, "w", newline="") as target:
            reader = csv.reader(source)
            writer = csv.writer(target)
            header = next(reader, None)
            if header != COLUMNS:
                raise ValueError(f"unexpected price-store header: {header}")
            writer.writerow(COLUMNS)
            for row in reader:
                if len(row) < len(COLUMNS):
                    continue
                symbol, row_date = row[0].strip().upper(), row[1].strip()
                if symbol in replace and row_date >= refresh_start:
                    continue
                writer.writerow(row[:len(COLUMNS)])
                if symbol in current and row_date > (latest.get(symbol) or ["", ""])[1]:
                    latest[symbol] = row[:len(COLUMNS)]
            for symbol in sorted(downloaded):
                unique = {row[1]: row for row in downloaded[symbol]}
                for row_date in sorted(unique):
                    row = unique[row_date]
                    writer.writerow(row)
                    if row_date > (latest.get(symbol) or ["", ""])[1]:
                        latest[symbol] = row
        os.replace(temp_name, store)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise

    snapshot_rows = [latest[symbol] for symbol in sorted(latest)]
    latest_path = data_dir / "latest_prices.csv"
    with latest_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        writer.writerows(snapshot_rows)
    spy_date = (latest.get("SPY") or ["", ""])[1]
    if spy_date:
        snapshots = data_dir / "snapshots"
        snapshots.mkdir(exist_ok=True)
        snapshot_path = snapshots / f"{spy_date}.csv"
        with snapshot_path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(COLUMNS)
            writer.writerows(snapshot_rows)
    else:
        snapshot_path = None
    return {
        "latest_rows": len(snapshot_rows),
        "latest_spy_date": spy_date or None,
        "latest_prices_csv": str(latest_path),
        "snapshot_csv": str(snapshot_path) if snapshot_path else None,
    }


def refresh_price_store(args: argparse.Namespace, store: Path) -> dict:
    symbols = load_symbols(args.constituents)
    symbols = sorted(set([*symbols, "SPY"]))
    end_date = date.today() + timedelta(days=1)
    start_date = date.today() - timedelta(days=args.refresh_days)
    print(
        f"Fetching current S&P 500 + SPY: {start_date} → {end_date} "
        f"({len(symbols)} symbols) ...")
    downloaded, failed = download_price_tail(
        symbols, start_date.isoformat(), end_date.isoformat(),
        batch_size=args.batch_size, retries=args.retries,
        retry_delay=args.retry_delay, sleep_secs=args.sleep_secs)
    coverage = len(downloaded) / len(symbols) if symbols else 0.0
    if coverage < 0.90:
        raise RuntimeError(
            f"Yahoo coverage only {coverage:.1%}; refusing to replace the local tail")
    merge = merge_price_tail(
        store, downloaded, start_date.isoformat(), symbols, args.data_dir)
    manifest = {
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": "Yahoo Finance via yfinance",
        "store": str(store),
        "refresh_start": start_date.isoformat(),
        "exclusive_end": end_date.isoformat(),
        "requested_symbols": len(symbols),
        "downloaded_symbols": len(downloaded),
        "coverage_pct": 100 * coverage,
        "failed_symbols": failed,
        **merge,
    }
    _atomic_json(args.data_dir / "latest_update.json", manifest)
    return manifest


def _parse_qqq_bridge(output: str) -> dict:
    for line in reversed(output.splitlines()):
        if line.startswith(QQQ_MARKER):
            return json.loads(line[len(QQQ_MARKER):])
    raise ValueError("QQQ bridge did not emit a machine-readable state")


def load_qqq_state(qqq_repo: Path, python: str, as_of: str) -> dict:
    """Run qqq_backtest's real state machine and probe its next-open action."""
    qqq_repo = qqq_repo.expanduser().resolve()
    if not (qqq_repo / "qqq_backtest.py").exists():
        raise FileNotFoundError(f"qqq_backtest.py not found in {qqq_repo}")
    bridge = f'''\
import json
import pandas as pd
import qqq_backtest as q
df = q.load_data()
df = df.loc[df.index <= pd.Timestamp("{as_of}")].copy()
if df.empty:
    raise RuntimeError("QQQ history has no row at or before {as_of}")
_, trades, open_trade = q.run_strategy(
    df, cooldown_days=q.COOLDOWN_DAYS, execution_lag=1, fill_on="open")
probe = df.copy()
next_date = df.index[-1] + pd.offsets.BDay(1)
probe.loc[next_date] = df.iloc[-1]
_, probe_trades, probe_open = q.run_strategy(
    probe, cooldown_days=q.COOLDOWN_DAYS, execution_lag=1, fill_on="open")
risk_on = open_trade is not None
probe_risk_on = probe_open is not None
action = "SELL_NEXT_OPEN" if risk_on and not probe_risk_on else (
    "BUY_NEXT_OPEN" if not risk_on and probe_risk_on else "NONE")
windows = [[t["entry_date"].strftime("%Y-%m-%d"),
            t["exit_date"].strftime("%Y-%m-%d")] for t in trades]
if open_trade:
    windows.append([open_trade["entry_date"].strftime("%Y-%m-%d"), None])
recent = [{{
    "entry_date": t["entry_date"].strftime("%Y-%m-%d"),
    "exit_date": t["exit_date"].strftime("%Y-%m-%d"),
    "buy_trigger": t.get("buy_trigger"),
    "sell_reason": t.get("sell_reason"),
}} for t in trades[-3:]]
payload = {{
    "source": str(q.DATA_DIR / "qqq_backtest.py"),
    "latest_date": df.index[-1].strftime("%Y-%m-%d"),
    "risk_on_at_latest_open": risk_on,
    "next_open_action": action,
    "risk_on_after_next_open": probe_risk_on,
    "open_since": (open_trade["entry_date"].strftime("%Y-%m-%d")
                   if open_trade else None),
    "windows": windows,
    "recent_trades": recent,
}}
print("{QQQ_MARKER}" + json.dumps(payload, sort_keys=True))
'''
    env = dict(os.environ)
    env.setdefault("MPLBACKEND", "Agg")
    result = subprocess.run(
        [python, "-c", bridge], cwd=qqq_repo, env=env,
        text=True, capture_output=True, timeout=300, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout)[-2000:]
        raise RuntimeError(f"QQQ bridge failed ({result.returncode}):\n{detail}")
    return _parse_qqq_bridge(result.stdout)


def forced_qqq_state(state: str, as_of: str) -> dict:
    windows = [list(window) for window in FALLBACK_WINDOWS]
    risk_on = state == "in"
    if not risk_on and windows and windows[-1][1] is None:
        windows[-1][1] = as_of
    return {
        "source": "forced diagnostic state",
        "latest_date": as_of,
        "risk_on_at_latest_open": risk_on,
        "next_open_action": "NONE",
        "risk_on_after_next_open": risk_on,
        "open_since": windows[-1][0] if risk_on else None,
        "windows": windows,
        "recent_trades": [],
    }


def latest_completed_spy_date(
    spy_dates: list[str], now: datetime | None = None,
) -> str:
    """Exclude a possibly partial US daily bar before 16:15 New York time."""
    if not spy_dates:
        raise ValueError("real SPY history is empty")
    now_ny = (now or datetime.now(ZoneInfo("America/New_York"))).astimezone(
        ZoneInfo("America/New_York"))
    latest = max(spy_dates)
    if (latest == now_ny.date().isoformat()
            and now_ny.time() < time(16, 15)):
        prior = [value for value in spy_dates if value < latest]
        if not prior:
            raise ValueError("no completed SPY session is available")
        return max(prior)
    return latest


def _in_windows(fill_date: str, windows: tuple[tuple[str, str | None], ...]) -> bool:
    return any(start <= fill_date and (end is None or fill_date < end)
               for start, end in windows)


def build_latest_candidates(
    prices: dict[str, list[dict]], symbols: list[str], as_of: str,
) -> tuple[list[dict], int, list[str]]:
    """Return latest false-to-true candidates using completed common sessions."""
    spy = prices.get("SPY", [])
    spy_dates = {row["date"] for row in spy if row["date"] <= as_of}
    candidates: list[dict] = []
    qualifying = 0
    missing: list[str] = []
    for symbol in symbols:
        bars = prices.get(symbol, [])
        common = sorted(
            {row["date"] for row in bars if row["date"] <= as_of}.intersection(spy_dates))
        if not common or common[-1] != as_of:
            missing.append(symbol)
            continue
        current = calculate_current_buy_signal(bars, spy, as_of)
        if current is None:
            missing.append(symbol)
            continue
        is_true = bool(current["positive_relative_ma_slope"])
        qualifying += int(is_true)
        previous = calculate_current_buy_signal(bars, spy, common[-2]) if len(common) >= 2 else None
        if not is_true or (previous and previous["positive_relative_ma_slope"]):
            continue
        candidates.append({
            "symbol": symbol,
            "signal_date": as_of,
            "close": current["stock_signal_close"],
            "ma60": current["stock_ma_value"],
            "stock_slope_pct": current["stock_ma_slope_pct"],
            "spy_slope_pct": current["spy_ma_slope_pct"],
            "divergence_pct": current["relative_ma_slope_pct"],
        })
    candidates.sort(key=lambda row: (-row["divergence_pct"], row["symbol"]))
    return candidates, qualifying, missing


def replay_portfolio(
    prices: dict[str, list[dict]], membership: dict,
    sectors: dict[str, str], windows: tuple[tuple[str, str | None], ...],
    as_of: str,
) -> tuple[dict, list[dict]]:
    signals, _ = build_standalone_signals(
        prices, membership, sectors, SIGNAL_START, as_of,
        ma_period=MA_PERIOD, slope_sessions=SLOPE_SESSIONS)
    gated = [dict(row) for row in signals if _in_windows(row["fill_date"], windows)]
    cost_neutral_risk = 100 * (
        1 - (1 - INITIAL_STOP_PCT / 100) / (1 + ONE_WAY_COST))
    cfg = Config(
        commission_bps=5.0, slippage_bps=5.0,
        max_risk_pct=cost_neutral_risk)
    with patch("portfolio_backtest._candidate_signals", return_value=gated):
        portfolio = run_portfolio(
            {}, prices, cfg, exit_rule="armed_trailing_stop",
            exit_params={
                "trigger_r": TRIGGER_R,
                "trailing_pct": TRAILING_PCT,
                "holding_windows": windows,
                "holding_window_exit_timing": "window_end_open",
            },
            simulation_start_date=SIMULATION_START)
    return portfolio, gated


def _series_metrics(values: list[float], dates: list[str]) -> dict:
    if not values or len(values) != len(dates):
        return {}
    returns = [values[index] / values[index - 1] - 1
               for index in range(1, len(values)) if values[index - 1] > 0]
    years = max(
        (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days / 365.25,
        1 / 252,
    )
    total = values[-1] / values[0] - 1 if values[0] else 0.0
    cagr = (values[-1] / values[0]) ** (1 / years) - 1 if values[0] else 0.0
    peak = values[0]
    mdd = 0.0
    for value in values:
        peak = max(peak, value)
        mdd = min(mdd, value / peak - 1)
    if len(returns) > 1:
        mean = sum(returns) / len(returns)
        variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
        sharpe = mean / math.sqrt(variance) * math.sqrt(252) if variance > 0 else 0.0
    else:
        sharpe = 0.0
    return {"total": total, "cagr": cagr, "mdd": mdd, "sharpe": sharpe,
            "final": values[-1]}


def dashboard_metrics(portfolio: dict, prices: dict[str, list[dict]]) -> tuple[dict, dict]:
    curve = portfolio.get("equity_curve", [])
    dates = [row["date"] for row in curve]
    strategy = _series_metrics([float(row["equity"]) for row in curve], dates)
    spy_map = {row["date"]: float(row["close"]) for row in prices.get("SPY", [])}
    spy_values = [spy_map[value] for value in dates if value in spy_map]
    spy_dates = [value for value in dates if value in spy_map]
    benchmark = _series_metrics(spy_values, spy_dates)
    completed = [row for row in portfolio.get("trades", [])
                 if row.get("exit_reason") != "end_of_data"]
    wins = sum(float(row["net_return_pct"]) > 0 for row in completed)
    strategy["trades"] = len(completed)
    strategy["win_rate"] = wins / len(completed) if completed else None
    strategy["time_in_market"] = (
        sum(float(row["gross_exposure_pct"]) for row in curve) / len(curve) / 100
        if curve else None)
    return strategy, benchmark


def print_metrics(strategy: dict, benchmark: dict) -> None:
    rows = [
        ("Total Return", f"{strategy.get('total', 0):.1%}", f"{benchmark.get('total', 0):.1%}"),
        ("CAGR", f"{strategy.get('cagr', 0):.1%}", f"{benchmark.get('cagr', 0):.1%}"),
        ("Max Drawdown", f"{strategy.get('mdd', 0):.1%}", f"{benchmark.get('mdd', 0):.1%}"),
        ("Sharpe Ratio", f"{strategy.get('sharpe', 0):.2f}", f"{benchmark.get('sharpe', 0):.2f}"),
        ("Final Value", f"${strategy.get('final', 0):,.0f}", "—"),
        ("# Completed Trades", str(strategy.get("trades", 0)), "—"),
        ("Win Rate", (f"{strategy['win_rate']:.1%}"
                      if strategy.get("win_rate") is not None else "—"), "—"),
        ("Average Exposure", (f"{strategy['time_in_market']:.1%}"
                              if strategy.get("time_in_market") is not None else "—"), "100.0%"),
    ]
    header = f"{'Metric':<24}{'Strategy':>16}{'SPY':>16}"
    print(f"\n{'=' * len(header)}\n{header}\n{'=' * len(header)}")
    for label, strategy_value, benchmark_value in rows:
        print(f"  {label:<22}{strategy_value:>16}{benchmark_value:>16}")
    print("=" * len(header))


def _held_days(entry: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(entry)).days


def print_trades(trades: list[dict], limit: int | None) -> None:
    completed = [row for row in trades if row.get("exit_reason") != "end_of_data"]
    shown = completed if limit is None else completed[-limit:] if limit else []
    print(f"\n── Completed stock trades ({len(completed)} total; showing {len(shown)}) ──")
    if not shown:
        print("  None")
        return
    print(
        f"  {'#':>3}  {'Ticker':<7}{'Entry':<12}{'Exit':<12}{'Held':>6}"
        f"{'Entry $':>11}{'Exit $':>11}{'Net':>9}  Reason")
    print("  " + "─" * 91)
    start_number = len(completed) - len(shown) + 1
    for number, row in enumerate(shown, start_number):
        print(
            f"  {number:>3}  {row['symbol']:<7}{row['entry_date']:<12}"
            f"{row['exit_date']:<12}{_held_days(row['entry_date'], row['exit_date']):>6}"
            f"{float(row['entry_price']):>11.2f}{float(row['exit_price']):>11.2f}"
            f"{float(row['net_return_pct']):>+8.2f}%  {row['exit_reason']}")


def open_positions(portfolio: dict, prices: dict[str, list[dict]], as_of: str) -> list[dict]:
    output = []
    for row in portfolio.get("trades", []):
        if row.get("exit_reason") != "end_of_data":
            continue
        bars = {bar["date"]: bar for bar in prices.get(row["symbol"], [])}
        current_bar = bars.get(as_of)
        if current_bar is None:
            eligible = [bar for bar in prices.get(row["symbol"], []) if bar["date"] <= as_of]
            current_bar = eligible[-1] if eligible else None
        if current_bar is None:
            continue
        current = float(current_bar["close"])
        entry = float(row["entry_price"])
        output.append({
            **row,
            "current_date": current_bar["date"],
            "current_price": current,
            "current_net_return_pct": 100 * (current * (1 - ONE_WAY_COST) / entry - 1),
        })
    return sorted(output, key=lambda row: (row["entry_date"], row["symbol"]))


def print_open_positions(rows: list[dict], qqq: dict) -> None:
    print(f"\n── Open stock positions ({len(rows)}) ──")
    if not rows:
        print("  None")
        return
    print(
        f"  {'Ticker':<8}{'Entry':<12}{'Held':>6}{'Entry $':>11}{'Current $':>12}"
        f"{'Net':>9}{'Stop $':>11}{'Trail':>10}  Next action")
    print("  " + "─" * 104)
    for row in rows:
        if qqq["next_open_action"] == "SELL_NEXT_OPEN":
            action = "SELL — QQQ exit"
        else:
            action = "HOLD"
        trail = "ARMED" if row.get("trailing_armed_date") else "not armed"
        print(
            f"  {row['symbol']:<8}{row['entry_date']:<12}"
            f"{_held_days(row['entry_date'], row['current_date']):>6}"
            f"{float(row['entry_price']):>11.2f}{row['current_price']:>12.2f}"
            f"{row['current_net_return_pct']:>+8.2f}%{float(row['stop']):>11.2f}"
            f"{trail:>10}  {action}")


def select_next_orders(
    candidates: list[dict], positions: list[dict], sectors: dict[str, str],
    qqq: dict, stock_as_of: str,
) -> tuple[list[dict], str]:
    if not qqq["risk_on_after_next_open"]:
        return [], "QQQ will be OUT at the next open"
    if qqq["latest_date"] < stock_as_of:
        return [], (
            f"BLOCKED: QQQ breadth is stale ({qqq['latest_date']} < {stock_as_of})")
    held = {row["symbol"] for row in positions}
    sector_counts = Counter(sectors.get(row["symbol"], "Unknown") for row in positions)
    slots = max(0, Config().max_positions - len(positions))
    selected = []
    for candidate in candidates:
        if candidate["symbol"] in held or len(selected) >= slots:
            continue
        sector = sectors.get(candidate["symbol"], "Unknown")
        if sector_counts[sector] >= 3:  # 3 × 10% matches the fixed 30% sector cap.
            continue
        row = {**candidate, "sector": sector}
        selected.append(row)
        sector_counts[sector] += 1
    return selected, "eligible for the next US session open"


def print_candidates(
    candidates: list[dict], selected: list[dict], qualifying: int,
    missing: list[str], reason: str,
) -> None:
    selected_symbols = {row["symbol"] for row in selected}
    print("\n── Latest MA60/Slope10 close-confirmed signals ──")
    print(
        f"  Qualifying now: {qualifying} | Fresh false→true: {len(candidates)} | "
        f"Missing/stale: {len(missing)}")
    print(f"  Order status: {reason}")
    if not candidates:
        print("  No fresh candidates.")
        return
    print(
        f"\n  {'Ticker':<8}{'Sector':<24}{'Close':>10}{'MA60':>10}"
        f"{'Stock slope':>14}{'SPY slope':>12}{'Divergence':>13}  Action")
    print("  " + "─" * 112)
    for row in candidates:
        action = "BUY NEXT OPEN" if row["symbol"] in selected else "WATCH / BLOCKED"
        print(
            f"  {row['symbol']:<8}{row.get('sector', 'Unknown'):<24}"
            f"{row['close']:>10.2f}{row['ma60']:>10.2f}"
            f"{row['stock_slope_pct']:>+13.2f}%{row['spy_slope_pct']:>+11.2f}%"
            f"{row['divergence_pct']:>+12.2f}pp  {action}")


def print_qqq_state(qqq: dict, stock_as_of: str) -> None:
    state = "IN / RISK-ON" if qqq["risk_on_at_latest_open"] else "OUT / RISK-OFF"
    next_state = "IN" if qqq["risk_on_after_next_open"] else "OUT"
    print("\n── QQQ breadth state ──")
    print(f"  Source       : {qqq['source']}")
    print(f"  QQQ data date: {qqq['latest_date']}")
    print(f"  Stock as-of  : {stock_as_of}")
    print(f"  Current      : {state}")
    print(f"  Open since   : {qqq.get('open_since') or '—'}")
    print(f"  Next open    : {qqq['next_open_action']} → state {next_state}")
    if qqq["latest_date"] < stock_as_of:
        print("  WARNING      : QQQ breadth data lag the stock-price date")


def main() -> None:
    args = parse_arguments()
    args.data_dir = args.data_dir.expanduser().resolve()
    args.seed_csv = args.seed_csv.expanduser().resolve()
    store = ensure_price_store(args.data_dir, args.seed_csv)
    if args.no_fetch:
        manifest = {
            "updated_at": None, "source": "saved local data (--no-fetch)",
            "store": str(store), "failed_symbols": [],
        }
    else:
        manifest = refresh_price_store(args, store)

    print(f"\nLoading {store} ...")
    client = CSVClient(str(store))
    if client.synthetic_benchmark:
        raise SystemExit("real SPY is required; synthetic benchmark rejected")
    prices = {
        row["symbol"]: list(reversed(client.get_historical_prices(
            row["symbol"], days=100_000)["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]
    }
    spy_dates = [row["date"] for row in prices["SPY"]]
    as_of = args.as_of or latest_completed_spy_date(spy_dates)
    if as_of not in set(spy_dates):
        raise SystemExit(f"--as-of {as_of} is not a SPY session in the saved data")

    if args.force_qqq_state:
        qqq = forced_qqq_state(args.force_qqq_state, as_of)
    else:
        print(f"Reading QQQ state from {args.qqq_repo} ...")
        qqq = load_qqq_state(args.qqq_repo, args.qqq_python, as_of)
    windows = tuple((str(start), str(end) if end else None)
                    for start, end in qqq["windows"])

    membership = load_membership(args.membership_csv)
    sectors = _sector_map(args.sector_json)
    current_symbols = load_symbols(args.constituents)
    candidates, qualifying, missing = build_latest_candidates(
        prices, current_symbols, as_of)
    for row in candidates:
        row["sector"] = sectors.get(row["symbol"], "Unknown")

    portfolio, signals = replay_portfolio(
        prices, membership, sectors, windows, as_of)
    strategy_metrics, benchmark_metrics = dashboard_metrics(portfolio, prices)
    positions = open_positions(portfolio, prices, as_of)
    selected, order_reason = select_next_orders(
        candidates, positions, sectors, qqq, as_of)

    print("\nNASDAQ / S&P 500 MA60 Relative-Slope Strategy — Daily Dashboard")
    print("=" * 72)
    print(
        f"BUY : close > MA{MA_PERIOD}, MA{MA_PERIOD} slope({SLOPE_SESSIONS}) > 0 "
        "and > SPY; false→true; next open")
    print(
        f"SELL: {INITIAL_STOP_PCT:.0f}% hard stop; arm at +{TRIGGER_R:.0f}R; "
        f"{TRAILING_PCT:.0f}% close trail; QQQ exit-open liquidation")
    print("STATUS: EXPERIMENTAL / VALIDATION FAILED / Backtest Score 20/100 (Reject)")
    print(f"Price store : {store}")
    print(f"Latest file : {args.data_dir / 'latest_prices.csv'}")
    print(f"Stock as-of : {as_of} | Historical signals: {len(signals)}")
    if manifest.get("failed_symbols"):
        print(f"Data warning: {len(manifest['failed_symbols'])} Yahoo symbols failed")

    print_qqq_state(qqq, as_of)
    print_metrics(strategy_metrics, benchmark_metrics)
    trade_limit = None if args.all_trades else args.recent_trades
    print_trades(portfolio.get("trades", []), trade_limit)
    print_open_positions(positions, qqq)
    print_candidates(candidates, selected, qualifying, missing, order_reason)

    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "classification": "EXPERIMENTAL_VALIDATION_FAILED_NOT_LIVE_ADVICE",
        "stock_as_of": as_of,
        "price_store": str(store),
        "qqq": qqq,
        "strategy_metrics": strategy_metrics,
        "benchmark_metrics": benchmark_metrics,
        "completed_trades": len([
            row for row in portfolio.get("trades", [])
            if row.get("exit_reason") != "end_of_data"]),
        "open_positions": positions,
        "fresh_candidates": candidates,
        "next_open_orders": selected,
        "qualifying_tickers": qualifying,
        "missing_or_stale_tickers": missing,
        "price_update": manifest,
    }
    _atomic_json(args.data_dir / "latest_strategy_result.json", payload)
    print(f"\nMachine result: {args.data_dir / 'latest_strategy_result.json'}")


if __name__ == "__main__":
    main()
