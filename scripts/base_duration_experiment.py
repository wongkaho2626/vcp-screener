#!/usr/bin/env python3
"""Prespecified test of base-duration (maturity) conditioning.

Frozen spec (backtests/base_duration/frozen_spec.md, declared 2026-07-17):
Minervini requires a proper VCP base to form over at least five weeks; shorter
"shelf" patterns are lower quality. Feature: vcp_pattern.pattern_duration_days
from detection metadata, joined to trades on (symbol, as_of_date). Declared
direction: mature (>= 35 calendar days) BETTER on per-trade excess vs SPY.
Pattern duration is complete at as_of_date, so the feature is causal. The
25/50-day splits are robustness checks only, never adopted.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
from datetime import datetime

from breakout_gap_experiment import fold_split, trim_top, two_sided_p, welch_t

FROZEN_THRESHOLD_DAYS = 35
SENSITIVITY_THRESHOLDS = (25, 50)
FOLD_BOUNDARY = "2021-01-01"


def build_pattern_index(detections_by_ticker: dict) -> dict:
    """(symbol, as_of_date) -> vcp_pattern dict, for trade joins."""
    index = {}
    for rows in detections_by_ticker.values():
        for row in rows:
            pattern = row.get("vcp_pattern") or {}
            index[(row["symbol"], row["as_of_date"])] = pattern
    return index


def annotate_duration(
    trades: list[dict], index: dict, threshold_days: int,
) -> tuple[list[dict], int]:
    """New trade dicts with pattern_duration_days and duration_group.

    Skips (and counts) trades with no joined detection or a non-positive
    duration.
    """
    annotated = []
    skipped = 0
    for trade in trades:
        pattern = index.get((trade["symbol"], trade["as_of_date"]))
        duration = (pattern or {}).get("pattern_duration_days") or 0
        if duration <= 0:
            skipped += 1
            continue
        group = "mature" if duration >= threshold_days else "short"
        annotated.append({**trade, "pattern_duration_days": duration,
                          "duration_group": group})
    return annotated, skipped


def analyze(trades: list[dict]) -> dict:
    """Group means, difference (mature - short), and Welch t."""
    mature = [t["excess_vs_spy_pct"] for t in trades if t["duration_group"] == "mature"]
    short = [t["excess_vs_spy_pct"] for t in trades if t["duration_group"] == "short"]
    t, df = welch_t(mature, short)
    return {
        "n_mature": len(mature),
        "n_short": len(short),
        "mean_mature": round(statistics.fmean(mature), 3) if mature else None,
        "mean_short": round(statistics.fmean(short), 3) if short else None,
        "diff": (
            round(statistics.fmean(mature) - statistics.fmean(short), 3)
            if mature and short else None
        ),
        "welch_t": round(t, 3) if t is not None else None,
        "df": round(df, 1) if df is not None else None,
        "p_two_sided": round(two_sided_p(t, df), 4) if t is not None else None,
    }


def spearman_duration_vs_excess(trades: list[dict]) -> dict:
    """Rank correlation of duration vs excess (declared: positive)."""
    try:
        from scipy import stats

        r = stats.spearmanr([t["pattern_duration_days"] for t in trades],
                            [t["excess_vs_spy_pct"] for t in trades])
        return {"spearman": round(float(r.statistic), 3),
                "p": round(float(r.pvalue), 4)}
    except ImportError:
        return {"spearman": None, "p": None}


def run_universe(trades: list[dict], index: dict) -> dict:
    frozen, skipped = annotate_duration(trades, index, FROZEN_THRESHOLD_DAYS)
    early, late = fold_split(frozen, FOLD_BOUNDARY)
    result = {
        "n_input": len(trades),
        "n_classified": len(frozen),
        "n_skipped": skipped,
        "duration_median_days": round(statistics.median(
            t["pattern_duration_days"] for t in frozen), 1) if frozen else None,
        "pooled": analyze(frozen),
        "spearman_duration_vs_excess": spearman_duration_vs_excess(frozen),
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
        alt, _ = annotate_duration(trades, index, thr)
        result["sensitivity_not_adopted"][f"threshold_{thr}d"] = analyze(alt)
    return result


def _fmt_row(label: str, s: dict) -> str:
    return (
        f"| {label} | {s['n_mature']} | {s['n_short']} | {s['mean_mature']} | "
        f"{s['mean_short']} | {s['diff']} | {s['welch_t']} | {s['p_two_sided']} |"
    )


def _universe_section(name: str, result: dict) -> list[str]:
    lines = [
        f"## {name} ({result['n_classified']} of {result['n_input']} trades "
        f"joined; {result['n_skipped']} skipped; median duration "
        f"{result['duration_median_days']} days)",
        "",
        "| Slice | n mature | n short | mean mature | mean short | diff (pp) | Welch t | p |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        _fmt_row("Pooled (frozen >=35d)", result["pooled"]),
    ]
    for fold_name, stats in result["folds"].items():
        lines.append(_fmt_row(f"Fold {fold_name}", stats))
    for trim_name, stats in result["outlier_trims"].items():
        lines.append(_fmt_row(trim_name, stats))
    for cell, stats in result["sensitivity_not_adopted"].items():
        lines.append(_fmt_row(f"{cell} (robustness only)", stats))
    sp = result["spearman_duration_vs_excess"]
    lines += ["", f"Spearman(duration, excess): {sp['spearman']} (p {sp['p']}) — "
              "declared direction positive.", ""]
    return lines


def _write_markdown(path: str, results: dict, meta: dict) -> None:
    lines = [
        "# Base-Duration (Maturity) Experiment",
        "",
        f"Generated: {meta['generated_at']}  ",
        f"Inputs: `{meta['inputs']}`  ",
        "Frozen spec: `backtests/base_duration/frozen_spec.md` (mature =",
        "pattern_duration_days >= 35; declared direction mature-better;",
        "declared before results)",
        "",
        "Detection-structure feature joined on (symbol, as_of_date); duration is",
        "complete at detection, so the feature is causal. Metric: per-trade",
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
        index.update(build_pattern_index(payload["detections_by_ticker"]))
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sp_trades_json")
    parser.add_argument("--sp-backtest", required=True)
    parser.add_argument("--r2k-trades", default=None)
    parser.add_argument("--r2k-backtest", action="append", default=[])
    parser.add_argument("--output-dir", default="backtests/base_duration")
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
    json_path = os.path.join(args.output_dir, f"base_duration_{stamp}.json")
    md_path = os.path.join(args.output_dir, f"base_duration_{stamp}.md")
    with open(json_path, "w") as f:
        json.dump({"metadata": meta, "results": results}, f, indent=1)
    _write_markdown(md_path, results, meta)
    print(f"wrote {json_path}\nwrote {md_path}")
    for name, result in results.items():
        print(name, json.dumps(result["pooled"]),
              "spearman:", json.dumps(result["spearman_duration_vs_excess"]))


if __name__ == "__main__":
    main()
