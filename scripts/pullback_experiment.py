#!/usr/bin/env python3
"""Pullback-entry experiment — buy the retest instead of the breakout.

For every breakout detection in one or more ``vcp_backtest_*.json`` reports,
compares two entries on the SAME pattern:

  breakout leg : close of the breakout bar (the existing trade_simulator rule,
                 including the max-extension skip)
  pullback leg : after the breakout, wait up to ``--window`` bars for price to
                 pull back and hold — either a pivot retest (low within
                 ``--tolerance-pct`` of the pivot, close at/above it:
                 resistance-turned-support) or an MA touch (low <= SMA, close
                 at/above it; strict touch because the MA lags price).
                 A close below the pattern stop while waiting kills the setup;
                 no pullback inside the window means the trade is missed.

Both legs exit identically: hard stop max(contraction low, entry - 8%) +
60-bar timeout. Reports per-variant fill rates, excess vs SPY, and a PAIRED
comparison (pullback minus breakout on the same detection) — the cleanest
answer to "does entering on the pullback beat chasing the breakout?".

Usage:
    python3 scripts/pullback_experiment.py backtests/.../vcp_backtest_X.json \
        [more.json ...] --price-csv SP500_Historical_Data.csv
"""

from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trade_simulator import _bootstrap_ci, _t_stat, _to_chrono, simulate_exit  # noqa: E402
from yf_client import YFClient  # noqa: E402


def plan_pullback_entry(
    chrono: list[dict], bo_idx: int, pivot: float, stop: float,
    tolerance_pct: float = 2.0, window: int = 15, ma_period: int | None = None,
) -> dict | None:
    """First post-breakout bar whose low touches the reference level and whose
    close holds it. Pure. Returns ``{"entry_idx", "entry_price"}`` or None
    (no pullback in the window, or the pattern stop was broken while waiting).

    Pivot mode allows a ``tolerance_pct`` band above the pivot; MA mode uses a
    strict touch (low <= SMA) because the lagging MA sits below recent closes.
    """
    end = min(bo_idx + 1 + window, len(chrono))
    for j in range(bo_idx + 1, end):
        close = chrono[j]["close"]
        if close < stop:
            return None
        if ma_period is not None:
            if j + 1 < ma_period:
                continue
            ref = st.fmean(b["close"] for b in chrono[j - ma_period + 1 : j + 1])
            touch_limit = ref
        else:
            ref = pivot
            touch_limit = pivot * (1 + tolerance_pct / 100)
        low = chrono[j].get("low", close)
        if low <= touch_limit and close >= ref:
            return {"entry_idx": j, "entry_price": close}
    return None


VARIANTS = [
    ("pivot retest 15d", {"window": 15}),
    ("pivot retest 30d", {"window": 30}),
    ("MA10 touch 15d", {"window": 15, "ma_period": 10}),
    ("MA20 touch 15d", {"window": 15, "ma_period": 20}),
]


def summarize(exc: list[float]) -> dict | None:
    exc = [e for e in exc if e is not None]
    if len(exc) < 6:
        return None
    return {
        "n": len(exc),
        "mean": round(st.fmean(exc), 2),
        "t": _t_stat(exc),
        "ci": _bootstrap_ci(exc),
        "median": round(st.median(exc), 2),
        "win": round(sum(1 for e in exc if e > 0) / len(exc) * 100, 1),
    }


def _fmt(v):
    return f"{v}" if v is not None else "—"


