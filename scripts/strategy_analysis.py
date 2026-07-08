#!/usr/bin/env python3
"""Post-backtest analysis addressing the backtest-analyst recommendations that
are computable offline from an existing ``vcp_trades_*.json`` trade set:

  (1) Cost model — charge slippage+commission on the stock leg and re-report
      excess-over-SPY at base / 2x / 5x cost, to set the true floor.
  (3) OOS validation of the composite-score cutoff — fit the best cutoff on
      2016-2020, evaluate it (and the fixed >=70) on 2021-2026.
  (4) Information Ratio vs a momentum benchmark (MTUM) as well as SPY — VCP is a
      factor bet, so SPY may be the wrong yardstick.
  (5) Portfolio equity-curve proxy — an equal-weight, capacity-capped book that
      realizes each trade's net return, giving approximate CAGR / Sharpe / MDD /
      Calmar (clearly caveated; the exact daily-marked curve needs bar refetch).

Exit-variant testing (recommendation 2) needs bar-level price paths and lives in
trade_simulator.py's re-simulation, not here.

Usage:
    python3 scripts/strategy_analysis.py backtests/vcp_trades_YYYY.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics as st
import sys
from bisect import bisect_right
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trade_simulator import _bootstrap_ci, _t_stat  # noqa: E402
from yf_client import YFClient  # noqa: E402

TRADES_PER_YEAR = 30  # ~317 trades over ~10.5y; used to annualize per-trade IR


# ── (1) Cost model ───────────────────────────────────────────────────────────
def net_excess_with_cost(trade: dict, cost_frac: float) -> float | None:
    """Excess-vs-SPY after charging cost_frac per side on the stock leg only.

    SPY benchmark is buy-and-hold (no per-trade cost), so charging only the
    traded stock is the conservative floor.
    """
    if trade.get("spy_ret_pct") is None:
        return None
    entry, exit_ = trade["entry_price"], trade["exit_price"]
    net_ret = (exit_ * (1 - cost_frac)) / (entry * (1 + cost_frac)) - 1
    return net_ret * 100 - trade["spy_ret_pct"]


def cost_sweep(trades: list[dict], bps_per_side: list[float]) -> list[dict]:
    rows = []
    for bps in bps_per_side:
        c = bps / 1e4
        xs = [v for t in trades if (v := net_excess_with_cost(t, c)) is not None]
        rows.append({
            "bps": bps, "n": len(xs), "mean": round(st.fmean(xs), 3),
            "t": _t_stat(xs), "ci": _bootstrap_ci(xs),
            "win": round(sum(1 for x in xs if x > 0) / len(xs) * 100, 1),
        })
    return rows


# ── (3) OOS score-cutoff validation ──────────────────────────────────────────
def score_cutoff_oos(trades: list[dict], split_year: str, cutoffs: list[float]) -> dict:
    train = [t for t in trades if t["entry_date"][:4] <= split_year]
    test = [t for t in trades if t["entry_date"][:4] > split_year]

    def mean_excess(ts, cut):
        xs = [t["excess_vs_spy_pct"] for t in ts
              if (t.get("composite_score") or 0) >= cut and t["excess_vs_spy_pct"] is not None]
        return (st.fmean(xs), len(xs), _t_stat(xs)) if len(xs) >= 2 else (None, len(xs), None)

    best_cut, best_train = None, -1e9
    for cut in cutoffs:
        m, n, _ = mean_excess(train, cut)
        if m is not None and n >= 10 and m > best_train:
            best_cut, best_train = cut, m
    return {
        "train_n": len(train), "test_n": len(test),
        "best_cut": best_cut,
        "train_at_best": mean_excess(train, best_cut) if best_cut else (None, 0, None),
        "test_at_best": mean_excess(test, best_cut) if best_cut else (None, 0, None),
        "test_at_70": mean_excess(test, 70.0),
        "test_all": mean_excess(test, 0.0),
    }


# ── (4) Information Ratio vs SPY and MTUM ─────────────────────────────────────
def fetch_close_map(symbol: str, days: int) -> dict[str, float]:
    client = YFClient()
    hist = client.get_historical_prices(symbol, days=days)
    bars = (hist or {}).get("historical") or []
    return {b["date"]: b["close"] for b in bars}


def bench_return(close_map: dict, dates_sorted: list[str], entry: str, exit_: str) -> float | None:
    """As-of benchmark return between entry and exit dates (%)."""
    def asof(d):
        i = bisect_right(dates_sorted, d) - 1
        return close_map[dates_sorted[i]] if i >= 0 else None
    a, b = asof(entry), asof(exit_)
    return (b / a - 1) * 100 if a and b and a > 0 else None


def info_ratio(excess: list[float]) -> tuple[float, float]:
    """Per-trade IR and annualized IR (× sqrt(trades/yr))."""
    m, sd = st.fmean(excess), st.stdev(excess)
    ir = m / sd if sd else 0.0
    return round(ir, 3), round(ir * math.sqrt(TRADES_PER_YEAR), 2)


# ── (5) Portfolio equity-curve proxy ─────────────────────────────────────────
def portfolio_proxy(trades: list[dict], cost_frac: float, max_concurrent: int) -> dict:
    """Equal-weight, capacity-capped book. Each accepted trade risks 1/K of
    equity and realizes its net return at exit; equity compounds at exits.

    Approximation: marks only at exits (no intra-trade daily path), so MDD is a
    lower bound on the true drawdown. Capacity cap drops signals taken while K
    slots are already full (chronological priority).
    """
    ordered = sorted(trades, key=lambda x: x["entry_date"])
    cash = 1.0
    open_pos: list[tuple[str, float, float]] = []  # (exit_date, capital, net)
    curve: list[tuple[str, float]] = []
    n_accepted = 0

    for t in ordered:
        # free capital/slots from positions that exited before this entry
        done = [p for p in open_pos if p[0] <= t["entry_date"]]
        for exit_date, cap, net in sorted(done, key=lambda p: p[0]):
            cash += cap * (1 + net)
            open_pos.remove((exit_date, cap, net))
            equity_now = cash + sum(c for _, c, _ in open_pos)
            curve.append((exit_date, equity_now))
        if len(open_pos) < max_concurrent and cash > 0:
            equity_now = cash + sum(c for _, c, _ in open_pos)
            alloc = min(equity_now / max_concurrent, cash)
            net = (t["exit_price"] * (1 - cost_frac)) / (t["entry_price"] * (1 + cost_frac)) - 1
            cash -= alloc
            open_pos.append((t["exit_date"], alloc, net))
            n_accepted += 1
    # close any remaining positions
    for exit_date, cap, net in sorted(open_pos, key=lambda p: p[0]):
        cash += cap * (1 + net)
        curve.append((exit_date, cash + sum(c for e, c, _ in open_pos if e > exit_date)))
    open_pos.clear()
    if not curve:
        return {}
    curve.sort(key=lambda e: e[0])
    rets = [curve[i][1] / curve[i - 1][1] - 1 for i in range(1, len(curve))]
    peak, mdd = curve[0][1], 0.0
    for _, v in curve:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    years = (datetime.fromisoformat(curve[-1][0]) - datetime.fromisoformat(curve[0][0])).days / 365.25
    cagr = curve[-1][1] ** (1 / years) - 1 if years > 0 else 0.0
    sharpe = (st.fmean(rets) / st.stdev(rets) * math.sqrt(TRADES_PER_YEAR)) if len(rets) > 1 and st.stdev(rets) else 0.0
    return {
        "n_accepted": n_accepted, "n_dropped": len(trades) - n_accepted,
        "final_equity": round(curve[-1][1], 3), "cagr": round(cagr * 100, 1),
        "mdd": round(mdd * 100, 1), "sharpe": round(sharpe, 2),
        "calmar": round(cagr / abs(mdd), 2) if mdd else None,
    }


def _fmt(v, s=""):
    return f"{v}{s}" if v is not None else "—"


def main() -> None:
    ap = argparse.ArgumentParser(description="VCP post-backtest analysis (recs 1,3,4,5)")
    ap.add_argument("trades_json")
    ap.add_argument("--base-bps", type=float, default=10.0, help="Base cost per side (bps)")
    ap.add_argument("--max-concurrent", type=int, default=10)
    ap.add_argument("--output-dir", default="backtests/")
    args = ap.parse_args()

    payload = json.load(open(args.trades_json))
    trades = payload["trades"]
    scan_days = (payload.get("metadata") or {}).get("scan_days", 2520)

    print("=" * 74)
    print(f"VCP strategy analysis — {len(trades)} trades")
    print("=" * 74)

    # (1) costs
    print("\n(1) COST SWEEP — excess vs SPY, cost charged on stock leg per side")
    rows = cost_sweep(trades, [0, args.base_bps, args.base_bps * 2, args.base_bps * 5])
    print(f"{'cost/side':>10}{'N':>5}{'meanExc':>9}{'t':>7}{'95% CI':>18}{'win%':>7}")
    for r in rows:
        tag = " (gross)" if r["bps"] == 0 else ""
        print(f"{r['bps']:>7.0f}bps{r['n']:>5}{r['mean']:>9}{_fmt(r['t']):>7}{str(r['ci']):>18}{r['win']:>7}{tag}")

    # (3) OOS score cutoff
    print("\n(3) OOS SCORE-CUTOFF VALIDATION (train 2016-2020 → test 2021-2026)")
    oos = score_cutoff_oos(trades, "2020", [50, 55, 60, 65, 70, 75, 80, 85])
    bc = oos["best_cut"]
    print(f"  train n={oos['train_n']}  test n={oos['test_n']}")
    print(f"  best cutoff on TRAIN: >={_fmt(bc)}  (train mean excess {_fmt(round(oos['train_at_best'][0],2) if oos['train_at_best'][0] is not None else None)}%)")
    tb = oos["test_at_best"]; t70 = oos["test_at_70"]; ta = oos["test_all"]
    print(f"  → OOS test of that cutoff: mean excess {_fmt(round(tb[0],2) if tb[0] is not None else None)}%  n={tb[1]}  t={_fmt(tb[2])}")
    print(f"  OOS test of fixed >=70   : mean excess {_fmt(round(t70[0],2) if t70[0] is not None else None)}%  n={t70[1]}  t={_fmt(t70[2])}")
    print(f"  OOS test all trades      : mean excess {_fmt(round(ta[0],2) if ta[0] is not None else None)}%  n={ta[1]}  t={_fmt(ta[2])}")

    # (4) Information Ratio vs SPY and MTUM
    print("\n(4) INFORMATION RATIO vs SPY and MTUM (momentum benchmark)")
    exc_spy = [t["excess_vs_spy_pct"] for t in trades if t["excess_vs_spy_pct"] is not None]
    ir_spy = info_ratio(exc_spy)
    print("  Fetching MTUM history...", end=" ", flush=True)
    ir_mtum = (None, None)
    try:
        mtum = fetch_close_map("MTUM", scan_days + 500)
        mdates = sorted(mtum)
        print(f"OK ({len(mtum)} bars)")
        exc_mtum, matched = [], 0
        for t in trades:
            br = bench_return(mtum, mdates, t["entry_date"], t["exit_date"])
            if br is not None:
                exc_mtum.append(t["ret_pct"] - br)
                matched += 1
        ir_mtum = info_ratio(exc_mtum)
        m_spy, m_mtum = st.fmean(exc_spy), st.fmean(exc_mtum)
        print(f"  vs SPY  : mean excess {m_spy:+.2f}%  IR/trade {ir_spy[0]}  annualized IR {ir_spy[1]}  t {_fmt(_t_stat(exc_spy))}")
        print(f"  vs MTUM : mean excess {m_mtum:+.2f}%  IR/trade {ir_mtum[0]}  annualized IR {ir_mtum[1]}  t {_fmt(_t_stat(exc_mtum))}  (n={matched})")
    except Exception as e:  # noqa: BLE001
        print(f"FAILED ({e}) — reporting SPY only")
        print(f"  vs SPY  : IR/trade {ir_spy[0]}  annualized IR {ir_spy[1]}  t {_fmt(_t_stat(exc_spy))}")

    # (5) Portfolio proxy
    print(f"\n(5) PORTFOLIO EQUITY-CURVE PROXY (equal-weight, max {args.max_concurrent} concurrent, {args.base_bps:.0f}bps/side)")
    pp = portfolio_proxy(trades, args.base_bps / 1e4, args.max_concurrent)
    if pp:
        print(f"  accepted {pp['n_accepted']} / dropped {pp['n_dropped']} (capacity)")
        print(f"  CAGR {pp['cagr']}%  MDD {pp['mdd']}%  Sharpe {pp['sharpe']}  Calmar {_fmt(pp['calmar'])}  finalx {pp['final_equity']}")
        print("  NOTE: marked at exits only → MDD is a LOWER bound; exact curve needs daily marks.")

    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    md = os.path.join(args.output_dir, f"vcp_strategy_analysis_{ts}.md")
    with open(md, "w") as f:
        f.write(f"# VCP Strategy Analysis\n\nGenerated {ts}\n\n")
        f.write("## (1) Cost sweep — excess vs SPY\n\n| Cost/side | N | Mean excess | t | 95% CI | Win% |\n|---|---|---|---|---|---|\n")
        for r in rows:
            f.write(f"| {r['bps']:.0f}bps | {r['n']} | {r['mean']}% | {_fmt(r['t'])} | {r['ci']} | {r['win']}% |\n")
        f.write(f"\n## (3) OOS score cutoff\n\nBest train cutoff >= {_fmt(bc)}; OOS test mean excess "
                f"{_fmt(round(tb[0],2) if tb[0] is not None else None)}% (t={_fmt(tb[2])}, n={tb[1]}). "
                f"Fixed >=70 OOS: {_fmt(round(t70[0],2) if t70[0] is not None else None)}% (t={_fmt(t70[2])}, n={t70[1]}).\n")
        f.write(f"\n## (4) Information Ratio\n\nvs SPY annualized IR {ir_spy[1]}; vs MTUM annualized IR {ir_mtum[1]}.\n")
        if pp:
            f.write(f"\n## (5) Portfolio proxy\n\nCAGR {pp['cagr']}%, MDD {pp['mdd']}% (lower bound), "
                    f"Sharpe {pp['sharpe']}, Calmar {_fmt(pp['calmar'])}.\n")
    print(f"\nMarkdown: {md}")


if __name__ == "__main__":
    main()
