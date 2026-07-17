#!/usr/bin/env python3
"""Trailing-PEG experiment — does valuation at detection explain VCP trade
outcomes?

"Method 1" from the data-sourcing discussion: PEG built entirely from free
Yahoo data. Trailing P/E uses the trade's own fill price divided by
trailing-twelve-month street EPS (sum of the last four reported quarterly EPS
from the earnings-events cache, point-in-time by announcement date). Growth is
the year-over-year change of that TTM figure, so this is a *trailing* PEG —
no analyst forward estimates are available for free historically.

    PEG = (entry_price / TTM_EPS) / YoY_TTM_growth_pct

PEG is only defined for TTM > 0 and growth > 0; loss-makers and decelerating
names are reported as their own cohorts rather than silently dropped. The
PEG bands (<=1 cheap / <=2 fair / >2 expensive) are the conventional
textbook cuts, declared before looking at results — no threshold sweep.

Usage:
    python3 scripts/peg_experiment.py backtests/vcp_trades_YYYY.json \
        --earnings-csv backtests/peg/earnings_events_peg.csv
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import date, datetime
from statistics import fmean, variance

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from earnings_vcp_experiment import load_earnings_events
from edge_rank import spearman
from trade_simulator import compute_trade_stats

# A clean 4-quarter announcement window spans ~9 months; anything wider means
# quarters are missing from the cache and the TTM sum would be corrupt.
RECENT_WINDOW_DAYS = 400
PRIOR_WINDOW_DAYS = 800
PEG_CHEAP_MAX = 1.0
PEG_FAIR_MAX = 2.0
FOLD_SPLIT_DATE = "2021-01-01"  # house robustness bar: 2016-2020 vs 2021-2026


def compute_peg(entry_price: float, events: list[dict], asof: str) -> dict:
    """Trailing PEG from point-in-time quarterly EPS events (oldest first).

    Returns {status, peg, pe, ttm_eps, growth_pct}; peg is None unless
    status == "ok".
    """
    base = {"peg": None, "pe": None, "ttm_eps": None, "growth_pct": None}
    past = [e for e in events if e["event_date"] <= asof]
    if len(past) < 8:
        return {**base, "status": "insufficient_history"}
    recent, prior = past[-4:], past[-8:-4]
    asof_day = date.fromisoformat(asof)
    recent_age = (asof_day - date.fromisoformat(recent[0]["event_date"])).days
    prior_age = (asof_day - date.fromisoformat(prior[0]["event_date"])).days
    if recent_age > RECENT_WINDOW_DAYS or prior_age > PRIOR_WINDOW_DAYS:
        return {**base, "status": "stale_history"}
    ttm = sum(e["reported_eps"] for e in recent)
    prior_ttm = sum(e["reported_eps"] for e in prior)
    if ttm <= 0:
        return {**base, "status": "nonpositive_ttm", "ttm_eps": ttm}
    pe = entry_price / ttm
    if prior_ttm <= 0:
        return {**base, "status": "nonpositive_growth", "ttm_eps": ttm, "pe": pe}
    growth_pct = (ttm / prior_ttm - 1.0) * 100.0
    if growth_pct <= 0:
        return {**base, "status": "nonpositive_growth", "ttm_eps": ttm,
                "pe": pe, "growth_pct": growth_pct}
    return {"status": "ok", "peg": pe / growth_pct, "pe": pe,
            "ttm_eps": ttm, "growth_pct": growth_pct}


def annotate_peg(trades: list[dict], events_by_symbol: dict[str, list[dict]]) -> list[dict]:
    """Return new trade dicts with PEG-at-detection attached (immutable)."""
    out = []
    for t in trades:
        events = events_by_symbol.get(t["symbol"])
        if not events:
            info = {"status": "no_earnings_data", "peg": None, "pe": None,
                    "ttm_eps": None, "growth_pct": None}
        else:
            info = compute_peg(t["entry_price"], events, t["as_of_date"])
        out.append({**t, "peg": info["peg"], "peg_status": info["status"],
                    "peg_pe": info["pe"], "peg_growth_pct": info["growth_pct"]})
    return out


def welch_t(a: list[float], b: list[float]) -> float | None:
    if len(a) < 2 or len(b) < 2:
        return None
    se = math.sqrt(variance(a) / len(a) + variance(b) / len(b))
    return (fmean(a) - fmean(b)) / se if se else None


def make_cohorts() -> dict:
    """Named predicates over a PEG-annotated trade dict (declared, no sweep)."""
    return {
        "all (no filter)": lambda t: True,
        "PEG defined": lambda t: t["peg_status"] == "ok",
        f"PEG <= {PEG_CHEAP_MAX:g} (cheap)": lambda t: t["peg"] is not None
        and t["peg"] <= PEG_CHEAP_MAX,
        f"{PEG_CHEAP_MAX:g} < PEG <= {PEG_FAIR_MAX:g} (fair)": lambda t: t["peg"] is not None
        and PEG_CHEAP_MAX < t["peg"] <= PEG_FAIR_MAX,
        f"PEG > {PEG_FAIR_MAX:g} (expensive)": lambda t: t["peg"] is not None
        and t["peg"] > PEG_FAIR_MAX,
        "growth <= 0 (PEG undefined)": lambda t: t["peg_status"] == "nonpositive_growth",
        "TTM EPS <= 0 (loss-maker)": lambda t: t["peg_status"] == "nonpositive_ttm",
        "no/stale/short data": lambda t: t["peg_status"]
        in ("no_earnings_data", "insufficient_history", "stale_history"),
    }


def cohort_row(name: str, trades: list[dict]) -> dict:
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
    }


def head_to_head(trades: list[dict]) -> list[dict]:
    """Declared pairwise contrasts on excess vs SPY (Welch t)."""
    def excess(pred):
        return [t["excess_vs_spy_pct"] for t in trades if pred(t)]

    cheapish = excess(lambda t: t["peg"] is not None and t["peg"] <= PEG_FAIR_MAX)
    expensive = excess(lambda t: t["peg"] is not None and t["peg"] > PEG_FAIR_MAX)
    defined = excess(lambda t: t["peg_status"] == "ok")
    decel = excess(lambda t: t["peg_status"] == "nonpositive_growth")
    rows = []
    for label, a, b in (
        (f"PEG <= {PEG_FAIR_MAX:g} vs PEG > {PEG_FAIR_MAX:g}", cheapish, expensive),
        ("PEG defined vs growth <= 0", defined, decel),
    ):
        t_stat = welch_t(a, b)
        rows.append({
            "label": label, "n_a": len(a), "n_b": len(b),
            "mean_a": fmean(a) if a else None, "mean_b": fmean(b) if b else None,
            "welch_t": t_stat,
        })
    return rows


def fold_rows(trades: list[dict]) -> list[dict]:
    rows = []
    for fold, pred in (
        (f"< {FOLD_SPLIT_DATE[:4]}", lambda t: t["entry_date"] < FOLD_SPLIT_DATE),
        (f">= {FOLD_SPLIT_DATE[:4]}", lambda t: t["entry_date"] >= FOLD_SPLIT_DATE),
    ):
        sub = [t for t in trades if pred(t)]
        a = [t["excess_vs_spy_pct"] for t in sub
             if t["peg"] is not None and t["peg"] <= PEG_FAIR_MAX]
        b = [t["excess_vs_spy_pct"] for t in sub
             if t["peg"] is not None and t["peg"] > PEG_FAIR_MAX]
        rows.append({"fold": fold, "n_a": len(a), "n_b": len(b),
                     "mean_a": fmean(a) if a else None,
                     "mean_b": fmean(b) if b else None,
                     "welch_t": welch_t(a, b)})
    return rows


def trim_check(trades: list[dict], pred, drop: int = 5) -> dict:
    """Drop the top `drop` excess winners from a cohort — does the mean survive?"""
    vals = sorted((t["excess_vs_spy_pct"] for t in trades if pred(t)), reverse=True)
    trimmed = vals[drop:]

    def t_stat(v):
        if len(v) < 2:
            return None
        sd = math.sqrt(variance(v))
        return fmean(v) / (sd / math.sqrt(len(v))) if sd else None

    return {"n_full": len(vals), "mean_full": fmean(vals) if vals else None,
            "t_full": t_stat(vals), "n_trim": len(trimmed),
            "mean_trim": fmean(trimmed) if trimmed else None, "t_trim": t_stat(trimmed)}


def _fmt(v, digits=2, suffix=""):
    if v is None:
        return "—"
    if isinstance(v, (list, tuple)):
        return str(v)
    return f"{v:.{digits}f}{suffix}" if isinstance(v, float) else f"{v}{suffix}"


def build_report(trades: list[dict], base_excess) -> tuple[str, list[dict]]:
    cohorts = make_cohorts()
    rows = [cohort_row(name, [t for t in trades if pred(t)])
            for name, pred in cohorts.items()]

    ok = [t for t in trades if t["peg_status"] == "ok"]
    sp_peg = spearman([(t["peg"], t["excess_vs_spy_pct"]) for t in ok])
    growth_pairs = [(t["peg_growth_pct"], t["excess_vs_spy_pct"]) for t in trades
                    if t["peg_growth_pct"] is not None]
    sp_growth = spearman(growth_pairs)

    h2h = head_to_head(trades)
    folds = fold_rows(trades)

    band_rows = [r for r in rows if "cheap" in r["name"] or "fair" in r["name"]
                 or "expensive" in r["name"]]
    best = max((r for r in band_rows if r["mean_excess"] is not None),
               key=lambda r: r["mean_excess"], default=None)
    trim = None
    if best:
        pred = cohorts[best["name"]]
        trim = {"name": best["name"], **trim_check(trades, pred)}

    status_counts = {}
    for t in trades:
        status_counts[t["peg_status"]] = status_counts.get(t["peg_status"], 0) + 1

    lines = [
        "# VCP Trailing-PEG Experiment",
        "",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        f"Baseline (all trades) mean excess vs SPY: **{_fmt(base_excess, suffix='%')}** — "
        "the no-filter row below must reproduce it exactly (sanity check).",
        "",
        "Trailing PEG at detection date, from free Yahoo data: PE = fill price / "
        "TTM street EPS (last 4 reported quarters, point-in-time by announcement "
        "date); growth = YoY change in TTM EPS. PEG bands are the textbook "
        "<=1 / <=2 / >2 cuts, declared up front. This is a *trailing* PEG — no "
        "historical forward estimates exist in free data.",
        "",
        "## Data coverage",
        "",
    ] + [f"- {k}: {v}" for k, v in sorted(status_counts.items())] + [
        "",
        "## Cohorts (excess vs SPY is the alpha test)",
        "",
        "| Cohort | N | Mean excess | t | 95% CI | Excess win% | Mean ret | Win% | PF |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['name']} | {r['n']} | {_fmt(r['mean_excess'], suffix='%')} | "
            f"{_fmt(r['t_excess'])} | {_fmt(r['ci_excess'])} | {_fmt(r['excess_win'], suffix='%')} | "
            f"{_fmt(r['mean_ret'], suffix='%')} | {_fmt(r['win_rate'], suffix='%')} | {_fmt(r['pf'])} |"
        )
    lines += [
        "",
        "## Declared contrasts (Welch t on excess vs SPY)",
        "",
        "| Contrast | N (a/b) | Mean a | Mean b | Welch t |",
        "|---|---|---|---|---|",
    ]
    for r in h2h:
        lines.append(f"| {r['label']} | {r['n_a']}/{r['n_b']} | {_fmt(r['mean_a'], suffix='%')} | "
                     f"{_fmt(r['mean_b'], suffix='%')} | {_fmt(r['welch_t'])} |")
    lines += [
        "",
        f"Spearman(PEG, excess) on defined-PEG trades (n={len(ok)}): **{_fmt(sp_peg, 3)}**",
        "",
        f"Spearman(TTM growth, excess) where growth defined (n={len(growth_pairs)}): "
        f"**{_fmt(sp_growth, 3)}**",
        "",
        f"## Fold split ({FOLD_SPLIT_DATE[:4]}) — PEG <= {PEG_FAIR_MAX:g} vs > {PEG_FAIR_MAX:g}",
        "",
        "| Fold | N (a/b) | Mean cheap-ish | Mean expensive | Welch t |",
        "|---|---|---|---|---|",
    ]
    for r in folds:
        lines.append(f"| {r['fold']} | {r['n_a']}/{r['n_b']} | {_fmt(r['mean_a'], suffix='%')} | "
                     f"{_fmt(r['mean_b'], suffix='%')} | {_fmt(r['welch_t'])} |")
    if trim:
        lines += [
            "",
            f"## Outlier trim — best PEG band ({trim['name']})",
            "",
            f"- full: n={trim['n_full']}, mean {_fmt(trim['mean_full'], suffix='%')}, "
            f"t {_fmt(trim['t_full'])}",
            f"- drop top 5: n={trim['n_trim']}, mean {_fmt(trim['mean_trim'], suffix='%')}, "
            f"t {_fmt(trim['t_trim'])}",
        ]
    lines += [
        "",
        "## Caveats",
        "",
        "- Trailing PEG (realized growth), not the forward PEG practitioners quote;",
        "  the two can disagree badly around earnings inflections.",
        "- Yahoo street EPS is as-announced (point-in-time by event date) but the",
        "  vendor may restate history; treat as best-effort PIT, not IBES-grade.",
        "- Band cuts are conventional but the multiple-cohort table is still",
        "  multiple testing; judge on the declared contrasts + fold + trim, not",
        "  the single best cell.",
        "- Excess-vs-SPY is market-neutral by construction; valuation regime",
        "  effects on the index itself are invisible here.",
        "",
    ]
    return "\n".join(lines), rows


def main() -> None:
    parser = argparse.ArgumentParser(description="VCP trailing-PEG experiment")
    parser.add_argument("trades_json", help="Path to a vcp_trades_*.json report")
    parser.add_argument("--earnings-csv", required=True,
                        help="Earnings events CSV (symbol,event_date,...,reported_eps,...)")
    parser.add_argument("--output-dir", default="backtests/peg")
    args = parser.parse_args()

    with open(args.trades_json) as f:
        payload = json.load(f)
    raw_trades = payload.get("trades") or []
    if not raw_trades:
        print("ERROR: no trades in JSON", file=sys.stderr)
        sys.exit(1)
    base_excess = (payload.get("stats") or {}).get("primary_mean_excess_vs_spy_pct")

    events = load_earnings_events(args.earnings_csv)
    trades = annotate_peg(raw_trades, events)
    report, rows = build_report(trades, base_excess)

    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    md_path = os.path.join(args.output_dir, f"vcp_peg_experiment_{ts}.md")
    with open(md_path, "w") as f:
        f.write(report)

    print("=" * 72)
    print(f"Trailing-PEG experiment — {len(trades)} trades, "
          f"baseline excess {_fmt(base_excess, suffix='%')}")
    print("=" * 72)
    hdr = f"{'Cohort':<30}{'N':>4}{'mExcess':>9}{'t':>7}{'eWin%':>7}{'PF':>6}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['name']:<30}{r['n']:>4}{_fmt(r['mean_excess']):>9}"
              f"{_fmt(r['t_excess']):>7}{_fmt(r['excess_win']):>7}{_fmt(r['pf']):>6}")
    print(f"\nMarkdown report: {md_path}")


if __name__ == "__main__":
    main()
