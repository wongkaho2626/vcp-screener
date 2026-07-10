#!/usr/bin/env python3
"""Exit stress experiments — three families that all failed to beat the
boring baseline (initial hard stop + 60-bar timeout). Kept reproducible
because the negative results are load-bearing for the project's conclusions.

Families:
  stop-only  : no time exit; hold until the close breaks the initial stop.
               Result: S&P mean +24% excess is a top-10-trade survivorship
               lottery (drop-top-10 → −7.8%, t −2.7); R2K +0.2% (t 0.06),
               drop-top-10 → −9.2% (t −8.1). Median trade rots at −8/−9%.
  strict     : Minervini 3-tier — stop full-exit / +20-25% scale out 50% /
               MA50-break sells the rest, no timeout. Degenerates to a
               faster, shallower stop (~2/3 exit via MA50 at median day
               18-19; only 10-15% ever reach the scale-out). S&P −0.29% vs
               baseline −0.53%; R2K −0.46% vs −0.41% — sign flips, ns.
  asymmetric : cull laggards early (day 10/15) and/or ride +20%-in-20d
               winners to 120-180d (optional 25% trail). Day-10 strength has
               no forward predictive power; ride variants are worse in BOTH
               universes (surges mean-revert); cull sign-flips.

Usage:
    python3 scripts/exit_stress_experiments.py backtests/.../vcp_trades_X.json \
        --price-csv SP500_Historical_Data.csv
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

NO_TIMEOUT = 10**6


# ---------------------------------------------------------------------------
# Pure walkers
# ---------------------------------------------------------------------------

def _sma(chrono: list[dict], idx: int, period: int) -> float | None:
    if idx + 1 < period:
        return None
    return st.fmean(b["close"] for b in chrono[idx - period + 1 : idx + 1])


def strict_exit(
    chrono: list[dict], start: int, entry: float, stop: float,
    pt_pct: float, ma_period: int = 50,
) -> tuple[list[tuple[float, int, float]], str]:
    """Two 50% legs: leg A takes profit at entry*(1+pt_pct); everything
    remaining exits on close<stop or close<SMA(ma_period); data end marks the
    rest at the last close. Pure. Returns (legs, path) where each leg is
    (weight, exit_idx, ret_pct)."""
    target = entry * (1 + pt_pct / 100)
    a_leg: tuple[float, int, float] | None = None
    last = len(chrono) - 1
    for j in range(start + 1, last + 1):
        close = chrono[j]["close"]
        ma = _sma(chrono, j, ma_period)
        terminal = None
        if close < stop:
            terminal = "stop"
        elif ma is not None and close < ma:
            terminal = "ma"
        ret = (close / entry - 1) * 100
        if a_leg is None and terminal is None and close >= target:
            a_leg = (0.5, j, ret)
        if terminal:
            if a_leg is None:
                return [(1.0, j, ret)], f"{terminal}-full"
            return [a_leg, (0.5, j, ret)], f"target+{terminal}"
    ret = (chrono[last]["close"] / entry - 1) * 100
    if a_leg is None:
        return [(1.0, last, ret)], "open-full"
    return [a_leg, (0.5, last, ret)], "target+open"


def momentum_walk(
    chrono: list[dict], start: int, entry: float, stop: float,
    cfg: dict, base_hold: int = 60,
) -> tuple[int, str]:
    """Asymmetric walk: hard stop always; optionally cull a laggard at
    ``cull_day`` when ret < ``cull_min``; optionally a trade that reaches
    ``ride_trigger``% within ``ride_window`` bars is ridden to ``ride_hold``
    bars (with an optional ``ride_trail``% trail from high-water). Pure."""
    high_water = entry
    qualified = False
    last = len(chrono) - 1
    for j in range(start + 1, last + 1):
        d = j - start
        close = chrono[j]["close"]
        high_water = max(high_water, close)
        ret = (close / entry - 1) * 100
        if close < stop:
            return j, "stop"
        if (not qualified and cfg.get("ride_trigger")
                and d <= cfg["ride_window"] and ret >= cfg["ride_trigger"]):
            qualified = True
        if (not qualified and cfg.get("cull_day") and d == cfg["cull_day"]
                and ret < cfg["cull_min"]):
            return j, "cull"
        if qualified:
            if cfg.get("ride_trail") and close < high_water * (1 - cfg["ride_trail"] / 100):
                return j, "ride_trail"
            if d >= cfg["ride_hold"]:
                return j, "ride_timeout"
        elif d >= base_hold:
            return j, "timeout"
    return last, "open"


# ---------------------------------------------------------------------------
# Experiment driver
# ---------------------------------------------------------------------------

ASYM_CONFIGS = [
    ("cull d10 ret<0", {"cull_day": 10, "cull_min": 0.0}),
    ("cull d15 ret<5", {"cull_day": 15, "cull_min": 5.0}),
    ("ride120", {"ride_trigger": 20.0, "ride_window": 20, "ride_hold": 120}),
    ("ride-trail25", {"ride_trigger": 20.0, "ride_window": 20, "ride_hold": 180,
                      "ride_trail": 25.0}),
    ("cull+ride-trail", {"cull_day": 10, "cull_min": 0.0, "ride_trigger": 20.0,
                         "ride_window": 20, "ride_hold": 180, "ride_trail": 25.0}),
]


def run(args: argparse.Namespace) -> None:
    payload = json.load(open(args.trades_json))
    trades = payload["trades"]

    if args.price_csv:
        from csv_client import CSVClient  # noqa: PLC0415 — optional offline path

        client = CSVClient(args.price_csv)
        sleep_secs = 0.0
    else:
        client = YFClient()
        sleep_secs = args.sleep_secs

    fetch_days = 3020
    print("Fetching SPY...", end=" ", flush=True)
    spy_chrono, spy_idx = _to_chrono(
        client.get_historical_prices("SPY", days=fetch_days)["historical"])
    print(f"OK ({len(spy_chrono)} bars)")

    def spy_ret(d1: str, d2: str) -> float | None:
        si, sj = spy_idx.get(d1), spy_idx.get(d2)
        if si is None or sj is None or sj <= si:
            return None
        return (spy_chrono[sj]["close"] / spy_chrono[si]["close"] - 1) * 100

    symbols = sorted({t["symbol"] for t in trades})
    bars: dict[str, tuple] = {}
    for i, sym in enumerate(symbols, 1):
        try:
            hist = client.get_historical_prices(sym, days=fetch_days)
            bars[sym] = _to_chrono((hist or {}).get("historical") or [])
        except Exception:  # noqa: BLE001 — skip bad tickers, keep the run alive
            bars[sym] = ([], {})
        if i % 100 == 0:
            print(f"  {i}/{len(symbols)} tickers", flush=True)
        if sleep_secs > 0 and i < len(symbols):
            time.sleep(sleep_secs)

    def located(t: dict) -> tuple | None:
        chrono, idx_map = bars.get(t["symbol"], ([], {}))
        start = idx_map.get(t["entry_date"])
        return (chrono, start) if start is not None else None

    def weighted_excess(chrono: list[dict], start: int,
                        legs: list[tuple[float, int, float]]) -> float | None:
        total = 0.0
        for weight, j, ret in legs:
            sr = spy_ret(chrono[start]["date"], chrono[j]["date"])
            if sr is None:
                return None
            total += weight * (ret - sr)
        return total

    results: list[tuple[str, list[dict]]] = []

    def simple_family(label: str, max_hold: int) -> None:
        rows = []
        for t in trades:
            loc = located(t)
            if loc is None:
                continue
            chrono, start = loc
            ex = simulate_exit(chrono, start, t["stop_price"], max_hold)
            if ex is None:
                continue
            ret = (ex["exit_price"] / t["entry_price"] - 1) * 100
            exc = weighted_excess(chrono, start,
                                  [(1.0, start + ex["hold_bars"], ret)])
            if exc is None:
                continue
            rows.append({"exc": exc, "hold": ex["hold_bars"],
                         "path": ex["exit_reason"], "year": t["entry_date"][:4]})
        results.append((label, rows))

    simple_family("baseline stop+60d", 60)
    simple_family("stop-only (no timeout)", NO_TIMEOUT)

    for pt in (20.0, 25.0):
        rows = []
        for t in trades:
            loc = located(t)
            if loc is None:
                continue
            chrono, start = loc
            legs, path = strict_exit(chrono, start, t["entry_price"],
                                     t["stop_price"], pt)
            exc = weighted_excess(chrono, start, legs)
            if exc is None:
                continue
            rows.append({"exc": exc, "hold": legs[-1][1] - start, "path": path,
                         "year": t["entry_date"][:4]})
        results.append((f"strict PT{pt:.0f}%/MA50", rows))

    for label, cfg in ASYM_CONFIGS:
        rows = []
        for t in trades:
            loc = located(t)
            if loc is None:
                continue
            chrono, start = loc
            j, reason = momentum_walk(chrono, start, t["entry_price"],
                                      t["stop_price"], cfg)
            ret = (chrono[j]["close"] / t["entry_price"] - 1) * 100
            exc = weighted_excess(chrono, start, [(1.0, j, ret)])
            if exc is None:
                continue
            rows.append({"exc": exc, "hold": j - start, "path": reason,
                         "year": t["entry_date"][:4]})
        results.append((label, rows))

    md = ["# Exit Stress Experiments", "",
          f"Source: {os.path.basename(args.trades_json)} | excess vs SPY over "
          "each leg's own holding period; no costs.", "",
          "| Config | N | Mean excess | t | 95% CI | Median | Win% | Avg hold |",
          "|---|---|---|---|---|---|---|---|"]
    hdr = (f"{'config':<24}{'n':>5}{'meanExc':>9}{'t':>7}{'medExc':>8}"
           f"{'win%':>7}{'hold':>6}")
    print("\n" + hdr)
    for label, rows in results:
        exc = [r["exc"] for r in rows]
        if len(exc) < 6:
            print(f"{label:<24} too few rows")
            continue
        mean_e, t_e, ci = round(st.fmean(exc), 2), _t_stat(exc), _bootstrap_ci(exc)
        med = round(st.median(exc), 2)
        win = round(sum(1 for e in exc if e > 0) / len(exc) * 100, 1)
        hold = round(st.fmean(r["hold"] for r in rows), 1)
        print(f"{label:<24}{len(exc):>5}{mean_e:>9}{t_e:>7}{med:>8}{win:>7}{hold:>6}")
        md.append(f"| {label} | {len(exc)} | {mean_e}% | {t_e} | {ci} | "
                  f"{med}% | {win}% | {hold} |")

    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    md_path = os.path.join(args.output_dir, f"vcp_exit_stress_{ts}.md")
    with open(md_path, "w") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nMarkdown: {md_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Exit stress experiments (3 families)")
    ap.add_argument("trades_json", help="Path to a vcp_trades_*.json report")
    ap.add_argument("--price-csv", help="Offline OHLCV CSV (CSVClient); else yfinance")
    ap.add_argument("--output-dir", default="backtests/")
    ap.add_argument("--sleep-secs", type=float, default=0.3)
    run(ap.parse_args())


if __name__ == "__main__":
    main()
