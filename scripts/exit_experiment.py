#!/usr/bin/env python3
"""Exit-rule experiment (backtest-analyst recommendation 2).

Holds the ENTRY set fixed (the accepted trades in a ``vcp_trades_*.json``) and
re-simulates only the EXIT under several rules, to test whether a trailing stop
"lets winners run while cutting the bleed" better than the fixed timeout — the
recommendation aimed at the negative median trade.

Each ticker's bars are fetched once; every exit config is simulated over the
same entries. Reports mean AND median excess-vs-SPY (median is the target
metric), win rate, profit factor, worst trade, and exit-reason mix.

Usage:
    python3 scripts/exit_experiment.py backtests/vcp_trades_YYYY.json
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

from trade_simulator import _to_chrono, compute_trade_stats, simulate_exit  # noqa: E402
from yf_client import YFClient  # noqa: E402

# (label, trail_pct)  — None = baseline fixed-timeout exit
CONFIGS = [
    ("timeout (baseline)", None),
    ("trail 10%", 10.0),
    ("trail 15%", 15.0),
    ("trail 20%", 20.0),
    ("trail 25%", 25.0),
]


def _fmt(v, s=""):
    return f"{v}{s}" if v is not None else "—"


def run(args) -> None:
    payload = json.load(open(args.trades_json))
    trades = payload["trades"]
    max_hold = (payload.get("metadata") or {}).get("max_hold_bars", 60)
    fetch_days = 2520 + 500

    client = YFClient()
    print("Fetching SPY...", end=" ", flush=True)
    spy_chrono, spy_idx = _to_chrono(client.get_historical_prices("SPY", days=fetch_days)["historical"])
    print(f"OK ({len(spy_chrono)} bars)")

    symbols = sorted({t["symbol"] for t in trades})
    bars: dict[str, tuple] = {}
    for i, sym in enumerate(symbols, 1):
        print(f"[{i}/{len(symbols)}] {sym}", end="  ", flush=True)
        try:
            hist = client.get_historical_prices(sym, days=fetch_days)
            bars[sym] = _to_chrono((hist or {}).get("historical") or [])
        except Exception as e:  # noqa: BLE001
            print(f"(err {e})", end="  ")
            bars[sym] = ([], {})
        if i % 6 == 0:
            print()
        if args.sleep_secs > 0 and i < len(symbols):
            time.sleep(args.sleep_secs)
    print()

    def spy_ret(entry_date, exit_date):
        si, sj = spy_idx.get(entry_date), spy_idx.get(exit_date)
        return (spy_chrono[sj]["close"] / spy_chrono[si]["close"] - 1) * 100 \
            if si is not None and sj is not None and sj > si else None

    results = []
    for label, trail in CONFIGS:
        sim_trades = []
        for t in trades:
            chrono, idx_map = bars.get(t["symbol"], ([], {}))
            start = idx_map.get(t["entry_date"])
            if start is None:
                continue
            ex = simulate_exit(chrono, start, t["stop_price"], max_hold, trail_pct=trail)
            if ex is None:
                continue
            ret = (ex["exit_price"] / t["entry_price"] - 1) * 100
            sr = spy_ret(t["entry_date"], ex["exit_date"])
            sim_trades.append({
                "ret_pct": round(ret, 2),
                "excess_vs_spy_pct": round(ret - sr, 2) if sr is not None else None,
                "hold_bars": ex["hold_bars"], "exit_reason": ex["exit_reason"],
            })
        stats = compute_trade_stats(sim_trades, skips={})
        exc = [x["excess_vs_spy_pct"] for x in sim_trades if x["excess_vs_spy_pct"] is not None]
        rets = [x["ret_pct"] for x in sim_trades]
        reasons = {}
        for x in sim_trades:
            reasons[x["exit_reason"]] = reasons.get(x["exit_reason"], 0) + 1
        results.append({
            "label": label, "n": len(sim_trades),
            "mean_exc": stats["primary_mean_excess_vs_spy_pct"],
            "t_exc": stats["primary_t_stat_excess"],
            "median_exc": round(st.median(exc), 2) if exc else None,
            "median_ret": round(st.median(rets), 2) if rets else None,
            "win": stats["win_rate_pct"], "pf": stats["profit_factor"],
            "worst": stats["worst_trade_pct"], "avg_hold": stats["avg_hold_bars"],
            "reasons": reasons,
        })

    print("\n" + "=" * 90)
    print("EXIT-RULE EXPERIMENT — same entries, different exits (target metric: median)")
    print("=" * 90)
    hdr = f"{'Exit rule':<20}{'N':>4}{'meanExc':>9}{'t':>6}{'medExc':>8}{'medRet':>8}{'win%':>7}{'PF':>6}{'worst':>8}{'hold':>6}"
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        print(f"{r['label']:<20}{r['n']:>4}{_fmt(r['mean_exc']):>9}{_fmt(r['t_exc']):>6}"
              f"{_fmt(r['median_exc']):>8}{_fmt(r['median_ret']):>8}{_fmt(r['win']):>7}"
              f"{_fmt(r['pf']):>6}{_fmt(r['worst']):>8}{_fmt(r['avg_hold']):>6}")
    for r in results:
        print(f"  {r['label']:<20} exits: {r['reasons']}")

    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    md = os.path.join(args.output_dir, f"vcp_exit_experiment_{ts}.md")
    with open(md, "w") as f:
        f.write("# VCP Exit-Rule Experiment\n\nSame entries, different exits. Target metric: median trade.\n\n")
        f.write("| Exit rule | N | Mean excess | t | Median excess | Median ret | Win% | PF | Worst | Avg hold |\n|---|---|---|---|---|---|---|---|---|---|\n")
        for r in results:
            f.write(f"| {r['label']} | {r['n']} | {_fmt(r['mean_exc'],'%')} | {_fmt(r['t_exc'])} | "
                    f"{_fmt(r['median_exc'],'%')} | {_fmt(r['median_ret'],'%')} | {_fmt(r['win'],'%')} | "
                    f"{_fmt(r['pf'])} | {_fmt(r['worst'],'%')} | {_fmt(r['avg_hold'])} |\n")
    print(f"\nMarkdown: {md}")


def main() -> None:
    ap = argparse.ArgumentParser(description="VCP exit-rule experiment (rec 2)")
    ap.add_argument("trades_json")
    ap.add_argument("--output-dir", default="backtests/")
    ap.add_argument("--sleep-secs", type=float, default=0.25)
    run(ap.parse_args())


if __name__ == "__main__":
    main()
