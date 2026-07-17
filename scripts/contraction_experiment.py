#!/usr/bin/env python3
"""Prespecified test of contraction-tightening sequence conditioning.

Frozen spec (backtests/contraction/frozen_spec.md, declared 2026-07-17):
Minervini's textbook VCP wants each contraction roughly half the prior one.
Feature: tightening_ratio = last contraction depth / first contraction depth,
from the detection metadata (vcp_pattern.contractions), joined to trades on
(symbol, as_of_date). Declared direction: tight sequences (ratio <= 0.5) earn
higher per-trade excess vs SPY. Contraction geometry is fully formed at
as_of_date, so the feature is causal. The 0.4/0.6 splits are robustness checks
only, never adopted.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
from datetime import datetime

from breakout_gap_experiment import fold_split, trim_top, two_sided_p, welch_t

FROZEN_THRESHOLD = 0.5
SENSITIVITY_THRESHOLDS = (0.4, 0.6)
FOLD_BOUNDARY = "2021-01-01"


def build_detection_index(detections_by_ticker: dict) -> dict:
    """(symbol, as_of_date) -> contraction list, for trade joins."""
    index = {}
    for rows in detections_by_ticker.values():
        for row in rows:
            contractions = (row.get("vcp_pattern") or {}).get("contractions") or []
            index[(row["symbol"], row["as_of_date"])] = contractions
    return index


def annotate_tightening(
    trades: list[dict], index: dict, threshold: float,
) -> tuple[list[dict], int]:
    """New trade dicts with tightening_ratio and tighten_group.

    Skips (and counts) trades with no joined detection, fewer than two
    contractions, or a non-positive first depth.
    """
    annotated = []
    skipped = 0
    for trade in trades:
        contractions = index.get((trade["symbol"], trade["as_of_date"]))
        if not contractions or len(contractions) < 2:
            skipped += 1
            continue
        first = contractions[0].get("depth_pct") or 0.0
        last = contractions[-1].get("depth_pct") or 0.0
        if first <= 0 or last < 0:
            skipped += 1
            continue
        ratio = last / first
        group = "tight" if ratio <= threshold else "loose"
        annotated.append({**trade, "tightening_ratio": round(ratio, 4),
                          "tighten_group": group})
    return annotated, skipped


def analyze(trades: list[dict]) -> dict:
    """Group means, difference (tight - loose), and Welch t."""
    tight = [t["excess_vs_spy_pct"] for t in trades if t["tighten_group"] == "tight"]
    loose = [t["excess_vs_spy_pct"] for t in trades if t["tighten_group"] == "loose"]
    t, df = welch_t(tight, loose)
    return {
        "n_tight": len(tight),
        "n_loose": len(loose),
        "mean_tight": round(statistics.fmean(tight), 3) if tight else None,
        "mean_loose": round(statistics.fmean(loose), 3) if loose else None,
        "diff": (
            round(statistics.fmean(tight) - statistics.fmean(loose), 3)
            if tight and loose else None
        ),
        "welch_t": round(t, 3) if t is not None else None,
        "df": round(df, 1) if df is not None else None,
        "p_two_sided": round(two_sided_p(t, df), 4) if t is not None else None,
    }


def spearman_ratio_vs_excess(trades: list[dict]) -> dict:
    """Rank correlation of tightening_ratio vs excess (declared: negative)."""
    try:
        from scipy import stats

        r = stats.spearmanr([t["tightening_ratio"] for t in trades],
                            [t["excess_vs_spy_pct"] for t in trades])
        return {"spearman": round(float(r.statistic), 3),
                "p": round(float(r.pvalue), 4)}
    except ImportError:
        return {"spearman": None, "p": None}


def run_universe(trades: list[dict], index: dict) -> dict:
    frozen, skipped = annotate_tightening(trades, index, FROZEN_THRESHOLD)
    early, late = fold_split(frozen, FOLD_BOUNDARY)
    result = {
        "n_input": len(trades),
        "n_classified": len(frozen),
        "n_skipped": skipped,
        "ratio_median": round(
            statistics.median(t["tightening_ratio"] for t in frozen), 3)
        if frozen else None,
        "pooled": analyze(frozen),
        "spearman_ratio_vs_excess": spearman_ratio_vs_excess(frozen),
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
        alt, _ = annotate_tightening(trades, index, thr)
        result["sensitivity_not_adopted"][f"threshold_{thr}"] = analyze(alt)
    return result


def _fmt_row(label: str, s: dict) -> str:
    return (
        f"| {label} | {s['n_tight']} | {s['n_loose']} | {s['mean_tight']} | "
        f"{s['mean_loose']} | {s['diff']} | {s['welch_t']} | {s['p_two_sided']} |"
    )


def _universe_section(name: str, result: dict) -> list[str]:
    lines = [
        f"## {name} ({result['n_classified']} of {result['n_input']} trades "
        f"joined; {result['n_skipped']} skipped; median ratio "
        f"{result['ratio_median']})",
        "",
        "| Slice | n tight | n loose | mean tight | mean loose | diff (pp) | Welch t | p |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        _fmt_row("Pooled (frozen <=0.5)", result["pooled"]),
    ]
    for fold_name, stats in result["folds"].items():
        lines.append(_fmt_row(f"Fold {fold_name}", stats))
    for trim_name, stats in result["outlier_trims"].items():
        lines.append(_fmt_row(trim_name, stats))
    for cell, stats in result["sensitivity_not_adopted"].items():
        lines.append(_fmt_row(f"{cell} (robustness only)", stats))
    sp = result["spearman_ratio_vs_excess"]
    lines += ["", f"Spearman(ratio, excess): {sp['spearman']} (p {sp['p']}) — "
              "declared direction negative.", ""]
    return lines


def _write_markdown(path: str, results: dict, meta: dict) -> None:
    lines = [
        "# Contraction-Tightening Sequence Experiment",
        "",
        f"Generated: {meta['generated_at']}  ",
        f"Inputs: `{meta['inputs']}`  ",
        "Frozen spec: `backtests/contraction/frozen_spec.md` (tight = last/first",
        "contraction depth <= 0.5; declared direction tight-better; declared",
        "before results)",
        "",
        "Detection-structure feature joined on (symbol, as_of_date); geometry is",
        "fully formed at detection, so the feature is causal. Metric: per-trade",
        "excess vs SPY from the source logs; groups share fill/cost models, so",
        "the difference is cost-invariant. Universes are survivorship-biased;",
        "all numbers are optimistic ceilings. Sensitivity rows are robustness",
        "checks, not a search; no variation is adopted.",
        "",
    ]
    for name, result in results.items():
        lines.extend(_universe_section(name, result))
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def _load_index(paths: list[str]) -> dict:
    index = {}
    for path in paths:
        with open(path) as f:
            payload = json.load(f)
        index.update(build_detection_index(payload["detections_by_ticker"]))
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sp_trades_json")
    parser.add_argument("--sp-backtest", required=True)
    parser.add_argument("--r2k-trades", default=None)
    parser.add_argument("--r2k-backtest", action="append", default=[])
    parser.add_argument("--output-dir", default="backtests/contraction")
    args = parser.parse_args()

    with open(args.sp_trades_json) as f:
        sp_trades = json.load(f)["trades"]
    results = {"S&P 500": run_universe(sp_trades, _load_index([args.sp_backtest]))}
    if args.r2k_trades and args.r2k_backtest:
        with open(args.r2k_trades) as f:
            r2k_trades = json.load(f)["trades"]
        results["Russell 2000"] = run_universe(
            r2k_trades, _load_index(args.r2k_backtest))

    meta = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "inputs": {
            "sp_trades": args.sp_trades_json,
            "sp_backtest": args.sp_backtest,
            "r2k_trades": args.r2k_trades or "not supplied",
            "r2k_backtests": args.r2k_backtest or "not supplied",
        },
    }
    os.makedirs(args.output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = os.path.join(args.output_dir, f"contraction_{stamp}.json")
    md_path = os.path.join(args.output_dir, f"contraction_{stamp}.md")
    with open(json_path, "w") as f:
        json.dump({"metadata": meta, "results": results}, f, indent=1)
    _write_markdown(md_path, results, meta)
    print(f"wrote {json_path}\nwrote {md_path}")
    for name, result in results.items():
        print(name, json.dumps(result["pooled"]),
              "spearman:", json.dumps(result["spearman_ratio_vs_excess"]))


if __name__ == "__main__":
    main()
