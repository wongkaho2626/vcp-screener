#!/usr/bin/env python3
"""Trial 544: MA60-only with 8% hard stop, then 3R-armed 24% trail."""

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
from ma60_trailing_experiment import compare_partition, decide
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import slice_prices

TRIGGER_R = 3.0
TRAILING_PCT = 24.0
TRIALS_BEFORE = 542
TRIALS_AFTER = 543
DEFAULT_TIMEOUT_JSON = (
    "backtests/ma60_only_v2/results/ma60_only_2026-08-02_161116.json"
)
DEFAULT_IMMEDIATE_TRAIL_JSON = (
    "backtests/ma60_trailing_v2/results/ma60_trailing_2026-08-02_163423.json"
)


def exit_state_counts(trades: list[dict]) -> dict[str, int]:
    reasons = Counter(row["exit_reason"] for row in trades)
    return {
        **dict(sorted(reasons.items())),
        "armed_trades": sum(bool(row.get("trailing_armed_date")) for row in trades),
        "unarmed_trades": sum(not row.get("trailing_armed_date") for row in trades),
    }


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
        "# Trial 544 — MA60 8% Hard Stop, then 3R-Armed 24% Trail",
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
        "The standalone MA60 rising-edge entry is unchanged. Hold the initial raw-open 8% hard stop until a completed close reaches entry plus 3R; then ratchet at 24% below the greatest completed close. The arm/ratchet is active next session. There is no timeout.",
        "",
        "## Comparison",
        "",
        "| Partition | 3R/24 trades | Armed | 3R/24 CAGR | Timeout CAGR | Immediate 8% trail CAGR | Lift vs timeout | MDD | Sharpe | PF | Avg hold |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("train", "validation", "best_available_oos", "full"):
        part = report["partitions"][name]
        metrics = part["metrics"]
        timeout = report["timeout_partitions"][name]["metrics"]
        immediate = report["immediate_trail_partitions"][name]["metrics"]
        comparison = report["comparisons_vs_timeout"][name]
        lines.append(
            f"| {name} | {metrics['summary']['trades']} | "
            f"{part['exit_states']['armed_trades']} | "
            f"{_format(metrics['summary']['cagr_pct'])}% | "
            f"{_format(timeout['summary']['cagr_pct'])}% | "
            f"{_format(immediate['summary']['cagr_pct'])}% | "
            f"{_format(comparison['cagr_lift_pct_points'])} pp | "
            f"{_format(metrics['summary']['max_drawdown_pct'])}% | "
            f"{_format(metrics['sharpe'], 3)} | "
            f"{_format(metrics['trade_metrics']['net_profit_factor'], 3)} | "
            f"{_format(metrics['trade_metrics']['average_holding_sessions'])} |"
        )
    lines += ["", "## Frozen decision checks", ""]
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
        "Positions still open at a partition's price boundary are liquidated at the final available close for accounting and counted as right-censored end-data exits.",
        "",
        "The latest period is best-available, not untouched OOS. MA60, the trigger and trail were requested after extensive prior research; sector history and delisted-price coverage remain incomplete.",
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
    parser.add_argument("--timeout-json", default=DEFAULT_TIMEOUT_JSON)
    parser.add_argument("--immediate-trail-json", default=DEFAULT_IMMEDIATE_TRAIL_JSON)
    parser.add_argument("--output-dir", default="backtests/ma60_3r_trailing_v2/results")
    parser.add_argument("--iterations", type=int, default=1000)
    args = parser.parse_args()
    coverage = json.loads(Path(args.coverage_json).read_text())
    timeout_report = json.loads(Path(args.timeout_json).read_text())
    immediate_report = json.loads(Path(args.immediate_trail_json).read_text())
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
    costs = {}
    comparisons = {}
    for offset, (name, (start, end, price_end)) in enumerate(PERIODS.items()):
        prices = slice_prices(prices_all, start, price_end)
        signals, counts = build_standalone_signals(
            prices, membership, sectors, start, end)
        result = evaluate_signals(
            signals, prices, iterations=args.iterations, seed_offset=200 + offset,
            exit_rule="armed_trailing_stop",
            exit_params={"trigger_r": TRIGGER_R, "trailing_pct": TRAILING_PCT},
        )
        raw[name] = result
        partitions[name] = {
            "period": [start, end],
            "price_end": price_end,
            "signal_counts": counts,
            "exit_states": exit_state_counts(result["trades"]),
            "metrics": result["metrics"],
        }
        comparisons[name] = compare_partition(
            timeout_report["partitions"][name], result)
        costs[name] = {"1": _compact_cost(result)}
        for multiplier in (2, 5, 10):
            stressed = evaluate_signals(
                signals, prices, cost_multiplier=multiplier,
                iterations=args.iterations, seed_offset=200 + offset + multiplier * 10,
                exit_rule="armed_trailing_stop",
                exit_params={"trigger_r": TRIGGER_R, "trailing_pct": TRAILING_PCT},
            )
            costs[name][str(multiplier)] = _compact_cost(stressed)
    decision = decide(
        timeout_report["partitions"]["best_available_oos"],
        raw["best_available_oos"], costs["best_available_oos"]["5"],
    )
    verdict = decision["verdict"]
    interpretation = (
        "The 3R-armed 24% trailing exit passed every frozen latest-period gate "
        "against the timeout baseline."
        if verdict == "IMPROVES" else
        "The 3R-armed 24% trailing exit worsened both latest CAGR and exposure-"
        "matched excess CAGR versus the timeout baseline."
        if verdict == "WORSENS" else
        "The 3R-armed 24% trailing exit produced mixed evidence and failed at "
        "least one frozen economic or robustness gate."
    )
    score = discovery_backtest_score(raw["full"]["score_cell"])
    reproduction = (
        ".venv/bin/python scripts/ma60_3r_trailing_experiment.py "
        "--price-csv SP500_PIT_2016_2026.csv "
        "--coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json "
        "--membership-csv scripts/data/sp500_membership.csv "
        "--sector-json scripts/data/sp500_constituents.json "
        f"--timeout-json {args.timeout_json} "
        f"--immediate-trail-json {args.immediate_trail_json} "
        "--output-dir backtests/ma60_3r_trailing_v2/results --iterations 1000"
    )
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "classification": "ma60_8pct_hard_stop_then_3r_armed_24pct_trail",
        "family_spec": "backtests/ma60_3r_trailing_v2/frozen_spec.md",
        "parameters": {
            "initial_stop_pct": 8.0,
            "trigger_r": TRIGGER_R,
            "trailing_pct": TRAILING_PCT,
            "watermark": "completed_close",
            "timeout": None,
        },
        "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": 1,
        "trials_after": TRIALS_AFTER,
        "coverage": coverage,
        "timeout_json": args.timeout_json,
        "immediate_trail_json": args.immediate_trail_json,
        "timeout_partitions": timeout_report["partitions"],
        "immediate_trail_partitions": immediate_report["partitions"],
        "partitions": partitions,
        "comparisons_vs_timeout": comparisons,
        "cost_stress": costs,
        "decision": decision,
        "backtest_score": score,
        "verdict": verdict,
        "interpretation": interpretation,
        "reproduction_command": reproduction,
    }
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stem = output / f"ma60_3r_trailing_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}"
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
        "comparisons_vs_timeout": comparisons,
        "full": partitions["full"],
        "best_available_oos": partitions["best_available_oos"],
        "json": str(stem.with_suffix(".json")),
        "markdown": str(stem.with_suffix(".md")),
    }, indent=2))


if __name__ == "__main__":
    main()
