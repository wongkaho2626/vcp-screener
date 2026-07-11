#!/usr/bin/env python3
"""Momentum validation suite — the five follow-ups from the xs-momentum
backtest review, in one CLI:

  S&P mode (--price-csv):
    1. turnover measurement + cost stress (10/20/50 bp round-trip)
    2. point-in-time membership filter (scripts/data/sp500_membership.csv)
    3. lookback sensitivity scan (3-1 / 6-1 / 9-1 / 12-1) — legitimate now:
       12-1 was prespecified and reported first; this is a post-hoc
       robustness check, not selection
    4. volatility scaling (de-risk only, trailing 6-month window)

  R2K mode (--symbols-json, yfinance):
    5. benchmark swap — excess vs an equal-weight index of the universe
       itself instead of SPY (removes the size effect from the measure);
       SPY excess reported alongside for contrast

Usage:
    python3 scripts/momentum_validation.py --price-csv SP500_Historical_Data.csv
    python3 scripts/momentum_validation.py \
        --symbols-json scripts/data/russell2000_constituents.json \
        --output-dir backtests/r2k/
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

from membership import is_member, load_membership  # noqa: E402
from signal_family_experiment import (  # noqa: E402
    momentum_score,
    month_end_indices,
    rank_momentum,
)
from trade_simulator import _t_stat, _to_chrono  # noqa: E402

LOOKBACKS = [("3-1", 63), ("6-1", 126), ("9-1", 189), ("12-1", 252)]
COST_TIERS_BP = (10.0, 20.0, 50.0)


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

def replaced_fraction(prev: list[str], cur: list[str]) -> float:
    """Fraction of the current book that had to be bought this rebalance
    (1.0 on the first month — the whole book is new)."""
    if not cur:
        return 0.0
    if not prev:
        return 1.0
    return len(set(cur) - set(prev)) / len(cur)


def apply_costs(vals: list[float], turnovers: list[float],
                roundtrip_bp: float) -> list[float]:
    """Net monthly excess: gross minus (replaced fraction x round-trip cost).
    ``roundtrip_bp`` is in basis points; vals/turnovers align by month."""
    drag = roundtrip_bp / 100.0  # bp -> %
    return [v - to * drag for v, to in zip(vals, turnovers)]


def vol_scaled(vals: list[float], window: int = 6,
               target: float | None = None) -> list[float]:
    """De-risk-only volatility scaling: weight_t = min(1, target / trailing
    sigma over ``window`` months). First ``window`` months pass unscaled.
    Default target = full-sample sigma (no leverage is ever applied)."""
    if len(vals) <= window:
        return list(vals)
    tgt = st.stdev(vals) if target is None else target
    out = list(vals[:window])
    for i in range(window, len(vals)):
        sigma = st.stdev(vals[i - window : i])
        w = min(1.0, tgt / sigma) if sigma > 0 else 1.0
        out.append(vals[i] * w)
    return out


def build_ew_index(chronos: list[list[dict]],
                   max_daily_ret: float = 1.0) -> tuple[list[dict], dict]:
    """Equal-weight index from per-symbol chrono bars: each day's index
    return is the mean of that day's available symbol returns. Daily moves
    beyond ``max_daily_ret`` (default ±100%) are treated as data glitches
    (unadjusted splits, penny-stock bad prints) and excluded — one fake
    +1900% day across 1,900 names would otherwise poison the whole index.
    Returns (chrono bars, date->idx map) shaped like _to_chrono output."""
    accum: dict[str, list[float]] = {}
    dates: set[str] = set()
    for chrono in chronos:
        for k in range(len(chrono)):
            dates.add(chrono[k]["date"])
            if k == 0:
                continue
            prev, cur = chrono[k - 1], chrono[k]
            if prev["close"] <= 0:
                continue
            r = cur["close"] / prev["close"] - 1
            if abs(r) > max_daily_ret:
                continue
            cell = accum.setdefault(cur["date"], [0.0, 0])
            cell[0] += r
            cell[1] += 1
    level = 100.0
    bars: list[dict] = []
    for d in sorted(dates):
        s, n = accum.get(d, (0.0, 0))
        if n > 0:
            level *= 1 + s / n
        bars.append({"date": d, "close": round(level, 6)})
    return bars, {b["date"]: i for i, b in enumerate(bars)}


# ---------------------------------------------------------------------------
# Monthly walk
# ---------------------------------------------------------------------------

def momentum_monthly(
    bars: dict[str, tuple], bench: tuple[list[dict], dict],
    eligible=None, lb_long: int = 252, lb_skip: int = 21,
    top_frac: float = 0.1,
) -> list[dict]:
    """Monthly portfolio walk. Returns [{date, exc, to, n}] where exc is the
    equal-weight portfolio excess vs the benchmark over the month and ``to``
    the replaced fraction vs the previous book."""
    bench_chrono, bench_idx = bench
    rebal = month_end_indices([b["date"] for b in bench_chrono])
    rows: list[dict] = []
    prev_picks: list[str] = []
    for k in range(len(rebal) - 1):
        d_in = bench_chrono[rebal[k]]["date"]
        d_out = bench_chrono[rebal[k + 1]]["date"]
        bench_r = (bench_chrono[rebal[k + 1]]["close"]
                   / bench_chrono[rebal[k]]["close"] - 1) * 100
        scores: dict[str, float] = {}
        for sym, (chrono, idx_map) in bars.items():
            i = idx_map.get(d_in)
            if i is None or idx_map.get(d_out) is None:
                continue
            if eligible is not None and not eligible(sym, d_in):
                continue
            s = momentum_score([b["close"] for b in chrono], i,
                               lb_long=lb_long, lb_skip=lb_skip)
            if s is not None:
                scores[sym] = s
        if len(scores) < 50:
            continue
        picks = rank_momentum(scores, top_frac=top_frac)
        rets = []
        for sym in picks:
            chrono, idx_map = bars[sym]
            rets.append((chrono[idx_map[d_out]]["close"]
                         / chrono[idx_map[d_in]]["close"] - 1) * 100)
        if not rets:
            continue
        rows.append({"date": d_in, "exc": st.fmean(rets) - bench_r,
                     "to": replaced_fraction(prev_picks, picks),
                     "n": len(picks)})
        prev_picks = picks
    return rows


# ---------------------------------------------------------------------------
# Stats & reporting
# ---------------------------------------------------------------------------

def series_stats(vals: list[float]) -> dict:
    n = len(vals)
    mean, sd = st.fmean(vals), st.stdev(vals)
    level, peak, mdd = 1.0, 1.0, 0.0
    for v in vals:
        level *= 1 + v / 100
        peak = max(peak, level)
        mdd = min(mdd, level / peak - 1)
    # A month below -100% sends the compounded level non-positive; the
    # annualised figure is then undefined — report NaN, don't crash.
    ann = ((level ** (12 / n) - 1) * 100) if level > 0 else float("nan")
    return {
        "n": n, "mean": round(mean, 3), "t": _t_stat(vals),
        "ir": round(mean / sd * math.sqrt(12), 2),
        "pos": round(sum(1 for v in vals if v > 0) / n * 100, 1),
        "mdd": round(mdd * 100, 1),
        "ann": round(ann, 2) if not math.isnan(ann) else ann,
    }


def fold_means(rows: list[dict]) -> tuple[str, str]:
    a = [r["exc"] for r in rows if r["date"][:4] <= "2020"]
    b = [r["exc"] for r in rows if r["date"][:4] >= "2021"]
    fa = f"{st.fmean(a):.2f} (t {_t_stat(a)})" if len(a) >= 6 else "—"
    fb = f"{st.fmean(b):.2f} (t {_t_stat(b)})" if len(b) >= 6 else "—"
    return fa, fb


def stat_row(label: str, vals: list[float], md: list[str],
             extra: str = "") -> None:
    s = series_stats(vals)
    print(f"{label:<26} mean {s['mean']:>7}%/mo  t {s['t']:>6}  IR {s['ir']:>5} "
          f" ann {s['ann']:>6}%  MDD {s['mdd']:>6}%  {extra}")
    md.append(f"| {label} | {s['n']} | {s['mean']}% | {s['t']} | {s['ir']} | "
              f"{s['ann']}% | {s['mdd']}% | {s['pos']}% | {extra} |")


# ---------------------------------------------------------------------------
# Drivers
# ---------------------------------------------------------------------------

def _load_bars(client, symbols: list[str], fetch_days: int,
               sleep_secs: float) -> dict[str, tuple]:
    if sleep_secs > 0:
        import time  # noqa: PLC0415 — only the yfinance path throttles
    bars: dict[str, tuple] = {}
    for n, sym in enumerate(symbols, 1):
        try:
            hist = client.get_historical_prices(sym, days=fetch_days)
            bars[sym] = _to_chrono((hist or {}).get("historical") or [])
        except Exception:  # noqa: BLE001 — skip bad tickers, keep the run alive
            bars[sym] = ([], {})
        if sleep_secs > 0:
            if n % 200 == 0:
                print(f"  fetched {n}/{len(symbols)}", flush=True)
            if n < len(symbols):
                time.sleep(sleep_secs)
    return bars


def run_sp(args: argparse.Namespace, md: list[str]) -> None:
    from csv_client import CSVClient  # noqa: PLC0415

    client = CSVClient(args.price_csv)
    print(f"data_source: {client.get_api_stats()['data_source']}")
    symbols = [d["symbol"] for d in client.get_constituents()]
    bars = _load_bars(client, symbols, 10**6, 0.0)
    spy = _to_chrono(client.get_historical_prices("SPY", days=10**6)["historical"])

    base = momentum_monthly(bars, spy)
    vals = [r["exc"] for r in base]
    tos = [r["to"] for r in base]
    avg_to = st.fmean(tos)

    md += ["## 1. Turnover & cost stress (S&P)", "",
           f"Avg replaced fraction: **{avg_to * 100:.1f}%/month** "
           f"(one-sided; first month = 100%).", "",
           "| Config | Months | Mean | t | IR | Ann | MDD | %>0 | Note |",
           "|---|---|---|---|---|---|---|---|---|"]
    stat_row("gross", vals, md)
    for bp in COST_TIERS_BP:
        net = apply_costs(vals, tos, bp)
        stat_row(f"net @{bp:.0f}bp RT", net, md,
                 extra=f"drag {avg_to * bp / 100:.2f}%/mo")

    md += ["", "## 2. Point-in-time membership filter (S&P)", "",
           "| Config | Months | Mean | t | IR | Ann | MDD | %>0 | Note |",
           "|---|---|---|---|---|---|---|---|---|"]
    intervals = load_membership()
    pit = momentum_monthly(
        bars, spy, eligible=lambda sym, d: is_member(intervals, sym, d))
    n_base = st.fmean(r["n"] for r in base)
    n_pit = st.fmean(r["n"] for r in pit)
    stat_row("current members", vals, md, extra=f"{n_base:.0f} picks/mo")
    stat_row("PIT members", [r["exc"] for r in pit], md,
             extra=f"{n_pit:.0f} picks/mo")

    md += ["", "## 3. Lookback sensitivity (S&P, gross)", "",
           "| Lookback | Months | Mean | t | IR | Ann | MDD | %>0 | Folds |",
           "|---|---|---|---|---|---|---|---|---|"]
    for label, lb in LOOKBACKS:
        rows = base if lb == 252 else momentum_monthly(bars, spy, lb_long=lb)
        fa, fb = fold_means(rows)
        stat_row(f"mom {label}", [r["exc"] for r in rows], md,
                 extra=f"≤20: {fa} / ≥21: {fb}")

    md += ["", "## 4. Volatility scaling (S&P, gross)", "",
           "| Config | Months | Mean | t | IR | Ann | MDD | %>0 | Note |",
           "|---|---|---|---|---|---|---|---|---|"]
    stat_row("unscaled", vals, md)
    stat_row("vol-scaled (6m, de-risk)", vol_scaled(vals), md)


def run_r2k(args: argparse.Namespace, md: list[str]) -> None:
    from yf_client import YFClient  # noqa: PLC0415

    client = YFClient()
    with open(args.symbols_json) as f:
        raw = json.load(f)
    symbols = sorted(d["symbol"] if isinstance(d, dict) else d for d in raw)
    print(f"data_source: yfinance | universe {len(symbols)}")
    bars = _load_bars(client, symbols, 3800, args.sleep_secs)
    spy = _to_chrono(client.get_historical_prices("SPY", days=3800)["historical"])
    ew = build_ew_index([c for c, _ in bars.values() if c])

    md += ["## 5. R2K benchmark swap", "",
           "Excess vs an equal-weight index of the R2K universe itself "
           "(removes the size effect) vs the SPY benchmark used previously.", "",
           "| Benchmark | Months | Mean | t | IR | Ann | MDD | %>0 | Folds |",
           "|---|---|---|---|---|---|---|---|---|"]
    legs = [("vs SPY", spy, None), ("vs R2K equal-weight", ew, None)]
    if args.pit_csv:
        intervals = load_membership(args.pit_csv)
        legs.append(("vs R2K EW, PIT members", ew,
                     lambda sym, d: is_member(intervals, sym, d)))
    for label, bench, eligible in legs:
        rows = momentum_monthly(bars, bench, eligible=eligible)
        fa, fb = fold_means(rows)
        n_avg = st.fmean(r["n"] for r in rows) if rows else 0
        stat_row(label, [r["exc"] for r in rows], md,
                 extra=f"≤20: {fa} / ≥21: {fb} | {n_avg:.0f} picks/mo")


def main() -> None:
    ap = argparse.ArgumentParser(description="xs-momentum validation suite")
    ap.add_argument("--price-csv", help="S&P mode: offline OHLCV CSV")
    ap.add_argument("--symbols-json", help="R2K mode: universe JSON (yfinance)")
    ap.add_argument("--pit-csv",
                    help="R2K mode: membership intervals CSV for a PIT leg "
                         "(scripts/data/r2k_membership.csv)")
    ap.add_argument("--sleep-secs", type=float, default=0.25)
    ap.add_argument("--output-dir", default="backtests/")
    args = ap.parse_args()
    if not args.price_csv and not args.symbols_json:
        ap.error("need --price-csv (S&P suite) or --symbols-json (R2K swap)")

    md = ["# Momentum Validation Suite", "",
          "12-1 top-decile monthly momentum; excess per month vs benchmark; "
          "monthly series stats. Follow-ups to the 2026-07-11 signal-family "
          "experiment.", ""]
    if args.price_csv:
        run_sp(args, md)
    else:
        run_r2k(args, md)

    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = os.path.join(args.output_dir, f"momentum_validation_{ts}.md")
    with open(path, "w") as f:
        f.write("\n".join(md) + "\n")
    print(f"\nMarkdown: {path}")


if __name__ == "__main__":
    main()
