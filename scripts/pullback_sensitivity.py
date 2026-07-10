#!/usr/bin/env python3
"""Parameter-sensitivity scan for the pullback-entry paired advantage.

Sweeps the MA-touch grid (MA period x entry window) around the shipped rule
(MA20, 15-bar window) and reports, per cell, the paired Δ (pullback minus
breakout excess on the same detection) with a 2016–2020 / 2021–2026 fold
split. Run to check that the advantage degrades smoothly rather than
cliff-edging — the robustness question a single-config backtest can't answer.

Findings on 2026-07-10 (S&P offline CSV + R2K yfinance): smooth monotone
gradient in both universes — MA10 ≈ 0 (its touch is trivial), deepening MAs
strengthen (MA30 w15 significant in both universes and both folds); windows
beyond ~15 bars decay toward zero (stale retests). The shipped rule stays
MA20 w15; MA30 is noted for prespecified validation on future data only.

Usage:
    python3 scripts/pullback_sensitivity.py backtests/.../vcp_backtest_X.json \
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

from pullback_experiment import plan_pullback_entry  # noqa: E402
from trade_simulator import _bootstrap_ci, _t_stat, _to_chrono, simulate_exit  # noqa: E402
from yf_client import YFClient  # noqa: E402

GRID = [
    ("MA10 w15", {"ma_period": 10, "window": 15}),
    ("MA15 w15", {"ma_period": 15, "window": 15}),
    ("MA20 w15", {"ma_period": 20, "window": 15}),
    ("MA25 w15", {"ma_period": 25, "window": 15}),
    ("MA30 w15", {"ma_period": 30, "window": 15}),
    ("MA20 w10", {"ma_period": 20, "window": 10}),
    ("MA20 w20", {"ma_period": 20, "window": 20}),
    ("MA20 w25", {"ma_period": 20, "window": 25}),
]
FOLDS = (("2016", "2020"), ("2021", "2026"))


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

    def spy_ret(d1: str, d2: str) -> float | None:
        si, sj = spy_idx.get(d1), spy_idx.get(d2)
        if si is None or sj is None or sj <= si:
            return None
        return (spy_chrono[sj]["close"] / spy_chrono[si]["close"] - 1) * 100

    def leg_exc(chrono: list[dict], idx: int, price: float,
                pstop: float | None) -> float | None:
        stop = max(pstop or 0, price * (1 - args.max_risk_pct / 100))
        ex = simulate_exit(chrono, idx, stop, args.max_hold_bars)
        if ex is None:
            return None
        ret = (ex["exit_price"] / price - 1) * 100
        sr = spy_ret(chrono[idx]["date"], ex["exit_date"])
        return None if sr is None else ret - sr

    pairs_by_cfg: dict[str, list[dict]] = {label: [] for label, _ in GRID}
    symbols = sorted(detections_by_ticker)
    for i, sym in enumerate(symbols, 1):
        try:
            hist = client.get_historical_prices(sym, days=fetch_days)
        except Exception:  # noqa: BLE001 — skip bad tickers, keep the run alive
            continue
        chrono, idx_map = _to_chrono((hist or {}).get("historical") or [])
        for det in detections_by_ticker[sym]:
            fo = det.get("forward_outcome") or {}
            pivot, pstop = fo.get("pivot_price"), fo.get("stop_price")
            if fo.get("outcome_type") != "breakout" or not pivot:
                continue
            bo_idx = idx_map.get(fo.get("exit_date"))
            if bo_idx is None:
                continue
            bo_price = fo.get("exit_price") or chrono[bo_idx]["close"]
            if (bo_price / pivot - 1) * 100 > args.max_extension_pct:
                continue
            bo = leg_exc(chrono, bo_idx, bo_price, pstop)
            if bo is None:
                continue
            wait_stop = pstop or pivot * (1 - args.max_risk_pct / 100)
            for label, kwargs in GRID:
                plan = plan_pullback_entry(chrono, bo_idx, pivot, wait_stop, **kwargs)
                if plan is None:
                    continue
                pb = leg_exc(chrono, plan["entry_idx"], plan["entry_price"], pstop)
                if pb is None:
                    continue
                pairs_by_cfg[label].append(
                    {"date": chrono[bo_idx]["date"], "d": pb - bo})
        if i % 100 == 0:
            print(f"  {i}/{len(symbols)} tickers", flush=True)
        if sleep_secs > 0 and i < len(symbols):
            time.sleep(sleep_secs)

    md = ["# Pullback-Entry Sensitivity Scan", "",
          "Paired Δ = pullback excess − breakout excess on the same detection (pp).", "",
          "| Config | N pairs | Mean Δ | t | 95% CI | Fold 16–20 | Fold 21–26 |",
          "|---|---|---|---|---|---|---|"]
    hdr = (f"{'config':<12}{'n':>6}{'meanΔ':>8}{'t':>7}{'CI':>16}"
           f"{'fold16-20':>22}{'fold21-26':>22}")
    print("\n" + hdr)
    for label, _ in GRID:
        pr = pairs_by_cfg[label]
        d = [x["d"] for x in pr]
        if len(d) < 6:
            print(f"{label:<12} too few pairs ({len(d)})")
            md.append(f"| {label} | {len(d)} | too few | | | | |")
            continue
        fold_strs = []
        for lo, hi in FOLDS:
            f = [x["d"] for x in pr if lo <= x["date"][:4] <= hi]
            fold_strs.append(f"{round(st.fmean(f), 2)} (t {_t_stat(f)}, n {len(f)})"
                             if len(f) >= 6 else f"n={len(f)}")
        mean_d, t, ci = round(st.fmean(d), 2), _t_stat(d), _bootstrap_ci(d)
        print(f"{label:<12}{len(d):>6}{mean_d:>8}{t:>7}{str(ci):>16}"
              f"{fold_strs[0]:>22}{fold_strs[1]:>22}")
        md.append(f"| {label} | {len(d)} | {mean_d} | {t} | {ci} | "
                  f"{fold_strs[0]} | {fold_strs[1]} |")

    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    md_path = os.path.join(args.output_dir, f"vcp_pullback_sensitivity_{ts}.md")
    with open(md_path, "w") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nMarkdown: {md_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Pullback-entry parameter-sensitivity scan")
    ap.add_argument("backtest_jsons", nargs="+", help="vcp_backtest_*.json report(s)")
    ap.add_argument("--price-csv", help="Offline OHLCV CSV (CSVClient); else yfinance")
    ap.add_argument("--max-extension-pct", type=float, default=5.0)
    ap.add_argument("--max-risk-pct", type=float, default=8.0)
    ap.add_argument("--max-hold-bars", type=int, default=60)
    ap.add_argument("--output-dir", default="backtests/")
    ap.add_argument("--sleep-secs", type=float, default=0.3)
    run(ap.parse_args())


if __name__ == "__main__":
    main()
