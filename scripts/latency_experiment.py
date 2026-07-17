#!/usr/bin/env python3
"""Prespecified test of detection-to-entry latency conditioning.

Frozen spec (backtests/latency/frozen_spec.md, declared 2026-07-17): the wait
between VCP detection (as_of_date) and breakout trigger (entry_date) reveals
demand; declared direction is fresh (latency <= 7 calendar days) BETTER on
per-trade excess vs SPY. Both dates are known at entry, so the feature is
causal. Trade-log fields only, so the R2K cross-universe prong runs offline.
The 4/14-day splits are robustness checks only, never adopted.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
from datetime import date
from datetime import datetime

from breakout_gap_experiment import fold_split, trim_top, two_sided_p, welch_t

FROZEN_THRESHOLD_DAYS = 7
SENSITIVITY_THRESHOLDS = (4, 14)
FOLD_BOUNDARY = "2021-01-01"


def annotate_latency(trades: list[dict], threshold_days: int) -> list[dict]:
    """New trade dicts with latency_days and latency_group.

    Negative latencies are data errors and are dropped.
    """
    annotated = []
    for trade in trades:
        latency = (date.fromisoformat(trade["entry_date"])
                   - date.fromisoformat(trade["as_of_date"])).days
        if latency < 0:
            continue
        group = "fresh" if latency <= threshold_days else "stale"
        annotated.append({**trade, "latency_days": latency,
                          "latency_group": group})
    return annotated


def analyze(trades: list[dict]) -> dict:
    """Group means, difference (fresh - stale), and Welch t."""
    fresh = [t["excess_vs_spy_pct"] for t in trades if t["latency_group"] == "fresh"]
    stale = [t["excess_vs_spy_pct"] for t in trades if t["latency_group"] == "stale"]
    t, df = welch_t(fresh, stale)
    return {
        "n_fresh": len(fresh),
        "n_stale": len(stale),
        "mean_fresh": round(statistics.fmean(fresh), 3) if fresh else None,
        "mean_stale": round(statistics.fmean(stale), 3) if stale else None,
        "diff": (
            round(statistics.fmean(fresh) - statistics.fmean(stale), 3)
            if fresh and stale else None
        ),
        "welch_t": round(t, 3) if t is not None else None,
        "df": round(df, 1) if df is not None else None,
        "p_two_sided": round(two_sided_p(t, df), 4) if t is not None else None,
    }


def run_universe(trades: list[dict]) -> dict:
    frozen = annotate_latency(trades, FROZEN_THRESHOLD_DAYS)
    early, late = fold_split(frozen, FOLD_BOUNDARY)
    result = {
        "n_input": len(trades),
        "n_classified": len(frozen),
        "latency_median_days": round(
            statistics.median(t["latency_days"] for t in frozen), 1) if frozen else None,
        "pooled": analyze(frozen),
        "folds": {
            f"2016-2020 (<{FOLD_BOUNDARY})": analyze(early),
            f"2021-2026 (>={FOLD_BOUNDARY})": analyze(late),
        },
        "outlier_trims": {
            "drop_top_5": analyze(trim_top(frozen, 5)),
            "drop_top_10": analyze(trim_top(frozen, 10)),
        },
        "sensitivity_not_adopted": {},
    }
    for thr in SENSITIVITY_THRESHOLDS:
        alt = annotate_latency(trades, thr)
        result["sensitivity_not_adopted"][f"threshold_{thr}d"] = analyze(alt)
    return result


def _fmt_row(label: str, s: dict) -> str:
    return (
        f"| {label} | {s['n_fresh']} | {s['n_stale']} | {s['mean_fresh']} | "
        f"{s['mean_stale']} | {s['diff']} | {s['welch_t']} | {s['p_two_sided']} |"
    )


def _universe_section(name: str, result: dict) -> list[str]:
    lines = [
        f"## {name} ({result['n_classified']} of {result['n_input']} trades "
        f"classified; median latency {result['latency_median_days']} days)",
        "",
        "| Slice | n fresh | n stale | mean fresh | mean stale | diff (pp) | Welch t | p |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        _fmt_row("Pooled (frozen <=7d)", result["pooled"]),
    ]
    for fold_name, stats in result["folds"].items():
        lines.append(_fmt_row(f"Fold {fold_name}", stats))
    for trim_name, stats in result["outlier_trims"].items():
        lines.append(_fmt_row(trim_name, stats))
    for cell, stats in result["sensitivity_not_adopted"].items():
        lines.append(_fmt_row(f"{cell} (robustness only)", stats))
    lines.append("")
    return lines


def _write_markdown(path: str, results: dict, meta: dict) -> None:
    lines = [
        "# Detection-to-Entry Latency Experiment",
        "",
        f"Generated: {meta['generated_at']}  ",
        f"S&P trades JSON: `{meta['sp_trades_json']}`  ",
        f"R2K trades JSON: `{meta['r2k_trades_json']}`  ",
        "Frozen spec: `backtests/latency/frozen_spec.md` (fresh = entry within",
        "7 calendar days of detection; declared direction fresh-better;",
        "declared before results)",
        "",
        "Trade-log-only feature (both dates known at entry), so both universes",
        "replicate offline. Metric: per-trade excess vs SPY from the source",
        "logs; groups share fill/cost models, so the difference is",
        "cost-invariant. Universes are survivorship-biased; all numbers are",
        "optimistic ceilings. Sensitivity rows are robustness checks, not a",
        "search; no variation is adopted.",
        "",
    ]
    for name, result in results.items():
        lines.extend(_universe_section(name, result))
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sp_trades_json")
    parser.add_argument("--r2k-trades", default=None)
    parser.add_argument("--output-dir", default="backtests/latency")
    args = parser.parse_args()

    with open(args.sp_trades_json) as f:
        sp_trades = json.load(f)["trades"]
    results = {"S&P 500": run_universe(sp_trades)}
    if args.r2k_trades:
        with open(args.r2k_trades) as f:
            results["Russell 2000"] = run_universe(json.load(f)["trades"])

    meta = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sp_trades_json": args.sp_trades_json,
        "r2k_trades_json": args.r2k_trades or "not supplied",
    }
    os.makedirs(args.output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = os.path.join(args.output_dir, f"latency_{stamp}.json")
    md_path = os.path.join(args.output_dir, f"latency_{stamp}.md")
    with open(json_path, "w") as f:
        json.dump({"metadata": meta, "results": results}, f, indent=1)
    _write_markdown(md_path, results, meta)
    print(f"wrote {json_path}\nwrote {md_path}")
    for name, result in results.items():
        print(name, json.dumps(result["pooled"]))


if __name__ == "__main__":
    main()
