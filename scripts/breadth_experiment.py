#!/usr/bin/env python3
"""Breadth-regime experiment — does gating VCP trades by S&P 500 breadth improve
performance?

Reads an existing ``vcp_trades_*.json`` (from trade_simulator.py), attaches the
S&P 500 breadth reading on each trade's entry date, and re-computes trade
statistics for a range of market-regime filters. A pure entry-regime gate only
ever *removes* trades, so filtering the existing trade set is exact and needs no
price refetch.

Two metric families are reported side by side because they answer different
questions (breadth is a market-timing signal, excess-over-SPY is market-neutral
by construction):
  - ABSOLUTE : mean raw return, win rate, profit factor, worst trade
  - RELATIVE : mean excess vs SPY + t-stat + bootstrap 95% CI  (the alpha test)

Usage:
    python3 scripts/breadth_experiment.py backtests/vcp_trades_YYYY.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from breadth_regime import DEFAULT_BREADTH_CSV, breadth_change, breadth_on_date, load_breadth
from trade_simulator import compute_trade_stats, group_stats_by_year

SCORE_CUTOFF = 70.0  # composite-score cohort that hinted at edge in the baseline


def attach_breadth(trades: list[dict], series: list[tuple[str, float]]) -> list[dict]:
    """Return new trade dicts with breadth-on-entry-date attached (immutable)."""
    return [
        {
            **t,
            "breadth": breadth_on_date(series, t["entry_date"]),
            "breadth_chg20": breadth_change(series, t["entry_date"], 20),
        }
        for t in trades
    ]


def make_filters(thresholds: list[float]) -> dict:
    """Named regime predicates over a breadth-annotated trade dict."""
    filters = {"all (no filter)": lambda t: True}
    for thr in thresholds:
        filters[f"breadth >= {thr:g}"] = (
            lambda t, thr=thr: t["breadth"] is not None and t["breadth"] >= thr
        )
    filters["not washed out (>=26)"] = (
        lambda t: t["breadth"] is not None and t["breadth"] >= 26
    )
    filters["breadth rising (20d)"] = (
        lambda t: t["breadth_chg20"] is not None and t["breadth_chg20"] > 0
    )
    return filters


def cohort_row(name: str, trades: list[dict]) -> dict:
    """One results row: reuse compute_trade_stats for the heavy lifting."""
    stats = compute_trade_stats(trades, skips={})
    return {
        "name": name,
        "n": stats["n_trades"],
        "mean_excess": stats["primary_mean_excess_vs_spy_pct"],
        "t_excess": stats["primary_t_stat_excess"],
        "ci_excess": stats["primary_bootstrap_95ci_excess_pct"],
        "excess_win": stats["excess_win_rate_pct"],
        "mean_ret": stats["mean_ret_pct"],
        "win_rate": stats["win_rate_pct"],
        "pf": stats["profit_factor"],
        "worst": stats["worst_trade_pct"],
    }


def _fmt(v, suffix="") -> str:
    return f"{v}{suffix}" if v is not None else "—"


def render_table(title: str, rows: list[dict]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| Regime | N | Mean excess vs SPY | t | 95% CI | Excess win% | Mean ret | Win% | PF | Worst |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['name']} | {r['n']} | {_fmt(r['mean_excess'], '%')} | "
            f"{_fmt(r['t_excess'])} | {_fmt(r['ci_excess'])} | "
            f"{_fmt(r['excess_win'], '%')} | {_fmt(r['mean_ret'], '%')} | "
            f"{_fmt(r['win_rate'], '%')} | {_fmt(r['pf'])} | {_fmt(r['worst'], '%')} |"
        )
    lines.append("")
    return lines


def build_report(all_trades, filters, base_excess) -> tuple[str, list[dict], list[dict]]:
    full_rows = [cohort_row(name, [t for t in all_trades if pred(t)])
                 for name, pred in filters.items()]
    hi = [t for t in all_trades if (t.get("composite_score") or 0) >= SCORE_CUTOFF]
    hi_rows = [cohort_row(name, [t for t in hi if pred(t)])
               for name, pred in filters.items()]

    lines = [
        "# VCP Breadth-Regime Experiment",
        "",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        f"Baseline (all trades) mean excess vs SPY: **{_fmt(base_excess, '%')}** — the "
        "no-filter row below must reproduce it exactly (sanity check).",
        "",
        "Breadth = % of S&P 500 above their 200-day MA, read as-of each trade's "
        "entry date. All regimes only *remove* trades from the fixed trade set.",
        "",
    ]
    lines += render_table("All trades — by breadth regime", full_rows)
    lines += render_table(f"Composite score >= {SCORE_CUTOFF:g} — by breadth regime", hi_rows)
    lines += [
        "## Caveats",
        "",
        "- Filtering shrinks N → weaker power; a higher mean with a wider CI is not",
        "  an improvement. Judge on the alpha (excess vs SPY) t-stat / CI, not the point.",
        "- The threshold sweep is in-sample selection (multiple testing); only a",
        "  large, monotonic, all-years-consistent lift is believable.",
        "- Excess-vs-SPY is market-neutral by construction, so a market-timing signal",
        "  moves absolute return/drawdown more than it moves market-relative alpha.",
        "",
    ]
    return "\n".join(lines), full_rows, hi_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="VCP breadth-regime experiment")
    parser.add_argument("trades_json", help="Path to a vcp_trades_*.json report")
    parser.add_argument("--breadth-csv", default=DEFAULT_BREADTH_CSV)
    parser.add_argument("--output-dir", default="backtests/")
    parser.add_argument(
        "--thresholds", nargs="+", type=float, default=[20, 30, 40, 50, 60]
    )
    args = parser.parse_args()

    with open(args.trades_json) as f:
        payload = json.load(f)
    raw_trades = payload.get("trades") or []
    if not raw_trades:
        print("ERROR: no trades in JSON", file=sys.stderr)
        sys.exit(1)
    base_excess = (payload.get("stats") or {}).get("primary_mean_excess_vs_spy_pct")

    series = load_breadth(args.breadth_csv)
    trades = attach_breadth(raw_trades, series)
    missing = sum(1 for t in trades if t["breadth"] is None)
    if missing:
        print(f"WARN: {missing}/{len(trades)} trades had no breadth reading", file=sys.stderr)

    filters = make_filters(args.thresholds)
    report, full_rows, hi_rows = build_report(trades, filters, base_excess)

    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    md_path = os.path.join(args.output_dir, f"vcp_breadth_experiment_{ts}.md")
    with open(md_path, "w") as f:
        f.write(report)

    # Console summary
    print("=" * 78)
    print(f"Breadth-regime experiment — {len(trades)} trades, "
          f"baseline excess {_fmt(base_excess, '%')}")
    print("=" * 78)
    hdr = f"{'Regime':<24}{'N':>4}{'mExcess':>9}{'t':>6}{'eWin%':>7}{'mRet':>8}{'PF':>6}{'worst':>8}"
    for label, rows in (("ALL TRADES", full_rows), (f"SCORE>={SCORE_CUTOFF:g}", hi_rows)):
        print(f"\n── {label} ──")
        print(hdr)
        print("-" * len(hdr))
        for r in rows:
            print(f"{r['name']:<24}{r['n']:>4}{_fmt(r['mean_excess']):>9}{_fmt(r['t_excess']):>6}"
                  f"{_fmt(r['excess_win']):>7}{_fmt(r['mean_ret']):>8}{_fmt(r['pf']):>6}"
                  f"{_fmt(r['worst']):>8}")
    print(f"\nMarkdown report: {md_path}")


if __name__ == "__main__":
    main()
