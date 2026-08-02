#!/usr/bin/env python3
"""Train-select a 2-5 session wait after each QQQ risk-on transition.

The wait is an entry embargo, not a price-confirmation rule.  A wait of N
skips the first N complete benchmark sessions of each QQQ risk-on window and
accepts only fresh MA60/Slope10 false-to-true orders whose fill date is later.
Signals emitted during the embargo are not carried forward.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from cross_sectional_leadership_discovery import discovery_backtest_score
from csv_client import CSVClient
from ma60_3r_trailing_experiment import exit_state_counts
from ma60_only_experiment import (
    PERIODS,
    _compact_cost,
    _sector_map,
    build_standalone_signals,
    evaluate_signals,
)
from ma60_period_gate_experiment import WINDOWS
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import slice_prices

MA_PERIOD = 60
SLOPE_SESSIONS = 10
WAIT_GRID = (2, 3, 4, 5)
CONTROL_WAIT = 0
MIN_TRAIN_TRADES = 15
DECLARED_TRIALS = 579  # Trial 575 incumbent plus four new wait cells.
EXIT_PARAMS = {
    "trigger_r": 3.0,
    "trailing_pct": 24.0,
    "holding_windows": WINDOWS,
    "holding_window_exit_timing": "window_end_open",
}
SIMULATION_STARTS = {
    "train": "2016-07-05",
    "validation": "2019-01-03",
    "best_available_oos": "2022-01-04",
    "full": "2016-07-05",
}


def _benchmark_sessions(prices: dict[str, list[dict]]) -> list[str]:
    return sorted({row["date"] for row in prices.get("SPY", [])})


def qqq_risk_on_age_sessions(
    fill_date: str,
    benchmark_sessions: list[str],
    windows: tuple[tuple[str, str | None], ...] = WINDOWS,
) -> tuple[str, int] | None:
    """Return (window start, completed sessions) at the fill-date open.

    Age zero is the QQQ risk-on fill open.  Age one is the next benchmark
    session's open, after one complete risk-on session has been observed.
    Finite window ends are entry-ineligible because QQQ exits at that open.
    """
    for start, end in windows:
        if start <= fill_date and (end is None or fill_date < end):
            start_index = bisect.bisect_left(benchmark_sessions, start)
            fill_index = bisect.bisect_left(benchmark_sessions, fill_date)
            if (start_index >= len(benchmark_sessions)
                    or fill_index >= len(benchmark_sessions)
                    or benchmark_sessions[start_index] != start
                    or benchmark_sessions[fill_index] != fill_date):
                return None
            return start, fill_index - start_index
    return None


def filter_after_qqq_wait(
    signals: list[dict],
    benchmark_sessions: list[str],
    wait_sessions: int,
) -> list[dict]:
    """Copy signals that fill after the causal QQQ entry embargo."""
    if wait_sessions < 0:
        raise ValueError("wait_sessions must be non-negative")
    output: list[dict] = []
    for signal in signals:
        state = qqq_risk_on_age_sessions(
            str(signal["fill_date"]), benchmark_sessions)
        if state is None:
            continue
        start, age = state
        if age < wait_sessions:
            continue
        row = deepcopy(signal)
        row["qqq_risk_on_start"] = start
        row["qqq_risk_on_age_sessions"] = age
        row["qqq_followthrough_wait_sessions"] = wait_sessions
        output.append(row)
    return output


def _cohort_diagnostics(trades: list[dict]) -> dict:
    counts = Counter(row["entry_date"] for row in trades)
    stops = [row for row in trades if row.get("exit_reason") == "stop"]
    large = [row for row in trades if counts[row["entry_date"]] >= 5]
    large_stops = [row for row in large if row.get("exit_reason") == "stop"]
    clustered_stops = [row for row in stops if sum(
        other.get("exit_reason") == "stop"
        and other["entry_date"] == row["entry_date"]
        for other in trades) >= 2]
    return {
        "trades": len(trades),
        "stops": len(stops),
        "stop_rate_pct": 100 * len(stops) / len(trades) if trades else 0.0,
        "large_cohort_trades": len(large),
        "large_cohort_stops": len(large_stops),
        "large_cohort_stop_rate_pct": (
            100 * len(large_stops) / len(large) if large else 0.0),
        "clustered_stops": len(clustered_stops),
        "clustered_stop_share_pct": (
            100 * len(clustered_stops) / len(stops) if stops else 0.0),
        "largest_entry_cohort": max(counts.values(), default=0),
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


def evaluate_wait(
    wait_sessions: int,
    partition: str,
    prices_all: dict[str, list[dict]],
    membership: dict,
    sectors: dict[str, str],
    iterations: int,
    *,
    cost_multiplier: int = 1,
    seed_offset: int = 0,
) -> tuple[dict, dict]:
    start, end, price_end = PERIODS[partition]
    prices = slice_prices(prices_all, start, price_end)
    raw_signals, counts = build_standalone_signals(
        prices, membership, sectors, start, end,
        ma_period=MA_PERIOD, slope_sessions=SLOPE_SESSIONS)
    signals = filter_after_qqq_wait(
        raw_signals, _benchmark_sessions(prices), wait_sessions)
    result = evaluate_signals(
        signals, prices, iterations=iterations, seed_offset=seed_offset,
        cost_multiplier=cost_multiplier, trials=DECLARED_TRIALS,
        exit_rule="armed_trailing_stop", exit_params=EXIT_PARAMS,
        simulation_start_date=SIMULATION_STARTS[partition])
    cell = {
        "partition": partition,
        "period": [start, end],
        "price_end": price_end,
        "wait_sessions": wait_sessions,
        "ungated_signal_counts": counts,
        "risk_on_signals": len(filter_after_qqq_wait(
            raw_signals, _benchmark_sessions(prices), 0)),
        "signals": len(signals),
        "exit_states": exit_state_counts(result["trades"]),
        "cohort_diagnostics": _cohort_diagnostics(result["trades"]),
        "metrics": result["metrics"],
    }
    return cell, result


def select_train_wait(cells: list[dict]) -> dict:
    eligible = [cell for cell in cells
                if cell["metrics"]["summary"]["trades"] >= MIN_TRAIN_TRADES]
    if not eligible:
        raise RuntimeError("no wait cell met the minimum train-trade count")
    return max(eligible, key=lambda cell: (
        cell["metrics"]["exposure_matched_excess_cagr_pct"],
        -cell["wait_sessions"],
    ))


def train_parameter_is_identifiable(cells: list[dict]) -> bool:
    """Whether the train grid produces more than one portfolio outcome."""
    outcomes = {
        (
            cell["signals"],
            cell["metrics"]["summary"]["trades"],
            cell["metrics"]["summary"]["end_value"],
        )
        for cell in cells
    }
    return len(outcomes) > 1


def _row(cell: dict) -> dict:
    metrics = cell["metrics"]
    return {
        "partition": cell["partition"],
        "wait_sessions": cell["wait_sessions"],
        "signals": cell["signals"],
        "trades": metrics["summary"]["trades"],
        "cagr_pct": metrics["summary"]["cagr_pct"],
        "spy_cagr_pct": metrics["spy_cagr_pct"],
        "exposure_matched_excess_cagr_pct": metrics[
            "exposure_matched_excess_cagr_pct"],
        "sharpe": metrics["sharpe"],
        "sortino": metrics["sortino"],
        "calmar": metrics["calmar"],
        "max_drawdown_pct": metrics["summary"]["max_drawdown_pct"],
        "profit_factor": metrics["trade_metrics"]["net_profit_factor"],
        **cell["cohort_diagnostics"],
    }


def _score_lines(score: dict) -> list[str]:
    labels = {
        "A_statistical_validity": "A. Statistical validity",
        "B_risk_adjusted_performance": "B. Risk-adjusted performance",
        "C_robustness_computable": "C. Robustness computable",
        "D_trade_quality_consistency": "D. Trade quality / consistency",
    }
    lines = [f"## Backtest Score: {score['final_score']}/100 — {score['band']}", "",
             "| Component | Score | Available max |", "|---|---:|---:|"]
    for key, item in score["components"].items():
        lines.append(f"| {labels[key]} | {item['score']} | {item['max']} |")
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
    score = report["backtest_score"]
    selected = report["selected_wait_sessions"]
    lines = [
        "# QQQ Risk-On Follow-Through Wait Experiment",
        "",
        "Classification: **DESCRIPTIVE_ONLY — validation/OOS already contaminated**",
        "",
        *_score_lines(score),
        "The experiment skips the first N complete SPY/QQQ-aligned sessions after each QQQ risk-on fill. Only fresh MA60/Slope10 false-to-true orders after the embargo can enter; embargoed orders are never carried forward.",
        "",
        "## Train-only wait grid",
        "",
        "| Wait | Signals | Trades | CAGR | Excess CAGR | Sharpe | MDD | PF | Stop rate | Large-cohort stop rate |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for cell in report["train_grid"]:
        r = _row(cell)
        lines.append(
            f"| {r['wait_sessions']} | {r['signals']} | {r['trades']} | "
            f"{r['cagr_pct']:.2f}% | {r['exposure_matched_excess_cagr_pct']:.2f}% | "
            f"{r['sharpe']:.3f} | {r['max_drawdown_pct']:.2f}% | "
            f"{(r['profit_factor'] or 0):.3f} | {r['stop_rate_pct']:.2f}% | "
            f"{r['large_cohort_stop_rate_pct']:.2f}% |")
    selection_text = (
        f"Train selected **{selected} sessions** by highest exposure-matched "
        f"excess CAGR among cells with at least {MIN_TRAIN_TRADES} trades."
        if report["train_parameter_identifiable"] else
        f"Train could **not identify this parameter**: waits 2/3/4/5 produced "
        f"exactly the same signals and portfolio because no new QQQ risk-on "
        f"transition occurred inside train. **{selected} sessions** is only the "
        "prespecified lower-wait tie-break, not an evidence-backed winner."
    )
    lines += [
        "",
        selection_text + " The tie-break was frozen before validation and best-available OOS evaluation.",
        "",
        "## Frozen selected wait versus zero-wait control",
        "",
        "| Partition | Variant | Trades | CAGR | SPY CAGR | Excess CAGR | Sharpe | MDD | PF | Stop rate | Clustered-stop share |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for partition in ("train", "validation", "best_available_oos", "full"):
        for variant in ("control", "selected"):
            r = _row(report["comparisons"][partition][variant])
            label = "wait 0" if variant == "control" else f"wait {selected}"
            lines.append(
                f"| {partition} | {label} | {r['trades']} | {r['cagr_pct']:.2f}% | "
                f"{r['spy_cagr_pct']:.2f}% | {r['exposure_matched_excess_cagr_pct']:.2f}% | "
                f"{r['sharpe']:.3f} | {r['max_drawdown_pct']:.2f}% | "
                f"{(r['profit_factor'] or 0):.3f} | {r['stop_rate_pct']:.2f}% | "
                f"{r['clustered_stop_share_pct']:.2f}% |")
    costs = report["cost_stress_best_available_oos"]
    lines += [
        "", "## Selected-wait OOS cost stress", "",
        "| Costs | CAGR | MDD | Sharpe | PF |",
        "|---:|---:|---:|---:|---:|",
    ]
    for multiplier in (1, 2, 5, 10):
        c = costs[str(multiplier)]
        lines.append(
            f"| {multiplier}x | {c['cagr_pct']:.2f}% | {c['max_drawdown_pct']:.2f}% | "
            f"{c['sharpe']:.3f} | {(c['profit_factor'] or 0):.3f} |")
    lines += [
        "", "## Verdict", "", report["interpretation"], "",
        "The QQQ dates and MA60/Slope10 specification were already inspected through the available sample. These results are not untouched OOS evidence and cannot validate a live edge.",
        "", "## Reproduction", "", "```bash", report["reproduction_command"], "```", "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--sector-json", default="scripts/data/sp500_constituents.json")
    parser.add_argument("--output-dir", default="backtests/qqq_followthrough_wait_v2/results")
    parser.add_argument("--iterations", type=int, default=1000)
    args = parser.parse_args()

    coverage = json.loads(Path(args.coverage_json).read_text())
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

    control_train, raw_control_train = evaluate_wait(
        0, "train", prices_all, membership, sectors, args.iterations,
        seed_offset=1500)
    train_grid: list[dict] = []
    raw_train: dict[int, dict] = {}
    for offset, wait in enumerate(WAIT_GRID):
        cell, raw_train[wait] = evaluate_wait(
            wait, "train", prices_all, membership, sectors, args.iterations,
            seed_offset=1510 + offset)
        train_grid.append(cell)
    selected_train = select_train_wait(train_grid)
    selected_wait = selected_train["wait_sessions"]
    train_identifiable = train_parameter_is_identifiable(train_grid)

    comparisons: dict[str, dict[str, dict]] = {
        "train": {"control": control_train, "selected": selected_train}}
    selected_raw: dict[str, dict] = {"train": raw_train[selected_wait]}
    control_raw: dict[str, dict] = {"train": raw_control_train}
    for offset, partition in enumerate(("validation", "best_available_oos", "full")):
        control, control_raw[partition] = evaluate_wait(
            0, partition, prices_all, membership, sectors, args.iterations,
            seed_offset=1600 + offset)
        selected_cell, selected_raw[partition] = evaluate_wait(
            selected_wait, partition, prices_all, membership, sectors,
            args.iterations, seed_offset=1700 + offset)
        comparisons[partition] = {
            "control": control, "selected": selected_cell}

    costs = {"1": _compact_cost(selected_raw["best_available_oos"])}
    for multiplier in (2, 5, 10):
        _, stressed = evaluate_wait(
            selected_wait, "best_available_oos", prices_all, membership,
            sectors, args.iterations, cost_multiplier=multiplier,
            seed_offset=1800 + multiplier)
        costs[str(multiplier)] = _compact_cost(stressed)

    full_control = comparisons["full"]["control"]
    full_selected = comparisons["full"]["selected"]
    c0 = full_control["cohort_diagnostics"]
    cs = full_selected["cohort_diagnostics"]
    m0 = full_control["metrics"]
    ms = full_selected["metrics"]
    improves = (
        ms["summary"]["cagr_pct"] > m0["summary"]["cagr_pct"]
        and ms["exposure_matched_excess_cagr_pct"]
        > m0["exposure_matched_excess_cagr_pct"]
        and abs(ms["summary"]["max_drawdown_pct"])
        <= abs(m0["summary"]["max_drawdown_pct"])
        and cs["stop_rate_pct"] < c0["stop_rate_pct"]
    )
    interpretation = (
        "INCONCLUSIVE / DO NOT ADOPT: train contains no QQQ risk-on transition, "
        "so it cannot distinguish waits 2-5. The mechanical two-session tie-break "
        "improves validation but materially worsens best-available OOS and full-sample "
        "performance."
        if not train_identifiable else
        "DESCRIPTIVE IMPROVEMENT: the train-selected wait improves full-sample CAGR, "
        "exposure-matched excess CAGR and stop rate without worsening MDD."
        if improves else
        "DOES NOT IMPROVE: the train-selected wait fails at least one required full-sample "
        "condition (CAGR, exposure-matched excess, stop rate, or MDD)."
    )
    score = discovery_backtest_score(selected_raw["full"]["score_cell"])
    reproduction = (
        ".venv/bin/python scripts/qqq_followthrough_wait_experiment.py "
        f"--price-csv {args.price_csv} --coverage-json {args.coverage_json} "
        f"--membership-csv {args.membership_csv} --sector-json {args.sector_json} "
        f"--output-dir {args.output_dir} --iterations {args.iterations}")
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "classification": "DESCRIPTIVE_ONLY_VALIDATION_AND_OOS_CONTAMINATED",
        "hypothesis": "Skipping the first 2-5 complete QQQ risk-on sessions reduces correlated stop cohorts and improves portfolio performance.",
        "wait_semantics": "skip N complete benchmark sessions; accept only fresh later false-to-true orders; do not carry embargoed signals forward",
        "wait_grid": list(WAIT_GRID),
        "declared_trials": DECLARED_TRIALS,
        "selection_objective": "maximum train exposure-matched excess CAGR with at least 15 trades; lower wait wins ties",
        "train_parameter_identifiable": train_identifiable,
        "selected_wait_sessions": selected_wait,
        "coverage": coverage,
        "train_control": control_train,
        "train_grid": train_grid,
        "comparisons": comparisons,
        "cost_stress_best_available_oos": costs,
        "backtest_score": score,
        "interpretation": interpretation,
        "reproduction_command": reproduction,
    }

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    stem = output / f"qqq_followthrough_wait_{stamp}"
    json_path = stem.with_suffix(".json")
    md_path = stem.with_suffix(".md")
    grid_path = Path(f"{stem}_train_grid.csv")
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    _csv(grid_path, [_row(control_train), *[_row(cell) for cell in train_grid]])
    for partition, result in selected_raw.items():
        _csv(Path(f"{stem}_{partition}_signals.csv"), result["signals"])
        _csv(Path(f"{stem}_{partition}_trades.csv"), result["trades"])
        _csv(Path(f"{stem}_{partition}_equity.csv"), result["equity_curve"])
    print(json.dumps({
        "selected_wait_sessions": selected_wait,
        "interpretation": interpretation,
        "backtest_score": score,
        "comparisons": {
            partition: {variant: _row(cell) for variant, cell in rows.items()}
            for partition, rows in comparisons.items()},
        "cost_stress_best_available_oos": costs,
        "json": str(json_path), "markdown": str(md_path),
    }, indent=2))


if __name__ == "__main__":
    main()