def run(args: argparse.Namespace) -> None:
    detections_by_ticker: dict[str, list[dict]] = {}
    for path in args.backtest_jsons:
        payload = json.load(open(path))
        for sym, dets in (payload.get("detections_by_ticker") or {}).items():
            detections_by_ticker.setdefault(sym, []).extend(dets)

    if args.price_csv:
        from csv_client import CSVClient  # noqa: PLC0415 — optional offline path

        client = CSVClient(args.price_csv)
        sleep_secs = 0.0
    else:
        client = YFClient()
        sleep_secs = args.sleep_secs

    fetch_days = 2520 + 500
    print("Fetching SPY...", end=" ", flush=True)
    spy_chrono, spy_idx = _to_chrono(
        client.get_historical_prices("SPY", days=fetch_days)["historical"]
    )
    print(f"OK ({len(spy_chrono)} bars)")

    def spy_ret(entry_date: str, exit_date: str) -> float | None:
        si, sj = spy_idx.get(entry_date), spy_idx.get(exit_date)
        if si is None or sj is None or sj <= si:
            return None
        return (spy_chrono[sj]["close"] / spy_chrono[si]["close"] - 1) * 100

    def leg_excess(chrono: list[dict], entry_idx: int, entry_price: float,
                   pattern_stop: float | None) -> float | None:
        stop = max(pattern_stop or 0, entry_price * (1 - args.max_risk_pct / 100))
        ex = simulate_exit(chrono, entry_idx, stop, args.max_hold_bars)
        if ex is None:
            return None
        ret = (ex["exit_price"] / entry_price - 1) * 100
        sr = spy_ret(chrono[entry_idx]["date"], ex["exit_date"])
        return ret - sr if sr is not None else None

    results = {label: {"exc": [], "pairs": [], "no_fill": 0, "invalidated_or_missed": 0}
               for label, _ in VARIANTS}
    breakout_exc: list[float] = []
    n_detections = 0

    symbols = sorted(detections_by_ticker)
    for i, sym in enumerate(symbols, 1):
        try:
            hist = client.get_historical_prices(sym, days=fetch_days)
        except Exception:  # noqa: BLE001 — skip bad tickers, keep the run alive
            continue
        chrono, idx_map = _to_chrono((hist or {}).get("historical") or [])
        for det in detections_by_ticker[sym]:
            fo = det.get("forward_outcome") or {}
            pivot, pattern_stop = fo.get("pivot_price"), fo.get("stop_price")
            if fo.get("outcome_type") != "breakout" or not pivot:
                continue
            bo_idx = idx_map.get(fo.get("exit_date"))
            if bo_idx is None:
                continue
            n_detections += 1

            bo_price = fo.get("exit_price") or chrono[bo_idx]["close"]
            extension_pct = (bo_price / pivot - 1) * 100
            bo_exc = (
                leg_excess(chrono, bo_idx, bo_price, pattern_stop)
                if extension_pct <= args.max_extension_pct
                else None
            )
            if bo_exc is not None:
                breakout_exc.append(bo_exc)

            wait_stop = pattern_stop or pivot * (1 - args.max_risk_pct / 100)
            for label, kwargs in VARIANTS:
                plan = plan_pullback_entry(
                    chrono, bo_idx, pivot, wait_stop,
                    tolerance_pct=args.tolerance_pct, **kwargs,
                )
                if plan is None:
                    results[label]["invalidated_or_missed"] += 1
                    continue
                pb_exc = leg_excess(chrono, plan["entry_idx"], plan["entry_price"],
                                    pattern_stop)
                if pb_exc is None:
                    results[label]["no_fill"] += 1
                    continue
                results[label]["exc"].append(pb_exc)
                if bo_exc is not None:
                    results[label]["pairs"].append(pb_exc - bo_exc)
        if sleep_secs > 0 and i < len(symbols):
            time.sleep(sleep_secs)

    md = ["# Pullback-Entry Experiment", "",
          f"Detections (breakout outcomes): {n_detections} | breakout-leg trades: "
          f"{len(breakout_exc)} | exits: stop + {args.max_hold_bars}-bar timeout", ""]

    hdr = (f"{'Entry':<20}{'N':>5}{'fill%':>7}{'meanExc':>9}{'t':>7}{'medExc':>9}"
           f"{'win%':>7}{'pairΔ':>8}{'t(Δ)':>7}")
    print("\n" + "=" * 86)
    print("PULLBACK vs BREAKOUT — same patterns, same exit rule (excess vs SPY, %)")
    print("=" * 86)
    print(hdr)
    b = summarize(breakout_exc)
    print(f"{'breakout (baseline)':<20}{b['n']:>5}{'—':>7}{_fmt(b['mean']):>9}"
          f"{_fmt(b['t']):>7}{_fmt(b['median']):>9}{_fmt(b['win']):>7}{'—':>8}{'—':>7}")
    md += ["| Entry | N | Fill% | Mean excess | t | Median | Win% | Paired Δ | t(Δ) |",
           "|---|---|---|---|---|---|---|---|---|",
           f"| breakout (baseline) | {b['n']} | — | {b['mean']}% | {b['t']} | "
           f"{b['median']}% | {b['win']}% | — | — |"]
    for label, _ in VARIANTS:
        r = results[label]
        s = summarize(r["exc"])
        fill = round(len(r["exc"]) / n_detections * 100, 1) if n_detections else 0
        pair_mean = round(st.fmean(r["pairs"]), 2) if len(r["pairs"]) >= 6 else None
        pair_t = _t_stat(r["pairs"]) if len(r["pairs"]) >= 6 else None
        if s:
            print(f"{label:<20}{s['n']:>5}{fill:>7}{_fmt(s['mean']):>9}{_fmt(s['t']):>7}"
                  f"{_fmt(s['median']):>9}{_fmt(s['win']):>7}{_fmt(pair_mean):>8}"
                  f"{_fmt(pair_t):>7}")
            md.append(f"| {label} | {s['n']} | {fill}% | {s['mean']}% | {s['t']} | "
                      f"{s['median']}% | {s['win']}% | {_fmt(pair_mean)} | {_fmt(pair_t)} |")
        else:
            print(f"{label:<20} (fewer than 6 fills)")
            md.append(f"| {label} | <6 fills | | | | | | | |")

    md += ["", "## Notes", "",
           "- Paired Δ = pullback excess minus breakout excess on the SAME detection",
           "  (only where both legs traded); positive = pullback entry better.",
           "- Fill% = pullback fills / all breakout detections. Missed trades are the",
           "  structural cost of waiting for a retest.",
           "- No transaction costs; close-based fills.", ""]

    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    md_path = os.path.join(args.output_dir, f"vcp_pullback_experiment_{ts}.md")
    with open(md_path, "w") as f:
        f.write("\n".join(md))
    print(f"\nMarkdown: {md_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Pullback-entry vs breakout-entry experiment")
    ap.add_argument("backtest_jsons", nargs="+", help="vcp_backtest_*.json report(s)")
    ap.add_argument("--price-csv", help="Offline OHLCV CSV (CSVClient); else yfinance")
    ap.add_argument("--tolerance-pct", type=float, default=2.0)
    ap.add_argument("--max-extension-pct", type=float, default=5.0)
    ap.add_argument("--max-risk-pct", type=float, default=8.0)
    ap.add_argument("--max-hold-bars", type=int, default=60)
    ap.add_argument("--output-dir", default="backtests/")
    ap.add_argument("--sleep-secs", type=float, default=0.3)
    run(ap.parse_args())


if __name__ == "__main__":
    main()
