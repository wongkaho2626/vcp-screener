#!/usr/bin/env python3
"""Trial 543: MA60-only entry with no timeout and an 8% trailing stop."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from cross_sectional_leadership_discovery import discovery_backtest_score
from csv_client import CSVClient
from ma60_only_experiment import (
    PERIODS,
    _compact_cost,
    _format,
    _sector_map,
    build_standalone_signals,
    evaluate_signals,
)
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import slice_prices

TRAILING_PCT = 8.0
TRIALS_BEFORE = 541
TRIALS_AFTER = 542
DEFAULT_BASELINE_JSON = (
    "backtests/ma60_only_v2/results/ma60_only_2026-08-02_161116.json"
)


def compare_partition(baseline: dict, challenger: dict) -> dict:
    base = baseline["metrics"]
    trial = challenger["metrics"]
    return {
        "cagr_lift_pct_points": (
            trial["summary"]["cagr_pct"] - base["summary"]["cagr_pct"]),
        "total_return_lift_pct_points": (
            trial["summary"]["total_return_pct"]
            - base["summary"]["total_return_pct"]),
        "mdd_change_pct_points": (
            trial["summary"]["max_drawdown_pct"]
            - base["summary"]["max_drawdown_pct"]),
        "sharpe_change": trial["sharpe"] - base["sharpe"],
        "exposure_matched_excess_cagr_lift_pct_points": (
            trial["exposure_matched_excess_cagr_pct"]
            - base["exposure_matched_excess_cagr_pct"]),
        "trade_change": (
            trial["summary"]["trades"] - base["summary"]["trades"]),
        "average_hold_change": (
            (trial["trade_metrics"]["average_holding_sessions"] or 0)
            - (base["trade_metrics"]["average_holding_sessions"] or 0)),
    }


def decide(
    baseline_oos: dict, challenger_oos: dict, challenger_5x: dict,
) -> dict:
    base = baseline_oos["metrics"]
    trial = challenger_oos["metrics"]
    checks = {
        "latest_cagr_improves": (
            trial["summary"]["cagr_pct"] > base["summary"]["cagr_pct"]),
        "latest_exposure_matched_excess_cagr_improves": (
            trial["exposure_matched_excess_cagr_pct"]
            > base["exposure_matched_excess_cagr_pct"]),
        "latest_trades>=30": trial["summary"]["trades"] >= 30,
        "latest_drop_best_five_expectancy>0": (
            (trial["trade_metrics"]["drop_best_five_net_expectancy_pct"] or 0) > 0),
        "latest_5x_cagr>0": challenger_5x["cagr_pct"] > 0,
        "latest_mdd_not_worse_by_more_than_2pp": (
            trial["summary"]["max_drawdown_pct"]
            >= base["summary"]["max_drawdown_pct"] - 2),
    }
    if all(checks.values()):
        verdict = "IMPROVES"
    elif (not checks["latest_cagr_improves"]
          and not checks["latest_exposure_matched_excess_cagr_improves"]):
        verdict = "WORSENS"
    else:
        verdict = "INCONCLUSIVE"
    return {"checks": checks, "verdict": verdict}


def _csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def render_markdown(report: dict) -> str:
    score = report["backtest_score"]
    lines = [
        "# Trial 543 — MA60-only with 8% Trailing Stop",
        "",
        f"Verdict: **{report['verdict']}**",
        "",
        f"## Backtest Score: {score['final_score']}/100 — {score['band']}",
        "",
        "| Component | Score | Available max |",
        "|---|---:|---:|",
    ]
    labels = {
        "A_statistical_validity": "A. Statistical validity",
        "B_risk_adjusted_performance": "B. Risk-adjusted performance",
        "C_robustness_computable": "C. Robustness computable",
        "D_trade_quality_consistency": "D. Trade quality / consistency",
    }
    for key, cell in score["components"].items():
        lines.append(f"| {labels[key]} | {cell['score']} | {cell['max']} |")
    lines += [
        f"| Measured total | {score['measured_total']} | {score['measured_denominator']} |",
        f"| Normalized raw score | {score['reduced_denominator_normalized_raw_score']} | 100 |",
        "| Caps | unresolved survivorship → 20 | |",
        f"| **Final score** | **{score['final_score']}** | **100** |",
        "",
        "## Exit definition",
        "",
        "The Trial 542 standalone MA60 rising-edge entry is unchanged. The 60-session timeout is disabled. Initial stop is 8% below raw entry open; after each completed close the stop ratchets to 92% of the highest completed close and becomes active next session.",
        "",
        "## Trailing strategy versus Trial 542 timeout baseline",
        "",
        "| Partition | Trail trades | Trail CAGR | Baseline CAGR | CAGR lift | Trail MDD | MDD change | Trail Sharpe | Excess-CAGR lift | Avg hold | End-data exits |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("train", "validation", "best_available_oos", "full"):
        part = report["partitions"][name]
        metrics = part["metrics"]
        base = report["baseline_partitions"][name]["metrics"]
        comparison = report["comparisons"][name]
        reasons = part["exit_reasons"]
        lines.append(
            f"| {name} | {metrics['summary']['trades']} | "
            f"{_format(metrics['summary']['cagr_pct'])}% | "
            f"{_format(base['summary']['cagr_pct'])}% | "
            f"{_format(comparison['cagr_lift_pct_points'])} pp | "
            f"{_format(metrics['summary']['max_drawdown_pct'])}% | "
            f"{_format(comparison['mdd_change_pct_points'])} pp | "
            f"{_format(metrics['sharpe'], 3)} | "
            f"{_format(comparison['exposure_matched_excess_cagr_lift_pct_points'])} pp | "
            f"{_format(metrics['trade_metrics']['average_holding_sessions'])} | "
            f"{reasons.get('end_of_data', 0)} |"
        )
    lines += [
        "",
        "## Frozen decision checks",
        "",
    ]
    for name, passed in report["decision"]["checks"].items():
        lines.append(f"- {'PASS' if passed else 'FAIL'} — `{name}`")
    lines += [
        "",
        "## Cost stress",
        "",
        "| Partition | 1x CAGR | 2x | 5x | 10x |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in ("train", "validation", "best_available_oos", "full"):
        costs = report["cost_stress"][name]
        lines.append(
            f"| {name} | {_format(costs['1']['cagr_pct'])}% | "
            f"{_format(costs['2']['cagr_pct'])}% | "
            f"{_format(costs['5']['cagr_pct'])}% | "
            f"{_format(costs['10']['cagr_pct'])}% |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        report["interpretation"],
        "",
        "Open positions at each partition price boundary are liquidated at the final available close for accounting. Because there is no time exit, those end-data trades are right-censored and reported explicitly.",
        "",
        "The latest period is best-available rather than untouched OOS; MA60 and this exit were requested after extensive prior research. Current sector labels are not point-in-time, and historical/delisted price coverage remains incomplete.",
        "",
        "## Reproduction",
        "",
        "```bash",
        report["reproduction_command"],
        "```",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--sector-json", default="scripts/data/sp500_constituents.json")
    parser.add_argument("--baseline-json", default=DEFAULT_BASELINE_JSON)
    parser.add_argument("--output-dir", default="backtests/ma60_trailing_v2/results")
    parser.add_argument("--iterations", type=int, default=1000)
    args = parser.parse_args()
    coverage = json.loads(Path(args.coverage_json).read_text())
    baseline_report = json.loads(Path(args.baseline_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/real-SPY gate failed")
    client = CSVClient(args.price_csv)
    if client.synthetic_benchmark:
        raise SystemExit("real SPY is required; synthetic benchmark rejected")
    prices_all = {
        row["symbol"]: list(reversed(client.get_historical_prices(
            row["symbol"], days=100_000)["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]
    }
    membership = load_membership(args.membership_csv)
    sectors = _sector_map(args.sector_json)
    partitions = {}
    raw = {}
    cost_stress = {}
    comparisons = {}
    for offset, (name, (start, end, price_end)) in enumerate(PERIODS.items()):
        prices = slice_prices(prices_all, start, price_end)
        signals, counts = build_standalone_signals(
            prices, membership, sectors, start, end)
        result = evaluate_signals(
            signals, prices, iterations=args.iterations, seed_offset=100 + offset,
            exit_rule="trailing_stop", exit_params={"trailing_pct": TRAILING_PCT},
        )
        raw[name] = result
        exit_reasons = dict(sorted(Counter(
            row["exit_reason"] for row in result["trades"]).items()))
        partitions[name] = {
            "period": [start, end],
            "price_end": price_end,
            "signal_counts": counts,
            "exit_reasons": exit_reasons,
            "metrics": result["metrics"],
        }
        comparisons[name] = compare_partition(
            baseline_report["partitions"][name], result)
        cost_stress[name] = {"1": _compact_cost(result)}
        for multiplier in (2, 5, 10):
            stressed = evaluate_signals(
                signals, prices, cost_multiplier=multiplier,
                iterations=args.iterations, seed_offset=100 + offset + multiplier * 10,
                exit_rule="trailing_stop",
                exit_params={"trailing_pct": TRAILING_PCT},
            )
            cost_stress[name][str(multiplier)] = _compact_cost(stressed)
    decision = decide(
        baseline_report["partitions"]["best_available_oos"],
        raw["best_available_oos"],
        cost_stress["best_available_oos"]["5"],
    )
    verdict = decision["verdict"]
    oos_comparison = comparisons["best_available_oos"]
    interpretation = (
        "The 8% trailing exit passed every frozen latest-period improvement, "
        "outlier, cost and drawdown check."
        if verdict == "IMPROVES" else
        "The 8% trailing exit worsened both latest-period CAGR and exposure-matched "
        "excess CAGR versus the 60-session timeout."
        if verdict == "WORSENS" else
        "The 8% trailing exit produced mixed latest-period evidence and failed at "
        "least one frozen economic or robustness requirement."
    )
    score = discovery_backtest_score(raw["full"]["score_cell"])
    reproduction = (
        ".venv/bin/python scripts/ma60_trailing_experiment.py "
        "--price-csv SP500_PIT_2016_2026.csv "
        "--coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json "
        "--membership-csv scripts/data/sp500_membership.csv "
        "--sector-json scripts/data/sp500_constituents.json "
        f"--baseline-json {args.baseline_json} "
        "--output-dir backtests/ma60_trailing_v2/results --iterations 1000"
    )
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "classification": "standalone_relative_ma60_trailing_stop",
        "family_spec": "backtests/ma60_trailing_v2/frozen_spec.md",
        "parameters": {
            "ma_period": 60,
            "slope_sessions": 20,
            "trailing_pct": TRAILING_PCT,
            "watermark": "completed_close",
            "timeout": None,
        },
        "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": 1,
        "trials_after": TRIALS_AFTER,
        "coverage": coverage,
        "baseline_json": args.baseline_json,
        "baseline_partitions": baseline_report["partitions"],
        "partitions": partitions,
        "comparisons": comparisons,
        "cost_stress": cost_stress,
        "decision": decision,
        "best_available_oos_cagr_lift_pct_points": oos_comparison["cagr_lift_pct_points"],
        "backtest_score": score,
        "verdict": verdict,
        "interpretation": interpretation,
        "reproduction_command": reproduction,
    }
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stem = output / f"ma60_trailing_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}"
    stem.with_suffix(".json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    stem.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    for name, result in raw.items():
        _csv(Path(f"{stem}_{name}_signals.csv"), result["signals"])
        _csv(Path(f"{stem}_{name}_trades.csv"), result["trades"])
        _csv(Path(f"{stem}_{name}_equity.csv"), result["equity_curve"])
    print(json.dumps({
        "verdict": verdict,
        "decision": decision,
        "score": score["final_score"],
        "comparisons": comparisons,
        "full": partitions["full"],
        "best_available_oos": partitions["best_available_oos"],
        "json": str(stem.with_suffix(".json")),
        "markdown": str(stem.with_suffix(".md")),
    }, indent=2))


if __name__ == "__main__":
    main()
