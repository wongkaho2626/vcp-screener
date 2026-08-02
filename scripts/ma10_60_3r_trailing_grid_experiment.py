#!/usr/bin/env python3
"""Trial 545-550: MA10-60 buy grid with Trial 544's frozen exit."""

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
    SLOPE_SESSIONS,
    _compact_cost,
    _sector_map,
    build_standalone_signals,
    evaluate_signals,
)
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import slice_prices

MA_PERIODS = (10, 20, 30, 40, 50, 60)
TRIGGER_R = 3.0
TRAILING_PCT = 24.0
TRIALS_BEFORE = 543
TRIALS_AFTER = 549
MIN_TRAIN_TRADES = 15
MIN_VALIDATION_TRADES = 30
DEFAULT_INCUMBENT_JSON = (
    "backtests/ma60_3r_trailing_v2/results/"
    "ma60_3r_trailing_2026-08-02_165231.json"
)


def cell_checks(cell: dict, minimum_trades: int) -> dict[str, bool]:
    metrics = cell["metrics"]
    summary = metrics["summary"]
    trade = metrics["trade_metrics"]
    return {
        f"trades>={minimum_trades}": summary["trades"] >= minimum_trades,
        "cagr>0": summary["cagr_pct"] > 0,
        "exposure_matched_excess_cagr>0": (
            metrics["exposure_matched_excess_cagr_pct"] > 0),
        "profit_factor>1.2": (trade["net_profit_factor"] or 0) > 1.2,
        "mdd>-30": summary["max_drawdown_pct"] > -30,
        "drop_best_five_expectancy>0": (
            trade["drop_best_five_net_expectancy_pct"] is not None
            and trade["drop_best_five_net_expectancy_pct"] > 0),
    }


def select_train_candidate(cells: list[dict]) -> tuple[list[dict], dict | None]:
    for cell in cells:
        cell["checks"] = cell_checks(cell, MIN_TRAIN_TRADES)
        cell["qualified"] = all(cell["checks"].values())
    qualified = sorted(
        (cell for cell in cells if cell["qualified"]),
        key=lambda row: (
            -row["metrics"]["exposure_matched_excess_cagr_pct"],
            row["ma_period"],
        ),
    )
    return qualified, qualified[0] if qualified else None


def validation_passes(cell: dict) -> bool:
    cell["checks"] = cell_checks(cell, MIN_VALIDATION_TRADES)
    cell["qualified"] = all(cell["checks"].values())
    return cell["qualified"]


def final_decision(incumbent: dict, challenger: dict,
                   challenger_5x: dict) -> dict:
    base = incumbent["metrics"]
    trial = challenger["metrics"]
    checks = {
        "oos_cagr_improves": (
            trial["summary"]["cagr_pct"] > base["summary"]["cagr_pct"]),
        "oos_exposure_matched_excess_cagr_improves": (
            trial["exposure_matched_excess_cagr_pct"]
            > base["exposure_matched_excess_cagr_pct"]),
        "oos_trades>=30": trial["summary"]["trades"] >= 30,
        "oos_drop_best_five_expectancy>0": (
            (trial["trade_metrics"]["drop_best_five_net_expectancy_pct"] or 0) > 0),
        "oos_5x_cagr>0": challenger_5x["cagr_pct"] > 0,
        "oos_mdd_not_worse_by_more_than_2pp": (
            trial["summary"]["max_drawdown_pct"]
            >= base["summary"]["max_drawdown_pct"] - 2),
    }
    if all(checks.values()):
        verdict = "IMPROVES"
    elif not checks["oos_cagr_improves"] and not checks[
            "oos_exposure_matched_excess_cagr_improves"]:
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


def evaluate_cell(
    ma_period: int, partition: str, prices_all: dict[str, list[dict]],
    membership: dict, sectors: dict[str, str], iterations: int,
    *, cost_multiplier: int = 1, seed_offset: int = 0,
) -> tuple[dict, dict]:
    start, end, price_end = PERIODS[partition]
    prices = slice_prices(prices_all, start, price_end)
    signals, counts = build_standalone_signals(
        prices, membership, sectors, start, end, ma_period=ma_period,
        slope_sessions=SLOPE_SESSIONS)
    result = evaluate_signals(
        signals, prices, cost_multiplier=cost_multiplier,
        iterations=iterations, seed_offset=seed_offset,
        exit_rule="armed_trailing_stop",
        exit_params={"trigger_r": TRIGGER_R, "trailing_pct": TRAILING_PCT},
        trials=TRIALS_AFTER,
    )
    cell = {
        "ma_period": ma_period,
        "slope_sessions": SLOPE_SESSIONS,
        "period": [start, end],
        "price_end": price_end,
        "signal_counts": counts,
        "exit_states": exit_state_counts(result["trades"]),
        "metrics": result["metrics"],
    }
    return cell, result


