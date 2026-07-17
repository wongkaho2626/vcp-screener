#!/usr/bin/env python3
"""Prespecified test of VCP signal-crowding conditioning.

Frozen spec (backtests/crowding/frozen_spec.md, declared 2026-07-17): a trade is
"crowded" when >= 2 other trades in the same universe have as_of_date within the
trailing 10 calendar days (inclusive) of its own as_of_date; declared direction
is crowded WORSE on per-trade excess vs SPY. Strictly causal: as_of_date is the
detection date and only trailing detections are counted. No price bars are
needed, so the R2K cross-universe prong runs from its trade log alone. Window
5/15 and min-prior 1/3 cells are robustness checks only, never adopted.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
from datetime import date, timedelta

from breakout_gap_experiment import fold_split, trim_top, two_sided_p, welch_t

FROZEN_WINDOW_DAYS = 10
FROZEN_MIN_PRIOR = 2
SENSITIVITY_MIN_PRIOR = (1, 3)
SENSITIVITY_WINDOWS = (5, 15)
FOLD_BOUNDARY = "2021-01-01"


def _parse(day: str) -> date:
    return date.fromisoformat(day)


def annotate_crowding(
    trades: list[dict], window_days: int, min_prior: int,
) -> list[dict]:
    """New trade dicts with n_prior (trailing co-detections) and crowd_group."""
    as_ofs = [_parse(t["as_of_date"]) for t in trades]
    annotated = []
    for i, trade in enumerate(trades):
        own = as_ofs[i]
        window_start = own - timedelta(days=window_days)
        n_prior = sum(
            1 for j, other in enumerate(as_ofs)
            if j != i and window_start <= other <= own
        )
        group = "crowded" if n_prior >= min_prior else "quiet"
        annotated.append({**trade, "n_prior": n_prior, "crowd_group": group})
    return annotated


def analyze(trades: list[dict]) -> dict:
    """Group means, difference (crowded - quiet), and Welch t."""
    crowded = [t["excess_vs_spy_pct"] for t in trades if t["crowd_group"] == "crowded"]
    quiet = [t["excess_vs_spy_pct"] for t in trades if t["crowd_group"] == "quiet"]
    t, df = welch_t(crowded, quiet)
    return {
        "n_crowded": len(crowded),
        "n_quiet": len(quiet),
        "mean_crowded": round(statistics.fmean(crowded), 3) if crowded else None,
        "mean_quiet": round(statistics.fmean(quiet), 3) if quiet else None,
        "diff": (
            round(statistics.fmean(crowded) - statistics.fmean(quiet), 3)
            if crowded and quiet else None
        ),
        "welch_t": round(t, 3) if t is not None else None,
        "df": round(df, 1) if df is not None else None,
        "p_two_sided": round(two_sided_p(t, df), 4) if t is not None else None,
    }


def run_universe(trades: list[dict]) -> dict:
    """Full frozen analysis plus robustness slices for one universe."""
    frozen = annotate_crowding(trades, FROZEN_WINDOW_DAYS, FROZEN_MIN_PRIOR)
    early, late = fold_split(frozen, FOLD_BOUNDARY)
    result = {
        "n_trades": len(trades),
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
    for mp in SENSITIVITY_MIN_PRIOR:
        alt = annotate_crowding(trades, FROZEN_WINDOW_DAYS, mp)
        result["sensitivity_not_adopted"][f"min_prior_{mp}"] = analyze(alt)
    for w in SENSITIVITY_WINDOWS:
        alt = annotate_crowding(trades, w, FROZEN_MIN_PRIOR)
        result["sensitivity_not_adopted"][f"window_{w}d"] = analyze(alt)
    return result


def _fmt_row(label: str, s: dict) -> str:
    return (
        f"| {label} | {s['n_crowded']} | {s['n_quiet']} | {s['mean_crowded']} | "
        f"{s['mean_quiet']} | {s['diff']} | {s['welch_t']} | {s['p_two_sided']} |"
    )


def _universe_section(name: str, result: dict) -> list[str]:
    lines = [
        f"## {name} ({result['n_trades']} trades)",
        "",
        "| Slice | n crowded | n quiet | mean crowded | mean quiet | diff (pp) | Welch t | p |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        _fmt_row("Pooled (frozen 10d / >=2)", result["pooled"]),
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
        "# VCP Signal-Crowding Experiment",
        "",
        f"Generated: {meta['generated_at']}  ",
        f"S&P trades JSON: `{meta['sp_trades_json']}`  ",
        f"R2K trades JSON: `{meta['r2k_trades_json']}`  ",
        "Frozen spec: `backtests/crowding/frozen_spec.md` (10-calendar-day",
        "trailing window on as_of_date, crowded = >=2 co-detections; declared",
        "direction: crowded worse; declared before results)",
        "",
        "No price bars consulted: the feature uses trade-log as_of_date fields",
        "only, so both universes replicate offline. Metric: per-trade excess vs",
        "SPY from the source logs. Groups share fill/cost models, so the",
        "difference is cost-invariant. Cluster-overlap caveat: crowded trades",
        "hold overlapping dates, so within-cluster outcomes are correlated and",
        "nominal t-values overstate independence. Universes are survivorship-",
        "biased; all numbers are optimistic ceilings. Sensitivity rows are",
        "robustness checks, not a search; no variation is adopted.",
        "",
    ]
    for name, result in results.items():
        lines.extend(_universe_section(name, result))
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sp_trades_json")
    parser.add_argument("--r2k-trades", default=None,
                        help="R2K trades JSON for the cross-universe prong")
    parser.add_argument("--output-dir", default="backtests/crowding")
    args = parser.parse_args()

    from datetime import datetime

    with open(args.sp_trades_json) as f:
        sp_trades = json.load(f)["trades"]
    results = {"S&P 500": run_universe(sp_trades)}
    if args.r2k_trades:
        with open(args.r2k_trades) as f:
            r2k_trades = json.load(f)["trades"]
        results["Russell 2000"] = run_universe(r2k_trades)

    meta = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sp_trades_json": args.sp_trades_json,
        "r2k_trades_json": args.r2k_trades or "not supplied",
    }
    os.makedirs(args.output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = os.path.join(args.output_dir, f"crowding_{stamp}.json")
    md_path = os.path.join(args.output_dir, f"crowding_{stamp}.md")
    with open(json_path, "w") as f:
        json.dump({"metadata": meta, "results": results}, f, indent=1)
    _write_markdown(md_path, results, meta)
    print(f"wrote {json_path}\nwrote {md_path}")
    for name, result in results.items():
        print(name, json.dumps(result["pooled"]))


if __name__ == "__main__":
    main()
