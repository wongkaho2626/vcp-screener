#!/usr/bin/env python3
"""Trial 569-572: MA60 slope-window grid inside the supplied calendar."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from cross_sectional_leadership_discovery import discovery_backtest_score
from csv_client import CSVClient
from ma10_60_3r_trailing_grid_experiment import cell_checks, final_decision
from ma60_3r_trailing_experiment import exit_state_counts
from ma60_only_experiment import (
    PERIODS,
    _compact_cost,
    _sector_map,
    build_standalone_signals,
    evaluate_signals,
)
from ma60_period_gate_experiment import filter_entry_windows
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import slice_prices

MA_PERIOD = 60
SLOPE_WINDOWS = (10, 20, 30, 40)
TRIGGER_R = 3.0
TRAILING_PCT = 24.0
TRIALS_BEFORE = 567
TRIALS_AFTER = 571
MIN_TRAIN_TRADES = 15
MIN_VALIDATION_TRADES = 30
SIMULATION_STARTS = {
    "train": "2016-07-05",
    "validation": "2019-01-03",
    "best_available_oos": "2022-01-04",
}
DEFAULT_INCUMBENT_JSON = (
    "backtests/ma60_period_gate_v2/results/"
    "ma60_period_gate_2026-08-02_172922.json"
)


def select_train_slope(cells: list[dict]) -> tuple[list[dict], dict | None]:
    for cell in cells:
        cell["checks"] = cell_checks(cell, MIN_TRAIN_TRADES)
        cell["qualified"] = all(cell["checks"].values())
    qualified = sorted(
        (cell for cell in cells if cell["qualified"]),
        key=lambda row: (
            -row["metrics"]["exposure_matched_excess_cagr_pct"],
            row["slope_sessions"],
        ),
    )
    return qualified, qualified[0] if qualified else None


def validation_passes(cell: dict) -> bool:
    cell["checks"] = cell_checks(cell, MIN_VALIDATION_TRADES)
    cell["qualified"] = all(cell["checks"].values())
    return cell["qualified"]


def _csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def evaluate_cell(
    slope_sessions: int, partition: str,
    prices_all: dict[str, list[dict]], membership: dict,
    sectors: dict[str, str], iterations: int, *,
    cost_multiplier: int = 1, seed_offset: int = 0,
) -> tuple[dict, dict]:
    start, end, price_end = PERIODS[partition]
    prices = slice_prices(prices_all, start, price_end)
    all_signals, counts = build_standalone_signals(
        prices, membership, sectors, start, end, ma_period=MA_PERIOD,
        slope_sessions=slope_sessions)
    signals = filter_entry_windows(all_signals)
    result = evaluate_signals(
        signals, prices, cost_multiplier=cost_multiplier,
        iterations=iterations, seed_offset=seed_offset,
        exit_rule="armed_trailing_stop",
        exit_params={"trigger_r": TRIGGER_R, "trailing_pct": TRAILING_PCT},
        trials=TRIALS_AFTER,
        simulation_start_date=SIMULATION_STARTS[partition],
    )
    cell = {
        "ma_period": MA_PERIOD,
        "slope_sessions": slope_sessions,
        "period": [start, end],
        "price_end": price_end,
        "ungated_signal_counts": counts,
        "ungated_signals": len(all_signals),
        "signals": len(signals),
        "retained_signal_pct": (
            100 * len(signals) / len(all_signals) if all_signals else 0),
        "exit_states": exit_state_counts(result["trades"]),
        "metrics": result["metrics"],
    }
    return cell, result


def _score_table(score: dict) -> list[str]:
    labels = {
        "A_statistical_validity": "A. Statistical validity",
        "B_risk_adjusted_performance": "B. Risk-adjusted performance",
        "C_robustness_computable": "C. Robustness computable",
        "D_trade_quality_consistency": "D. Trade quality / consistency",
    }
    lines = [f"## Backtest Score: {score['final_score']}/100 — {score['band']}", "",
             "| Component | Score | Available max |", "|---|---:|---:|"]
    for key, value in score["components"].items():
        lines.append(f"| {labels[key]} | {value['score']} | {value['max']} |")
    caps = "; ".join(
        f"{item['reason']} → {item['cap']}" for item in score["caps_applied"])
    lines += [
        f"| Measured total | {score['measured_total']} | {score['measured_denominator']} |",
        f"| Normalized raw score | {score['reduced_denominator_normalized_raw_score']} | 100 |",
        f"| Caps applied | {caps} | |",
        f"| **Final score** | **{score['final_score']}** | **100** |", "",
    ]
    return lines


def render_markdown(report: dict) -> str:
    lines = [
        "# Trial 569–572 — MA60 Slope-Window Grid",
        "",
        f"Sequential outcome: **{report['sequential_outcome']}**  ",
        "Evidence classification: **DESCRIPTIVE_ONLY**",
        "",
        *_score_table(report["backtest_score"]),
        "MA60, the user-supplied fill-date calendar and the 8% / +3R / 24% no-timeout exit remain unchanged. Only the 10/20/30/40-session slope window changes.",
        "",
        "## Train grid",
        "",
        "| Slope | Signals | Trades | Armed | CAGR | Excess CAGR | Sharpe | Sortino | Calmar | MDD | PF | Drop-best-5 | Gate |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for cell in report["train_grid"]:
        metrics = cell["metrics"]
        summary = metrics["summary"]
        trade = metrics["trade_metrics"]
        lines.append(
            f"| {cell['slope_sessions']} | {cell['signals']} | "
            f"{summary['trades']} | {cell['exit_states']['armed_trades']} | "
            f"{summary['cagr_pct']:.2f}% | "
            f"{metrics['exposure_matched_excess_cagr_pct']:.2f}% | "
            f"{metrics['sharpe']:.3f} | {metrics['sortino']:.3f} | "
            f"{metrics['calmar']:.3f} | {summary['max_drawdown_pct']:.2f}% | "
            f"{(trade['net_profit_factor'] or 0):.3f} | "
            f"{trade['drop_best_five_net_expectancy_pct']:.2f}% | "
            f"{'PASS' if cell['qualified'] else 'FAIL'} |")
    lines += [
        "",
        "## Sequential access",
        "",
        f"Train-qualified slopes: **{report['qualified_slopes']}**.  ",
        f"Selected slope: **{str(report['selected_slope']) + ' sessions' if report['selected_slope'] else 'none'}**.  ",
        f"Validation accessed: **{'YES' if report['validation_accessed'] else 'NO'}**.  ",
        f"Best-available OOS accessed: **{'YES' if report['best_available_oos_accessed'] else 'NO'}**.",
        "",
    ]
    if report.get("validation"):
        cell = report["validation"]
        metrics = cell["metrics"]
        lines += [
            "### Validation",
            "",
            f"Slope {cell['slope_sessions']}: {metrics['summary']['trades']} trades, "
            f"{metrics['summary']['cagr_pct']:.2f}% CAGR, "
            f"{metrics['exposure_matched_excess_cagr_pct']:.2f}% exposure-matched excess CAGR, "
            f"{metrics['summary']['max_drawdown_pct']:.2f}% MDD, "
            f"drop-best-five {metrics['trade_metrics']['drop_best_five_net_expectancy_pct']:.2f}%.",
            "",
        ]
    if report.get("best_available_oos"):
        cell = report["best_available_oos"]
        metrics = cell["metrics"]
        lines += [
            "### Best-available OOS",
            "",
            f"Slope {cell['slope_sessions']}: {metrics['summary']['trades']} trades, "
            f"{metrics['summary']['cagr_pct']:.2f}% CAGR, "
            f"{metrics['exposure_matched_excess_cagr_pct']:.2f}% exposure-matched excess CAGR, "
            f"{metrics['summary']['max_drawdown_pct']:.2f}% MDD.",
            "",
        ]
    lines += [
        "## Interpretation", "", report["interpretation"], "",
        "The exact calendar dates remain potentially post-hoc. A passing slope cannot convert this family into valid untouched OOS evidence.",
        "", "## Reproduction", "", "```bash",
        report["reproduction_command"], "```", "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--sector-json", default="scripts/data/sp500_constituents.json")
    parser.add_argument("--incumbent-json", default=DEFAULT_INCUMBENT_JSON)
    parser.add_argument("--output-dir", default="backtests/ma60_slope_grid_period_gate_v2/results")
    parser.add_argument("--iterations", type=int, default=1000)
    args = parser.parse_args()

    coverage = json.loads(Path(args.coverage_json).read_text())
    incumbent = json.loads(Path(args.incumbent_json).read_text())
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

    train_cells, raw_train = [], {}
    for offset, slope in enumerate(SLOPE_WINDOWS):
        cell, raw_train[slope] = evaluate_cell(
            slope, "train", prices_all, membership, sectors,
            args.iterations, seed_offset=700 + offset)
        train_cells.append(cell)
    qualified, selected = select_train_slope(train_cells)
    diagnostic = max(
        train_cells,
        key=lambda row: (
            row["metrics"]["exposure_matched_excess_cagr_pct"],
            -row["slope_sessions"],
        ),
    )

    validation = validation_raw = None
    best_oos = best_oos_raw = None
    costs = decision = None
    if selected is not None:
        validation, validation_raw = evaluate_cell(
            selected["slope_sessions"], "validation", prices_all,
            membership, sectors, args.iterations, seed_offset=800)
        if validation_passes(validation):
            best_oos, best_oos_raw = evaluate_cell(
                selected["slope_sessions"], "best_available_oos", prices_all,
                membership, sectors, args.iterations, seed_offset=900)
            costs = {"1": _compact_cost(best_oos_raw)}
            for multiplier in (2, 5, 10):
                _, stressed = evaluate_cell(
                    selected["slope_sessions"], "best_available_oos",
                    prices_all, membership, sectors, args.iterations,
                    cost_multiplier=multiplier,
                    seed_offset=900 + multiplier * 10)
                costs[str(multiplier)] = _compact_cost(stressed)
            decision = final_decision(
                incumbent["partitions"]["best_available_oos"],
                best_oos, costs["5"])

    if selected is None:
        sequential_outcome = "NO_QUALIFYING_WINNER"
        interpretation = (
            "No slope window passed every frozen train gate, so validation "
            "and OOS remained sealed.")
    elif best_oos is None:
        sequential_outcome = "VALIDATION_FAIL"
        interpretation = (
            f"The {selected['slope_sessions']}-session slope won train but "
            "failed the frozen validation gate, so OOS remained sealed.")
    else:
        sequential_outcome = decision["verdict"]
        interpretation = (
            f"The {selected['slope_sessions']}-session slope passed train and "
            "validation; its diagnostic OOS comparison is reported without "
            "overriding the calendar family's descriptive-only status.")

    score = discovery_backtest_score(
        raw_train[diagnostic["slope_sessions"]]["score_cell"])
    if diagnostic["metrics"]["summary"]["trades"] < 30:
        score["caps_applied"].append({
            "reason": "fewer than 30 completed train trades",
            "cap": 40,
        })
    reproduction = (
        ".venv/bin/python scripts/ma60_slope_grid_period_gate_experiment.py "
        f"--price-csv {args.price_csv} --coverage-json {args.coverage_json} "
        f"--membership-csv {args.membership_csv} --sector-json {args.sector_json} "
        f"--incumbent-json {args.incumbent_json} --output-dir {args.output_dir} "
        f"--iterations {args.iterations}")
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/ma60_slope_grid_period_gate_v2/frozen_spec.md",
        "classification": "DESCRIPTIVE_ONLY",
        "parameters": {
            "ma_period": MA_PERIOD,
            "slope_windows": SLOPE_WINDOWS,
            "calendar_spec": "backtests/ma60_period_gate_v2/frozen_spec.md",
            "initial_stop_pct": 8.0,
            "trigger_r": TRIGGER_R,
            "trailing_pct": TRAILING_PCT,
            "timeout": None,
        },
        "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": len(SLOPE_WINDOWS),
        "trials_after": TRIALS_AFTER,
        "coverage": coverage,
        "incumbent_json": args.incumbent_json,
        "train_grid": train_cells,
        "qualified_slopes": [row["slope_sessions"] for row in qualified],
        "selected_slope": selected["slope_sessions"] if selected else None,
        "diagnostic_leader": diagnostic["slope_sessions"],
        "validation_accessed": validation is not None,
        "validation_passed": bool(validation and validation.get("qualified")),
        "best_available_oos_accessed": best_oos is not None,
        "validation": validation,
        "best_available_oos": best_oos,
        "cost_stress": costs,
        "decision": decision,
        "sequential_outcome": sequential_outcome,
        "backtest_score": score,
        "verdict": "DESCRIPTIVE_ONLY",
        "interpretation": interpretation,
        "reproduction_command": reproduction,
    }

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    stem = output / f"ma60_slope_grid_period_gate_{stamp}"
    stem.with_suffix(".json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    stem.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    for slope, result in raw_train.items():
        prefix = Path(f"{stem}_train_slope{slope}")
        _csv(Path(f"{prefix}_signals.csv"), result["signals"])
        _csv(Path(f"{prefix}_trades.csv"), result["trades"])
        _csv(Path(f"{prefix}_equity.csv"), result["equity_curve"])
    for name, result in (("validation", validation_raw),
                         ("best_available_oos", best_oos_raw)):
        if result is None:
            continue
        prefix = Path(f"{stem}_{name}_slope{selected['slope_sessions']}")
        _csv(Path(f"{prefix}_signals.csv"), result["signals"])
        _csv(Path(f"{prefix}_trades.csv"), result["trades"])
        _csv(Path(f"{prefix}_equity.csv"), result["equity_curve"])
    print(json.dumps({
        "verdict": report["verdict"],
        "sequential_outcome": sequential_outcome,
        "qualified_slopes": report["qualified_slopes"],
        "selected_slope": report["selected_slope"],
        "diagnostic_leader": report["diagnostic_leader"],
        "validation_accessed": report["validation_accessed"],
        "validation_passed": report["validation_passed"],
        "best_available_oos_accessed": report["best_available_oos_accessed"],
        "score": score,
        "json": str(stem.with_suffix('.json')),
        "markdown": str(stem.with_suffix('.md')),
    }, indent=2))


if __name__ == "__main__":
    main()