def _score_lines(score: dict) -> list[str]:
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
    lines = ["# Trial 545–550 — MA10–60 Buy Grid with Frozen 3R Exit", "",
             f"Family verdict: **{report['verdict']}**", "",
             *_score_lines(report["backtest_score"]),
             "The exit is unchanged: 8% hard stop until a completed close reaches +3R, then a 24% completed-close trail active next session, with no timeout.", "",
             "## Train grid", "",
             "| MA | Signals | Trades | Armed | CAGR | Excess CAGR | Sharpe | Sortino | Calmar | MDD | PF | Drop-best-5 | Gate |",
             "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for cell in report["train_grid"]:
        metrics = cell["metrics"]
        summary = metrics["summary"]
        trade = metrics["trade_metrics"]
        trim = trade["drop_best_five_net_expectancy_pct"]
        lines.append(
            f"| {cell['ma_period']} | {summary['signals']} | {summary['trades']} | "
            f"{cell['exit_states']['armed_trades']} | {summary['cagr_pct']:.2f}% | "
            f"{metrics['exposure_matched_excess_cagr_pct']:.2f}% | "
            f"{metrics['sharpe']:.3f} | {metrics['sortino']:.3f} | "
            f"{metrics['calmar']:.3f} | {summary['max_drawdown_pct']:.2f}% | "
            f"{(trade['net_profit_factor'] or 0):.3f} | "
            f"{trim:.2f}% | {'PASS' if cell['qualified'] else 'FAIL'} |")
    selected = report["selected_period"]
    lines += ["", "## Sequential decision", "",
              f"Train-qualified periods: **{report['qualified_periods']}**.  ",
              f"Selected period: **{'MA' + str(selected) if selected else 'none'}**.  ",
              f"Validation accessed: **{'YES' if report['validation_accessed'] else 'NO'}**.  ",
              f"Best-available OOS accessed: **{'YES' if report['best_available_oos_accessed'] else 'NO'}**.", ""]
    if report.get("validation"):
        cell = report["validation"]
        metrics = cell["metrics"]
        lines += ["### Validation", "",
                  f"MA{cell['ma_period']}: {metrics['summary']['trades']} trades, "
                  f"{metrics['summary']['cagr_pct']:.2f}% CAGR, "
                  f"{metrics['exposure_matched_excess_cagr_pct']:.2f}% exposure-matched excess CAGR, "
                  f"{metrics['summary']['max_drawdown_pct']:.2f}% MDD, "
                  f"drop-best-five {metrics['trade_metrics']['drop_best_five_net_expectancy_pct']:.2f}%.", ""]
    if report.get("best_available_oos"):
        cell = report["best_available_oos"]
        metrics = cell["metrics"]
        lines += ["### Best-available OOS", "",
                  f"MA{cell['ma_period']}: {metrics['summary']['trades']} trades, "
                  f"{metrics['summary']['cagr_pct']:.2f}% CAGR, "
                  f"{metrics['exposure_matched_excess_cagr_pct']:.2f}% exposure-matched excess CAGR, "
                  f"{metrics['summary']['max_drawdown_pct']:.2f}% MDD.", ""]
    lines += ["## Interpretation", "", report["interpretation"], "",
              "This family is multiple-comparison discovery and the latest period is best-available, not untouched OOS. Incomplete delisted histories retain the survivorship cap.", "",
              "## Reproduction", "", "```bash", report["reproduction_command"], "```", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--sector-json", default="scripts/data/sp500_constituents.json")
    parser.add_argument("--incumbent-json", default=DEFAULT_INCUMBENT_JSON)
    parser.add_argument("--output-dir", default="backtests/ma10_60_3r_trailing_grid_v2/results")
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
    for offset, ma_period in enumerate(MA_PERIODS):
        cell, raw_train[ma_period] = evaluate_cell(
            ma_period, "train", prices_all, membership, sectors,
            args.iterations, seed_offset=300 + offset)
        train_cells.append(cell)
    qualified, selected = select_train_candidate(train_cells)
    diagnostic = max(
        train_cells,
        key=lambda row: (
            row["metrics"]["exposure_matched_excess_cagr_pct"],
            -row["ma_period"],
        ),
    )

    validation = validation_raw = None
    best_oos = best_oos_raw = None
    cost_stress = None
    decision = None
    if selected is not None:
        validation, validation_raw = evaluate_cell(
            selected["ma_period"], "validation", prices_all, membership,
            sectors, args.iterations, seed_offset=400)
        if validation_passes(validation):
            best_oos, best_oos_raw = evaluate_cell(
                selected["ma_period"], "best_available_oos", prices_all,
                membership, sectors, args.iterations, seed_offset=500)
            cost_stress = {"1": _compact_cost(best_oos_raw)}
            for multiplier in (2, 5, 10):
                _, stressed = evaluate_cell(
                    selected["ma_period"], "best_available_oos", prices_all,
                    membership, sectors, args.iterations,
                    cost_multiplier=multiplier,
                    seed_offset=500 + multiplier * 10)
                cost_stress[str(multiplier)] = _compact_cost(stressed)
            decision = final_decision(
                incumbent["partitions"]["best_available_oos"], best_oos,
                cost_stress["5"])

    if selected is None:
        verdict = "NO_QUALIFYING_WINNER"
        interpretation = (
            "No MA period passed every frozen train gate, so validation and "
            "best-available OOS remained sealed.")
    elif best_oos is None:
        verdict = "VALIDATION_FAIL"
        interpretation = (
            f"MA{selected['ma_period']} won the train selection but failed the "
            "frozen validation gate; best-available OOS remained sealed.")
    else:
        verdict = decision["verdict"]
        interpretation = (
            f"MA{selected['ma_period']} passed train and validation; the verdict "
            "uses its frozen comparison with the Trial 544 MA60 incumbent.")

    score = discovery_backtest_score(raw_train[diagnostic["ma_period"]]["score_cell"])
    reproduction = (
        ".venv/bin/python scripts/ma10_60_3r_trailing_grid_experiment.py "
        f"--price-csv {args.price_csv} --coverage-json {args.coverage_json} "
        f"--membership-csv {args.membership_csv} --sector-json {args.sector_json} "
        f"--incumbent-json {args.incumbent_json} --output-dir {args.output_dir} "
        f"--iterations {args.iterations}")
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/ma10_60_3r_trailing_grid_v2/frozen_spec.md",
        "classification": "standalone_relative_ma10_60_grid_frozen_3r_exit",
        "parameters": {
            "ma_periods": MA_PERIODS, "slope_sessions": SLOPE_SESSIONS,
            "initial_stop_pct": 8.0, "trigger_r": TRIGGER_R,
            "trailing_pct": TRAILING_PCT, "timeout": None,
        },
        "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": len(MA_PERIODS),
        "trials_after": TRIALS_AFTER,
        "coverage": coverage,
        "incumbent_json": args.incumbent_json,
        "train_grid": train_cells,
        "qualified_periods": [row["ma_period"] for row in qualified],
        "selected_period": selected["ma_period"] if selected else None,
        "diagnostic_leader": diagnostic["ma_period"],
        "validation_accessed": validation is not None,
        "validation_passed": bool(validation and validation.get("qualified")),
        "best_available_oos_accessed": best_oos is not None,
        "validation": validation,
        "best_available_oos": best_oos,
        "cost_stress": cost_stress,
        "decision": decision,
        "backtest_score": score,
        "verdict": verdict,
        "interpretation": interpretation,
        "reproduction_command": reproduction,
    }

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    stem = output / f"ma10_60_3r_trailing_grid_{stamp}"
    stem.with_suffix(".json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    stem.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    for ma_period, result in raw_train.items():
        prefix = Path(f"{stem}_train_ma{ma_period}")
        _csv(Path(f"{prefix}_signals.csv"), result["signals"])
        _csv(Path(f"{prefix}_trades.csv"), result["trades"])
        _csv(Path(f"{prefix}_equity.csv"), result["equity_curve"])
    for name, result in (("validation", validation_raw),
                         ("best_available_oos", best_oos_raw)):
        if result is None:
            continue
        prefix = Path(f"{stem}_{name}_ma{selected['ma_period']}")
        _csv(Path(f"{prefix}_signals.csv"), result["signals"])
        _csv(Path(f"{prefix}_trades.csv"), result["trades"])
        _csv(Path(f"{prefix}_equity.csv"), result["equity_curve"])
    print(json.dumps({
        "verdict": verdict,
        "qualified_periods": report["qualified_periods"],
        "selected_period": report["selected_period"],
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
