#!/usr/bin/env python3
"""Index forward-PE experiment — can market-level valuation
(S&P500ForwardPE.csv) improve the VCP trade results?

Two declared channels, fixed before looking at outcomes:

1. Market-valuation regime gate: trailing-5y percentile of the index forward
   P/E at detection (point-in-time), cheap half (<= 50) vs expensive half.
   Prior expectation from CLAUDE.md: null on excess-vs-SPY, which is
   market-neutral by construction — this is the same structural trap that
   killed the breadth / 200DMA / realized-vol gates. Raw returns are shown
   for completeness but are beta, not edge.
2. Relative stock valuation: rel_PE = stock trailing PE (from the PEG
   experiment) / index forward PE on the same date. This is the one genuinely
   new cross-time signal an index-level series can add — it removes the
   secular index re-rating from each stock's PE. Declared cut: rel_PE <= 1.5
   (at most a 50% premium to the market) vs > 1.5, plus scale-free Spearman.

Also reports the PEG <= 2 vs > 2 contrast *within* each market-valuation half,
to check whether the earlier PEG fold asymmetry lines up with market valuation
rather than calendar time.

Usage:
    python3 scripts/forward_pe_experiment.py backtests/vcp_trades_YYYY.json \
        --earnings-csv backtests/peg/earnings_events_peg.csv \
        --forward-pe-csv S&P500ForwardPE.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from bisect import bisect_right
from datetime import date, datetime, timedelta
from statistics import fmean

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from earnings_vcp_experiment import load_earnings_events
from edge_rank import spearman
from peg_experiment import PEG_FAIR_MAX, annotate_peg, cohort_row, trim_check, welch_t

STALE_DAYS = 45          # don't carry a forward-PE reading beyond this
PCTILE_YEARS = 5         # trailing window for the regime percentile
PCTILE_MIN_OBS = 30      # minimum observations inside that window
REGIME_CUT = 50.0        # cheap-market half vs expensive-market half
REL_PE_CUT = 1.5         # stock at most 50% premium to market vs more
FOLD_SPLIT_DATE = "2021-01-01"


def load_forward_pe(path: str) -> list[tuple[str, float]]:
    """Load (date, forward_pe) rows, validated and sorted by date."""
    out = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        missing = {"date", "forward_pe"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"forward-PE CSV missing columns: {sorted(missing)}")
        for line, row in enumerate(reader, 2):
            try:
                day = date.fromisoformat(row["date"].strip()).isoformat()
                value = float(row["forward_pe"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid forward-PE row {line}: {exc}") from exc
            if value <= 0:
                raise ValueError(f"invalid forward-PE row {line}: nonpositive value")
            out.append((day, value))
    return sorted(out)


def fpe_on_date(series: list[tuple[str, float]], asof: str) -> float | None:
    """Last forward-PE observation on or before asof, unless stale."""
    idx = bisect_right(series, (asof, float("inf")))
    if idx == 0:
        return None
    obs_date, value = series[idx - 1]
    age = (date.fromisoformat(asof) - date.fromisoformat(obs_date)).days
    return value if age <= STALE_DAYS else None


def trailing_percentile(series: list[tuple[str, float]], asof: str,
                        years: int = PCTILE_YEARS) -> float | None:
    """Midrank percentile of the current reading within its trailing window."""
    current = fpe_on_date(series, asof)
    if current is None:
        return None
    start = (date.fromisoformat(asof) - timedelta(days=round(years * 365.25))).isoformat()
    window = [v for d, v in series if start < d <= asof]
    if len(window) < PCTILE_MIN_OBS:
        return None
    less = sum(1 for v in window if v < current)
    equal = sum(1 for v in window if v == current)
    return (less + 0.5 * equal) / len(window) * 100.0


def annotate_market_valuation(trades: list[dict],
                              series: list[tuple[str, float]]) -> list[dict]:
    """Return new trade dicts with market forward-PE context (immutable)."""
    out = []
    for t in trades:
        fpe = fpe_on_date(series, t["as_of_date"])
        pct = trailing_percentile(series, t["as_of_date"])
        stock_pe = t.get("peg_pe")
        rel = stock_pe / fpe if stock_pe is not None and fpe else None
        out.append({**t, "market_fpe": fpe, "market_fpe_pct5y": pct, "rel_pe": rel})
    return out


def _fmt(v, digits=2, suffix=""):
    if v is None:
        return "—"
    if isinstance(v, (list, tuple)):
        return str(v)
    return f"{v:.{digits}f}{suffix}" if isinstance(v, float) else f"{v}{suffix}"


def make_cohorts() -> dict:
    return {
        "all (no filter)": lambda t: True,
        f"market pctile <= {REGIME_CUT:g} (cheap mkt)": lambda t:
            t["market_fpe_pct5y"] is not None and t["market_fpe_pct5y"] <= REGIME_CUT,
        f"market pctile > {REGIME_CUT:g} (dear mkt)": lambda t:
            t["market_fpe_pct5y"] is not None and t["market_fpe_pct5y"] > REGIME_CUT,
        f"rel PE <= {REL_PE_CUT:g}": lambda t:
            t["rel_pe"] is not None and t["rel_pe"] <= REL_PE_CUT,
        f"rel PE > {REL_PE_CUT:g}": lambda t:
            t["rel_pe"] is not None and t["rel_pe"] > REL_PE_CUT,
        "rel PE undefined": lambda t: t["rel_pe"] is None,
    }


def contrasts(trades: list[dict]) -> list[dict]:
    def pick(pred, field="excess_vs_spy_pct"):
        return [t[field] for t in trades if pred(t)]

    cheap_m = lambda t: t["market_fpe_pct5y"] is not None and t["market_fpe_pct5y"] <= REGIME_CUT
    dear_m = lambda t: t["market_fpe_pct5y"] is not None and t["market_fpe_pct5y"] > REGIME_CUT
    lo_rel = lambda t: t["rel_pe"] is not None and t["rel_pe"] <= REL_PE_CUT
    hi_rel = lambda t: t["rel_pe"] is not None and t["rel_pe"] > REL_PE_CUT
    rows = []
    for label, pa, pb, field in (
        ("cheap vs dear market (excess)", cheap_m, dear_m, "excess_vs_spy_pct"),
        ("cheap vs dear market (raw ret)", cheap_m, dear_m, "ret_pct"),
        (f"rel PE <= {REL_PE_CUT:g} vs > {REL_PE_CUT:g} (excess)", lo_rel, hi_rel,
         "excess_vs_spy_pct"),
    ):
        a, b = pick(pa, field), pick(pb, field)
        rows.append({"label": label, "n_a": len(a), "n_b": len(b),
                     "mean_a": fmean(a) if a else None,
                     "mean_b": fmean(b) if b else None, "welch_t": welch_t(a, b)})
    return rows


def peg_within_regime(trades: list[dict]) -> list[dict]:
    """PEG <= 2 vs > 2 (excess) inside each market-valuation half."""
    rows = []
    for label, regime in (
        (f"market pctile <= {REGIME_CUT:g}", lambda t:
            t["market_fpe_pct5y"] is not None and t["market_fpe_pct5y"] <= REGIME_CUT),
        (f"market pctile > {REGIME_CUT:g}", lambda t:
            t["market_fpe_pct5y"] is not None and t["market_fpe_pct5y"] > REGIME_CUT),
    ):
        sub = [t for t in trades if regime(t)]
        a = [t["excess_vs_spy_pct"] for t in sub
             if t.get("peg") is not None and t["peg"] <= PEG_FAIR_MAX]
        b = [t["excess_vs_spy_pct"] for t in sub
             if t.get("peg") is not None and t["peg"] > PEG_FAIR_MAX]
        rows.append({"label": label, "n_a": len(a), "n_b": len(b),
                     "mean_a": fmean(a) if a else None,
                     "mean_b": fmean(b) if b else None, "welch_t": welch_t(a, b)})
    return rows


def rel_pe_folds(trades: list[dict]) -> list[dict]:
    rows = []
    for fold, pred in (
        (f"< {FOLD_SPLIT_DATE[:4]}", lambda t: t["entry_date"] < FOLD_SPLIT_DATE),
        (f">= {FOLD_SPLIT_DATE[:4]}", lambda t: t["entry_date"] >= FOLD_SPLIT_DATE),
    ):
        sub = [t for t in trades if pred(t)]
        a = [t["excess_vs_spy_pct"] for t in sub
             if t["rel_pe"] is not None and t["rel_pe"] <= REL_PE_CUT]
        b = [t["excess_vs_spy_pct"] for t in sub
             if t["rel_pe"] is not None and t["rel_pe"] > REL_PE_CUT]
        rows.append({"fold": fold, "n_a": len(a), "n_b": len(b),
                     "mean_a": fmean(a) if a else None,
                     "mean_b": fmean(b) if b else None, "welch_t": welch_t(a, b)})
    return rows


def build_report(trades: list[dict], base_excess) -> tuple[str, list[dict]]:
    cohorts = make_cohorts()
    rows = [cohort_row(name, [t for t in trades if pred(t)])
            for name, pred in cohorts.items()]
    h2h = contrasts(trades)
    interaction = peg_within_regime(trades)
    folds = rel_pe_folds(trades)

    defined = [t for t in trades if t["rel_pe"] is not None]
    sp_rel = spearman([(t["rel_pe"], t["excess_vs_spy_pct"]) for t in defined])
    with_pct = [t for t in trades if t["market_fpe_pct5y"] is not None]
    sp_regime = spearman([(t["market_fpe_pct5y"], t["excess_vs_spy_pct"])
                          for t in with_pct])

    gated = [r for r in rows if r["name"] != "all (no filter)"]
    best = max((r for r in gated if r["mean_excess"] is not None),
               key=lambda r: r["mean_excess"], default=None)
    trim = {"name": best["name"], **trim_check(trades, cohorts[best["name"]])} if best else None

    lines = [
        "# VCP Index Forward-PE Experiment",
        "",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
        "",
        f"Baseline (all trades) mean excess vs SPY: **{_fmt(base_excess, suffix='%')}** — "
        "the no-filter row below must reproduce it exactly (sanity check).",
        "",
        "Index forward P/E (bottom-up consensus, ~weekly) used two declared ways: "
        f"(1) trailing-{PCTILE_YEARS}y percentile as a market-valuation regime gate, "
        f"(2) rel PE = stock trailing PE / index forward PE, cut at {REL_PE_CUT:g}. "
        "No threshold sweep.",
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
    lines += ["", "## Declared contrasts (Welch t)", "",
              "| Contrast | N (a/b) | Mean a | Mean b | Welch t |", "|---|---|---|---|---|"]
    for r in h2h:
        lines.append(f"| {r['label']} | {r['n_a']}/{r['n_b']} | {_fmt(r['mean_a'], suffix='%')} | "
                     f"{_fmt(r['mean_b'], suffix='%')} | {_fmt(r['welch_t'])} |")
    lines += [
        "",
        f"Spearman(rel PE, excess), n={len(defined)}: **{_fmt(sp_rel, 3)}**",
        "",
        f"Spearman(market pctile, excess), n={len(with_pct)}: **{_fmt(sp_regime, 3)}**",
        "",
        f"## PEG <= {PEG_FAIR_MAX:g} vs > {PEG_FAIR_MAX:g} within market-valuation halves",
        "",
        "| Regime | N (a/b) | Mean PEG<=2 | Mean PEG>2 | Welch t |", "|---|---|---|---|---|",
    ]
    for r in interaction:
        lines.append(f"| {r['label']} | {r['n_a']}/{r['n_b']} | {_fmt(r['mean_a'], suffix='%')} | "
                     f"{_fmt(r['mean_b'], suffix='%')} | {_fmt(r['welch_t'])} |")
    lines += ["", f"## Fold split ({FOLD_SPLIT_DATE[:4]}) — rel PE <= {REL_PE_CUT:g} vs > {REL_PE_CUT:g}",
              "", "| Fold | N (a/b) | Mean low rel PE | Mean high rel PE | Welch t |",
              "|---|---|---|---|---|"]
    for r in folds:
        lines.append(f"| {r['fold']} | {r['n_a']}/{r['n_b']} | {_fmt(r['mean_a'], suffix='%')} | "
                     f"{_fmt(r['mean_b'], suffix='%')} | {_fmt(r['welch_t'])} |")
    if trim:
        lines += ["", f"## Outlier trim — best gated cohort ({trim['name']})", "",
                  f"- full: n={trim['n_full']}, mean {_fmt(trim['mean_full'], suffix='%')}, "
                  f"t {_fmt(trim['t_full'])}",
                  f"- drop top 5: n={trim['n_trim']}, mean {_fmt(trim['mean_trim'], suffix='%')}, "
                  f"t {_fmt(trim['t_trim'])}"]
    lines += [
        "",
        "## Caveats",
        "",
        "- Excess-vs-SPY is market-neutral by construction: a market-level valuation",
        "  gate is structurally expected to be null on it (see breadth/vol/200DMA).",
        "- rel PE mixes a trailing stock PE with a forward index PE; it is a",
        "  detrending device, not a like-for-like valuation ratio.",
        "- Vendor forward-PE history may be restated; treated as best-effort PIT.",
        "- Raw-return rows are beta in a 2016–2026 bull tape, not edge.",
        "",
    ]
    return "\n".join(lines), rows


def main() -> None:
    parser = argparse.ArgumentParser(description="VCP index forward-PE experiment")
    parser.add_argument("trades_json", help="Path to a vcp_trades_*.json report")
    parser.add_argument("--earnings-csv", required=True)
    parser.add_argument("--forward-pe-csv", required=True)
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
    series = load_forward_pe(args.forward_pe_csv)
    trades = annotate_market_valuation(annotate_peg(raw_trades, events), series)
    missing = sum(1 for t in trades if t["market_fpe"] is None)
    if missing:
        print(f"WARN: {missing}/{len(trades)} trades had no forward-PE reading",
              file=sys.stderr)

    report, rows = build_report(trades, base_excess)
    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    md_path = os.path.join(args.output_dir, f"vcp_forward_pe_experiment_{ts}.md")
    with open(md_path, "w") as f:
        f.write(report)

    print("=" * 72)
    print(f"Forward-PE experiment — {len(trades)} trades, "
          f"baseline excess {_fmt(base_excess, suffix='%')}")
    print("=" * 72)
    hdr = f"{'Cohort':<34}{'N':>4}{'mExcess':>9}{'t':>7}{'eWin%':>7}{'PF':>6}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['name']:<34}{r['n']:>4}{_fmt(r['mean_excess']):>9}"
              f"{_fmt(r['t_excess']):>7}{_fmt(r['excess_win']):>7}{_fmt(r['pf']):>6}")
    print(f"\nMarkdown report: {md_path}")


if __name__ == "__main__":
    main()
