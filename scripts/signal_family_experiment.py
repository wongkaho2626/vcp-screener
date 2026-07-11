#!/usr/bin/env python3
"""Signal-family experiment — test three non-VCP entry families on the same
infrastructure (offline CSV, excess vs SPY over each trade's own dates,
fold split + outlier trims). Prespecified BEFORE running to avoid the
multiple-testing trap: one canonical parameterisation per family, no grids.

Families (all long-only, close-based fills, no costs):
  xs-momentum : classic 12-1 cross-sectional momentum. At each month-end,
                rank names by close[t-21]/close[t-252]-1, buy the top decile,
                exit at the next month-end. Primary t-stat is computed on the
                MONTHLY portfolio excess series (per-trade t is inflated by
                cross-sectional correlation).
  mean-rev    : short-term reversal in an uptrend. close > SMA200 and
                Wilder RSI(2) < 10 → buy the close; exit when RSI(2) > 70,
                on a close 8% below entry, or after 10 bars.
  52w-high    : George-Hwang proximity. close within 2% of the 252-bar
                rolling high and > SMA200 → buy the close; exits identical
                to the VCP baseline (-8% close-based stop + 60-bar timeout),
                20-bar re-entry cooldown per symbol.

Usage:
    python3 scripts/signal_family_experiment.py --price-csv SP500_Historical_Data.csv
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics as st
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from csv_client import CSVClient  # noqa: E402
from trade_simulator import _bootstrap_ci, _t_stat, _to_chrono, simulate_exit  # noqa: E402


# ---------------------------------------------------------------------------
# Pure signal functions
# ---------------------------------------------------------------------------

def wilder_rsi(closes: list[float], period: int = 2) -> list[float | None]:
    """Wilder-smoothed RSI; None until ``period`` deltas have accrued."""
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains, losses = [], []
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_g, avg_l = st.fmean(gains), st.fmean(losses)

    def to_rsi(g: float, lo: float) -> float:
        if lo == 0:
            return 100.0
        return 100.0 - 100.0 / (1.0 + g / lo)

    out[period] = to_rsi(avg_g, avg_l)
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        avg_g = (avg_g * (period - 1) + max(d, 0.0)) / period
        avg_l = (avg_l * (period - 1) + max(-d, 0.0)) / period
        out[i] = to_rsi(avg_g, avg_l)
    return out


def _sma_series(closes: list[float], period: int) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    run = 0.0
    for i, c in enumerate(closes):
        run += c
        if i >= period:
            run -= closes[i - period]
        if i >= period - 1:
            out[i] = run / period
    return out


def mean_reversion_trades(
    chrono: list[dict], ma_period: int = 200, rsi_period: int = 2,
    entry_th: float = 10.0, exit_th: float = 70.0, max_hold: int = 10,
    stop_pct: float = 8.0,
) -> list[dict]:
    """Oversold-in-uptrend walker. Returns [{entry_idx, exit_idx, reason}]."""
    closes = [b["close"] for b in chrono]
    rsi = wilder_rsi(closes, rsi_period)
    sma = _sma_series(closes, ma_period)
    trades: list[dict] = []
    i = ma_period
    last = len(chrono) - 1
    while i <= last:
        r, m = rsi[i], sma[i]
        if r is None or m is None or closes[i] <= m or r >= entry_th:
            i += 1
            continue
        entry = closes[i]
        stop = entry * (1 - stop_pct / 100)
        exit_idx, reason = None, None
        for j in range(i + 1, last + 1):
            if closes[j] < stop:
                exit_idx, reason = j, "stop"
            elif rsi[j] is not None and rsi[j] > exit_th:
                exit_idx, reason = j, "rsi"
            elif j - i >= max_hold:
                exit_idx, reason = j, "timeout"
            if exit_idx is not None:
                break
        if exit_idx is None:
            break  # ran off the data with an open trade — drop it
        trades.append({"entry_idx": i, "exit_idx": exit_idx, "reason": reason})
        i = exit_idx + 1
    return trades


def near_high_trades(
    chrono: list[dict], lookback: int = 252, within_pct: float = 2.0,
    ma_period: int = 200, stop_pct: float = 8.0, max_hold: int = 60,
    cooldown: int = 20,
) -> list[dict]:
    """52-week-high proximity walker; exits via simulate_exit (VCP baseline).
    Returns [{entry_idx, exit_idx, reason, stop_price}]."""
    closes = [b["close"] for b in chrono]
    sma = _sma_series(closes, ma_period)
    trades: list[dict] = []
    i = max(lookback, ma_period) - 1
    last = len(chrono) - 1
    next_ok = 0
    while i <= last:
        if i < next_ok:
            i += 1
            continue
        m = sma[i]
        hi = max(closes[i - lookback + 1 : i + 1])
        if m is None or closes[i] <= m or closes[i] < hi * (1 - within_pct / 100):
            i += 1
            continue
        stop = closes[i] * (1 - stop_pct / 100)
        ex = simulate_exit(chrono, i, stop, max_hold)
        if ex is None:
            break
        exit_idx = i + ex["hold_bars"]
        trades.append({"entry_idx": i, "exit_idx": exit_idx,
                       "reason": ex["exit_reason"], "stop_price": stop})
        next_ok = exit_idx + cooldown + 1
        i = exit_idx + 1
    return trades


def momentum_score(closes: list[float], i: int, lb_long: int = 252,
                   lb_skip: int = 21) -> float | None:
    """12-1 momentum: return from t-lb_long to t-lb_skip. None w/o history."""
    if i < lb_long:
        return None
    base = closes[i - lb_long]
    if base <= 0:
        return None
    return closes[i - lb_skip] / base - 1


def rank_momentum(scores: dict[str, float], top_frac: float = 0.1) -> list[str]:
    """Top ``top_frac`` symbols by score (ceil), best first."""
    n = math.ceil(len(scores) * top_frac)
    return sorted(scores, key=lambda s: scores[s], reverse=True)[:n]


def month_end_indices(dates: list[str]) -> list[int]:
    """Indices of the last trading day of each month; the final bar is
    excluded (its month may be incomplete and there is no forward bar)."""
    return [i for i in range(len(dates) - 1) if dates[i][:7] != dates[i + 1][:7]]


# ---------------------------------------------------------------------------
# Stats & reporting
# ---------------------------------------------------------------------------

def _fold(rows: list[dict], pred) -> list[float]:
    return [r["exc"] for r in rows if pred(r["year"])]


def _trim_mean_t(exc: list[float], drop: int) -> tuple[float, float]:
    kept = sorted(exc)[: len(exc) - drop] if drop < len(exc) else []
    if len(kept) < 6:
        return float("nan"), float("nan")
    return round(st.fmean(kept), 2), _t_stat(kept)


def _clustered_t(rows: list[dict]) -> tuple[float | None, int]:
    """t-stat on the entry-month mean-excess series — the primary
    significance measure; per-trade t is inflated by same-month
    cross-sectional correlation (market-wide RSI triggers, shared
    rebalance dates)."""
    groups: dict[str, list[float]] = {}
    for r in rows:
        groups.setdefault(r["date"][:7], []).append(r["exc"])
    means = [st.fmean(v) for v in groups.values()]
    if len(means) < 6:
        return None, len(means)
    return _t_stat(means), len(means)


def summarize(label: str, rows: list[dict], md: list[str]) -> None:
    exc = [r["exc"] for r in rows]
    if len(exc) < 6:
        md.append(f"| {label} | too few trades ({len(exc)}) |" + " |" * 10)
        return
    mean_e, t_e, ci = round(st.fmean(exc), 2), _t_stat(exc), _bootstrap_ci(exc)
    med = round(st.median(exc), 2)
    win = round(sum(1 for e in exc if e > 0) / len(exc) * 100, 1)
    a = _fold(rows, lambda y: y <= "2020")
    b = _fold(rows, lambda y: y >= "2021")
    fold_a = f"{st.fmean(a):.2f} (t {_t_stat(a)}, n {len(a)})" if len(a) >= 6 else "—"
    fold_b = f"{st.fmean(b):.2f} (t {_t_stat(b)}, n {len(b)})" if len(b) >= 6 else "—"
    d5m, d5t = _trim_mean_t(exc, 5)
    d10m, d10t = _trim_mean_t(exc, 10)
    ct, months = _clustered_t(rows)
    t_primary = f"{ct} (n {months} mo)" if ct is not None else "—"
    print(f"{label:<12} n {len(exc):>5}  mean {mean_e:>7}  t/mo {t_primary:<16} "
          f"t/trade {t_e:<7} med {med:>7}  win {win}%")
    md.append(
        f"| {label} | {len(exc)} | {mean_e}% | {t_primary} | {t_e} | {ci} | "
        f"{med}% | {win}% | {fold_a} | {fold_b} | {d5m}% (t {d5t}) | "
        f"{d10m}% (t {d10t}) |"
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> None:
    if args.price_csv:
        client = CSVClient(args.price_csv)
        sleep_secs, fetch_days = 0.0, 10**6
    else:
        import time  # noqa: PLC0415 — only the yfinance path throttles

        from yf_client import YFClient  # noqa: PLC0415 — optional dependency

        client = YFClient()
        sleep_secs, fetch_days = args.sleep_secs, 3800
    print(f"data_source: {client.get_api_stats()['data_source']}")

    if args.symbols_json:
        with open(args.symbols_json) as f:
            raw = json.load(f)
        symbols = sorted(d["symbol"] if isinstance(d, dict) else d for d in raw)
    else:
        symbols = [d["symbol"] for d in client.get_constituents()]

    spy_chrono, spy_idx = _to_chrono(
        client.get_historical_prices("SPY", days=fetch_days)["historical"])
    print(f"Universe: {len(symbols)} names | SPY calendar: {len(spy_chrono)} bars")

    def spy_ret(d1: str, d2: str) -> float | None:
        si, sj = spy_idx.get(d1), spy_idx.get(d2)
        if si is None or sj is None or sj <= si:
            return None
        return (spy_chrono[sj]["close"] / spy_chrono[si]["close"] - 1) * 100

    bars: dict[str, tuple] = {}
    for n, sym in enumerate(symbols, 1):
        try:
            hist = client.get_historical_prices(sym, days=fetch_days)
            bars[sym] = _to_chrono((hist or {}).get("historical") or [])
        except Exception:  # noqa: BLE001 — skip bad tickers, keep the run alive
            bars[sym] = ([], {})
        if sleep_secs > 0:
            if n % 100 == 0:
                print(f"  fetched {n}/{len(symbols)}", flush=True)
            if n < len(symbols):
                time.sleep(sleep_secs)

    def excess_row(chrono: list[dict], i: int, j: int) -> dict | None:
        d1, d2 = chrono[i]["date"], chrono[j]["date"]
        sr = spy_ret(d1, d2)
        if sr is None:
            return None
        ret = (chrono[j]["close"] / chrono[i]["close"] - 1) * 100
        return {"exc": ret - sr, "year": d1[:4], "date": d1}

    src = os.path.basename(args.price_csv or args.symbols_json or "yfinance")
    md = ["# Signal-Family Experiment", "",
          f"Universe: {len(symbols)} names ({src}) | "
          "excess vs SPY over each trade's own dates; close fills; no costs. "
          "Prespecified: one parameterisation per family, no grids.", "",
          "| Family | N | Mean excess | t (monthly) | t (trade) | 95% CI | "
          "Median | Win% | Fold ≤2020 | Fold ≥2021 | drop-top-5 | drop-top-10 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]

    # --- xs-momentum -------------------------------------------------------
    rebal = month_end_indices([b["date"] for b in spy_chrono])
    mom_rows: list[dict] = []
    for k in range(len(rebal) - 1):
        d_in = spy_chrono[rebal[k]]["date"]
        d_out = spy_chrono[rebal[k + 1]]["date"]
        scores: dict[str, float] = {}
        for sym in symbols:
            chrono, idx_map = bars[sym]
            i = idx_map.get(d_in)
            if i is None or idx_map.get(d_out) is None:
                continue
            s = momentum_score([b["close"] for b in chrono], i)
            if s is not None:
                scores[sym] = s
        if len(scores) < 50:
            continue
        for sym in rank_momentum(scores, top_frac=0.1):
            chrono, idx_map = bars[sym]
            row = excess_row(chrono, idx_map[d_in], idx_map[d_out])
            if row is not None:
                mom_rows.append(row)
    summarize("xs-momentum", mom_rows, md)

    # --- mean-rev + 52w-high (per-symbol walks) ----------------------------
    mr_rows: list[dict] = []
    nh_rows: list[dict] = []
    for n, sym in enumerate(symbols, 1):
        chrono, _ = bars[sym]
        if len(chrono) < 260:
            continue
        for t in mean_reversion_trades(chrono):
            row = excess_row(chrono, t["entry_idx"], t["exit_idx"])
            if row is not None:
                mr_rows.append(row)
        for t in near_high_trades(chrono):
            row = excess_row(chrono, t["entry_idx"], t["exit_idx"])
            if row is not None:
                nh_rows.append(row)
        if n % 100 == 0:
            print(f"  {n}/{len(symbols)} symbols walked", flush=True)
    summarize("mean-rev", mr_rows, md)
    summarize("52w-high", nh_rows, md)

    md += ["", "## Notes", "",
           "- t (monthly) clusters trades by entry month and tests the monthly "
           "mean series — the primary measure; t (trade) is inflated by "
           "cross-sectional correlation and shown for reference only.",
           "- Universe is survivorship-biased (current constituents only) — "
           "all numbers are optimistic ceilings, same caveat as the VCP runs.",
           "- VCP baseline for reference: S&P mean excess −0.53% (t −0.86), "
           "R2K −0.46% (t −0.92)."]

    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = os.path.join(args.output_dir, f"signal_family_{ts}.md")
    with open(path, "w") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nMarkdown: {path}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Three prespecified non-VCP signal families vs SPY")
    ap.add_argument("--price-csv",
                    help="OHLCV CSV (Ticker,Date,O,H,L,C,Adj Close,Volume); "
                         "omit to fetch via yfinance")
    ap.add_argument("--symbols-json",
                    help="Universe override: JSON list of symbols or "
                         '{"symbol": ...} dicts (required without --price-csv)')
    ap.add_argument("--sleep-secs", type=float, default=0.25,
                    help="Throttle between yfinance fetches")
    ap.add_argument("--output-dir", default="backtests/")
    args = ap.parse_args()
    if not args.price_csv and not args.symbols_json:
        ap.error("need --price-csv or --symbols-json (universe source)")
    run(args)


if __name__ == "__main__":
    main()
