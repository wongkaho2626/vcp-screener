#!/usr/bin/env python3
"""Trial 551-568: user-supplied entry-date gate on the Trial 544 strategy."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from cross_sectional_leadership_discovery import discovery_backtest_score
from csv_client import CSVClient
from ma60_3r_trailing_experiment import exit_state_counts
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

WINDOWS: tuple[tuple[str, str | None], ...] = (
    ("2002-07-24", "2002-08-15"),
    ("2002-10-10", "2002-11-12"),
    ("2003-01-10", "2003-03-18"),
    ("2004-03-25", "2004-06-14"),
    ("2005-03-31", "2007-07-27"),
    ("2008-01-23", "2008-09-30"),
    ("2008-10-17", "2008-11-05"),
    ("2008-11-24", "2009-01-14"),
    ("2009-02-02", "2009-02-18"),
    ("2009-03-09", "2011-09-19"),
    ("2011-10-06", "2014-08-08"),
    ("2015-08-25", "2018-03-23"),
    ("2018-10-15", "2020-02-26"),
    ("2020-03-16", "2021-12-01"),
    ("2022-06-14", "2022-11-14"),
    ("2023-01-27", "2023-05-02"),
    ("2023-10-30", "2024-12-19"),
    ("2025-04-07", None),
)
TRIGGER_R = 3.0
TRAILING_PCT = 24.0
TRIALS_BEFORE = 549
TRIALS_AFTER = 567
DEFAULT_BASELINE_JSON = (
    "backtests/ma60_3r_trailing_v2/results/"
    "ma60_3r_trailing_2026-08-02_165231.json"
)


def in_entry_window(date: str) -> bool:
    return any(start <= date and (end is None or date <= end)
               for start, end in WINDOWS)


def filter_entry_windows(signals: list[dict]) -> list[dict]:
    """Retain copies whose actual fill date is in an inclusive window."""
    return [dict(row) for row in signals if in_entry_window(row["fill_date"])]


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
    labels = {
        "A_statistical_validity": "A. Statistical validity",
        "B_risk_adjusted_performance": "B. Risk-adjusted performance",
        "C_robustness_computable": "C. Robustness computable",
        "D_trade_quality_consistency": "D. Trade quality / consistency",
    }
    lines = [
        "# Trial 551–568 — User-Supplied MA60 Entry Windows",
        "",
        "Classification: **DESCRIPTIVE_ONLY**",
        "",
        f"## Backtest Score: {score['final_score']}/100 — {score['band']}",
        "",
        "| Component | Score | Available max |",
        "|---|---:|---:|",
    ]
    for key, value in score["components"].items():
        lines.append(f"| {labels[key]} | {value['score']} | {value['max']} |")
    caps = "; ".join(
        f"{item['reason']} → {item['cap']}" for item in score["caps_applied"])
    lines += [
        f"| Measured total | {score['measured_total']} | {score['measured_denominator']} |",
        f"| Normalized raw score | {score['reduced_denominator_normalized_raw_score']} | 100 |",
        f"| Caps applied | {caps} | |",
        f"| **Final score** | **{score['final_score']}** | **100** |",
        "",
        "Only fill dates inside the supplied inclusive windows may enter. Existing positions are not closed when a window ends. The MA60 entry and 8% hard-stop / +3R / 24% trailing exit are unchanged.",
        "",
        "## Portfolio comparison",
        "",
        "| Partition | Signals kept | Retained | Trades | Gated CAGR | Baseline CAGR | Lift | Gated MDD | Sharpe | PF | Avg hold |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("train", "validation", "best_available_oos", "full"):
        part = report["partitions"][name]
        metrics = part["metrics"]
        base = report["baseline_partitions"][name]["metrics"]
        comparison = report["comparisons"][name]
        lines.append(
            f"| {name} | {part['retained_signals']} | "
            f"{part['retained_signal_pct']:.2f}% | "
            f"{metrics['summary']['trades']} | "
            f"{_format(metrics['summary']['cagr_pct'])}% | "
            f"{_format(base['summary']['cagr_pct'])}% | "
            f"{_format(comparison['cagr_lift_pct_points'])} pp | "
            f"{_format(metrics['summary']['max_drawdown_pct'])}% | "
            f"{_format(metrics['sharpe'], 3)} | "
            f"{_format(metrics['trade_metrics']['net_profit_factor'], 3)} | "
            f"{_format(metrics['trade_metrics']['average_holding_sessions'])} |")
    lines += ["", "## Diagnostic checks versus Trial 544 OOS", ""]
    for name, passed in report["diagnostic_decision"]["checks"].items():
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
            f"{_format(costs['10']['cagr_pct'])}% |")
    lines += [
        "",
        "## Evidence boundary",
        "",
        f"Only {report['coverage_of_windows']['executable_overlap_count']} of 18 windows overlap executable 2016+ strategy periods. Earlier windows are untested because repository-local raw execution data is absent.",
        "",
        "The dates' causal provenance is unknown and the overlapping sample is already contaminated by earlier research. These numbers cannot establish an improvement or a live signal. Exact endpoints contribute at least 18 additional multiplicity units.",
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
    parser.add_argument("--output-dir", default="backtests/ma60_period_gate_v2/results")
    parser.add_argument("--iterations", type=int, default=1000)
    args = parser.parse_args()

    coverage = json.loads(Path(args.coverage_json).read_text())
    baseline = json.loads(Path(args.baseline_json).read_text())
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

    partitions, raw, costs, comparisons = {}, {}, {}, {}
    for offset, (name, (start, end, price_end)) in enumerate(PERIODS.items()):
        prices = slice_prices(prices_all, start, price_end)
        all_signals, counts = build_standalone_signals(
            prices, membership, sectors, start, end)
        gated = filter_entry_windows(all_signals)
        result = evaluate_signals(
            gated, prices, iterations=args.iterations,
            seed_offset=600 + offset, exit_rule="armed_trailing_stop",
            exit_params={"trigger_r": TRIGGER_R, "trailing_pct": TRAILING_PCT},
            trials=TRIALS_AFTER,
            simulation_start_date=min(row["fill_date"] for row in all_signals))
        raw[name] = result
        partitions[name] = {
            "period": [start, end],
            "price_end": price_end,
            "ungated_signal_counts": counts,
            "ungated_signals": len(all_signals),
            "retained_signals": len(gated),
            "retained_signal_pct": (
                100 * len(gated) / len(all_signals) if all_signals else 0),
            "exit_states": exit_state_counts(result["trades"]),
            "metrics": result["metrics"],
        }
        comparisons[name] = compare_partition(
            baseline["partitions"][name], result)
        costs[name] = {"1": _compact_cost(result)}
        for multiplier in (2, 5, 10):
            stressed = evaluate_signals(
                gated, prices, cost_multiplier=multiplier,
                iterations=args.iterations,
                seed_offset=600 + offset + multiplier * 10,
                exit_rule="armed_trailing_stop",
                exit_params={"trigger_r": TRIGGER_R,
                             "trailing_pct": TRAILING_PCT},
                trials=TRIALS_AFTER,
                simulation_start_date=min(
                    row["fill_date"] for row in all_signals))
            costs[name][str(multiplier)] = _compact_cost(stressed)

    diagnostic = decide(
        baseline["partitions"]["best_available_oos"],
        raw["best_available_oos"], costs["best_available_oos"]["5"])
    score = discovery_backtest_score(raw["full"]["score_cell"])
    executable_windows = [
        [start, end] for start, end in WINDOWS
        if end is None or end >= PERIODS["full"][0]
    ]
    reproduction = (
        ".venv/bin/python scripts/ma60_period_gate_experiment.py "
        f"--price-csv {args.price_csv} --coverage-json {args.coverage_json} "
        f"--membership-csv {args.membership_csv} --sector-json {args.sector_json} "
        f"--baseline-json {args.baseline_json} --output-dir {args.output_dir} "
        f"--iterations {args.iterations}")
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/ma60_period_gate_v2/frozen_spec.md",
        "classification": "DESCRIPTIVE_ONLY",
        "parameters": {
            "windows": WINDOWS,
            "eligibility_date": "fill_date",
            "finite_endpoints_inclusive": True,
            "force_exit_at_window_end": False,
            "ma_period": 60,
            "slope_sessions": 20,
            "initial_stop_pct": 8.0,
            "trigger_r": TRIGGER_R,
            "trailing_pct": TRAILING_PCT,
            "timeout": None,
        },
        "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": len(WINDOWS),
        "trials_after": TRIALS_AFTER,
        "coverage": coverage,
        "coverage_of_windows": {
            "supplied_count": len(WINDOWS),
            "executable_overlap_count": len(executable_windows),
            "executable_windows": executable_windows,
            "untested_count": len(WINDOWS) - len(executable_windows),
            "reason": "repository-local raw execution data is absent before the current 2016+ strategy period",
        },
        "baseline_json": args.baseline_json,
        "baseline_partitions": baseline["partitions"],
        "partitions": partitions,
        "comparisons": comparisons,
        "cost_stress": costs,
        "diagnostic_decision": diagnostic,
        "backtest_score": score,
        "verdict": "DESCRIPTIVE_ONLY",
        "interpretation": (
            "The supplied calendar gate changes historical performance, but "
            "unknown date provenance and incomplete early coverage prevent a "
            "causal or out-of-sample improvement claim."),
        "reproduction_command": reproduction,
    }

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stem = output / f"ma60_period_gate_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}"
    stem.with_suffix(".json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    stem.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    for name, result in raw.items():
        _csv(Path(f"{stem}_{name}_signals.csv"), result["signals"])
        _csv(Path(f"{stem}_{name}_trades.csv"), result["trades"])
        _csv(Path(f"{stem}_{name}_equity.csv"), result["equity_curve"])
    print(json.dumps({
        "verdict": report["verdict"],
        "coverage_of_windows": report["coverage_of_windows"],
        "comparisons": comparisons,
        "diagnostic_decision": diagnostic,
        "score": score,
        "full": partitions["full"],
        "best_available_oos": partitions["best_available_oos"],
        "json": str(stem.with_suffix('.json')),
        "markdown": str(stem.with_suffix('.md')),
    }, indent=2))


if __name__ == "__main__":
    main()
