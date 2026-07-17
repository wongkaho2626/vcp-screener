#!/usr/bin/env python3
"""Prespecified test of initial stop-width (base tightness) conditioning.

Frozen spec (backtests/stop_width/frozen_spec.md, declared 2026-07-17): the
initial risk width risk_pct = (entry - stop) / entry measures base looseness;
declared direction is tight (risk_pct <= 6%) BETTER on per-trade excess vs SPY.
Both prices are fixed at entry, so the feature is causal. Trade-log fields only,
so the R2K cross-universe prong runs offline. The 5%/7% splits are robustness
checks only, never adopted. The exit_reason mix per group is reported to
separate "tightness predicts quality" from "tight stops die early".
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
from collections import Counter
from datetime import datetime

from breakout_gap_experiment import fold_split, trim_top, two_sided_p, welch_t

FROZEN_THRESHOLD_PCT = 6.0
SENSITIVITY_THRESHOLDS = (5.0, 7.0)
FOLD_BOUNDARY = "2021-01-01"


def annotate_stop_width(trades: list[dict], threshold_pct: float) -> list[dict]:
    """New trade dicts with risk_pct and width_group; invalid prices dropped."""
    annotated = []
    for trade in trades:
        entry = trade.get("entry_price") or 0.0
        stop = trade.get("stop_price") or 0.0
        if entry <= 0 or stop <= 0 or stop >= entry:
            continue
        risk_pct = (entry - stop) / entry * 100.0
        group = "tight" if risk_pct <= threshold_pct else "wide"
        annotated.append({**trade, "risk_pct": round(risk_pct, 3),
                          "width_group": group})
    return annotated


def analyze(trades: list[dict]) -> dict:
    """Group means, difference (tight - wide), and Welch t."""
    tight = [t["excess_vs_spy_pct"] for t in trades if t["width_group"] == "tight"]
    wide = [t["excess_vs_spy_pct"] for t in trades if t["width_group"] == "wide"]
    t, df = welch_t(tight, wide)
    return {
        "n_tight": len(tight),
        "n_wide": len(wide),
        "mean_tight": round(statistics.fmean(tight), 3) if tight else None,
        "mean_wide": round(statistics.fmean(wide), 3) if wide else None,
        "diff": (
            round(statistics.fmean(tight) - statistics.fmean(wide), 3)
            if tight and wide else None
        ),
        "welch_t": round(t, 3) if t is not None else None,
        "df": round(df, 1) if df is not None else None,
        "p_two_sided": round(two_sided_p(t, df), 4) if t is not None else None,
    }


def exit_mix(trades: list[dict]) -> dict:
    """exit_reason distribution per width group, for the declared confound."""
    mix = {}
    for group in ("tight", "wide"):
        rows = [t for t in trades if t["width_group"] == group]
        counts = Counter(t.get("exit_reason", "unknown") for t in rows)
        total = len(rows) or 1
        mix[group] = {
            reason: round(count / total * 100.0, 1)
            for reason, count in sorted(counts.items())
        }
    return mix


def run_universe(trades: list[dict]) -> dict:
    frozen = annotate_stop_width(trades, FROZEN_THRESHOLD_PCT)
    early, late = fold_split(frozen, FOLD_BOUNDARY)
    result = {
        "n_input": len(trades),
        "n_classified": len(frozen),
        "risk_pct_median": round(
            statistics.median(t["risk_pct"] for t in frozen), 2) if frozen else None,
        "pooled": analyze(frozen),
        "exit_reason_mix_pct": exit_mix(frozen),
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
        alt = annotate_stop_width(trades, thr)
        result["sensitivity_not_adopted"][f"threshold_{thr}pct"] = analyze(alt)
    return result


def _fmt_row(label: str, s: dict) -> str:
    return (
        f"| {label} | {s['n_tight']} | {s['n_wide']} | {s['mean_tight']} | "
        f"{s['mean_wide']} | {s['diff']} | {s['welch_t']} | {s['p_two_sided']} |"
    )


def _universe_section(name: str, result: dict) -> list[str]:
    lines = [
        f"## {name} ({result['n_classified']} of {result['n_input']} trades "
        f"classified; median risk {result['risk_pct_median']}%)",
        "",
        "| Slice | n tight | n wide | mean tight | mean wide | diff (pp) | Welch t | p |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        _fmt_row("Pooled (frozen <=6%)", result["pooled"]),
    ]
    for fold_name, stats in result["folds"].items():
        lines.append(_fmt_row(f"Fold {fold_name}", stats))
    for trim_name, stats in result["outlier_trims"].items():
        lines.append(_fmt_row(trim_name, stats))
    for cell, stats in result["sensitivity_not_adopted"].items():
        lines.append(_fmt_row(f"{cell} (robustness only)", stats))
    lines += ["", f"Exit-reason mix (%): `{json.dumps(result['exit_reason_mix_pct'])}`", ""]
    return lines


def _write_markdown(path: str, results: dict, meta: dict) -> None:
    lines = [
        "# Initial Stop-Width (Base Tightness) Experiment",
        "",
        f"Generated: {meta['generated_at']}  ",
        f"S&P trades JSON: `{meta['sp_trades_json']}`  ",
        f"R2K trades JSON: `{meta['r2k_trades_json']}`  ",
        "Frozen spec: `backtests/stop_width/frozen_spec.md` (tight = risk <= 6%,",
        "declared direction tight-better, declared before results)",
        "",
        "Trade-log-only feature (entry/stop fixed at entry), so both universes",
        "replicate offline. Metric: per-trade excess vs SPY from the source logs;",
        "groups share fill/cost models, so the difference is cost-invariant.",
        "Declared confound: stop width mechanically changes stop-out frequency —",
        "see the exit-reason mix per group. Universes are survivorship-biased;",
        "all numbers are optimistic ceilings. Sensitivity rows are robustness",
        "checks, not a search; no variation is adopted.",
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
    parser.add_argument("--output-dir", default="backtests/stop_width")
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
    json_path = os.path.join(args.output_dir, f"stop_width_{stamp}.json")
    md_path = os.path.join(args.output_dir, f"stop_width_{stamp}.md")
    with open(json_path, "w") as f:
        json.dump({"metadata": meta, "results": results}, f, indent=1)
    _write_markdown(md_path, results, meta)
    print(f"wrote {json_path}\nwrote {md_path}")
    for name, result in results.items():
        print(name, json.dumps(result["pooled"]))


if __name__ == "__main__":
    main()
