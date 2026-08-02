#!/usr/bin/env python3
"""Regenerate a descriptive performance report for the current MA60 candidate."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from cross_sectional_leadership_discovery import discovery_backtest_score
from csv_client import CSVClient
from current_ma60_candidate import (
    EXIT_PARAMS,
    EXIT_RULE,
    MA_PERIOD,
    SLOPE_SESSIONS,
    build_current_buy_signals,
    build_qqq_synchronized_buy_signals,
    current_candidate_spec,
)
from ma60_3r_trailing_experiment import exit_state_counts
from ma60_only_experiment import (
    PERIODS,
    _compact_cost,
    _sector_map,
    build_standalone_signals,
    evaluate_signals,
)
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import slice_prices

DECLARED_TRIALS = 573
SIMULATION_STARTS = {
    "train": "2016-07-05",
    "validation": "2019-01-03",
    "best_available_oos": "2022-01-04",
    "full": "2016-07-05",
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


def _fmt(value: object, digits: int = 2) -> str:
    return "n/a" if value is None else f"{float(value):.{digits}f}"


def _score_lines(score: dict) -> list[str]:
    labels = {
        "A_statistical_validity": "A. Statistical validity",
        "B_risk_adjusted_performance": "B. Risk-adjusted performance",
        "C_robustness_computable": "C. Robustness computable",
        "D_trade_quality_consistency": "D. Trade quality / consistency",
    }
    lines = [
        f"## Backtest Score: {score['final_score']}/100 — {score['band']}",
        "",
        "| Component | Score | Available max |",
        "|---|---:|---:|",
    ]
    for key, item in score["components"].items():
        lines.append(f"| {labels[key]} | {item['score']} | {item['max']} |")
    caps = "; ".join(
        f"{item['reason']} → {item['cap']}" for item in score["caps_applied"])
    lines += [
        f"| Measured total | {score['measured_total']} | {score['measured_denominator']} |",
        f"| Normalized raw score | {score['reduced_denominator_normalized_raw_score']} | 100 |",
        f"| Caps applied | {caps} | |",
        f"| **Final score** | **{score['final_score']}** | **100** |",
        "",
    ]
    return lines


def render_markdown(report: dict) -> str:
    period_exit_enabled = report["candidate_spec"]["force_exit_outside_calendar"]
    qqq_synchronized = (
        report["candidate_spec"].get("period_exit_timing")
        == "qqq_window_end_open")
    calendar_overlay_enabled = report["candidate_spec"].get(
        "calendar_overlay_enabled", True)
    title = (
        "Current MA60 / Slope10 / QQQ-Synchronized Regime Overlay"
        if qqq_synchronized
        else "MA60 / Slope10 / No-QQQ-Regime Control"
        if not calendar_overlay_enabled
        else "Current MA60 / Slope10 / Forced-Period-Exit Performance"
        if period_exit_enabled
        else "Current MA60 / Slope10 / No-Period-Exit Ablation"
    )
    exit_description = (
        "and a QQQ-synchronized liquidation at each finite window-end open."
        if qqq_synchronized
        else "with no QQQ calendar entry gate or boundary exit."
        if not calendar_overlay_enabled
        else "and an opening liquidation on the first ticker session outside all "
        "holding windows."
        if period_exit_enabled
        else "with no forced liquidation when a calendar window ends. The "
        "calendar restricts entries only."
    )
    lookahead_evidence = (
        "QQQ close-confirmed state change executes at the next open; stock "
        "entries and exits use that same executable session boundary."
        if qqq_synchronized
        else "Close-confirmed stock-versus-SPY signal and next-ticker-open entry; "
        "no QQQ regime data are used."
        if not calendar_overlay_enabled
        else "Close-confirmed signal; next-ticker-open entry; period exit executes "
        "at the first known outside-window open."
        if period_exit_enabled
        else "Close-confirmed signal and next-ticker-open entry; no calendar "
        "boundary exit is used."
    )
    snooping_evidence = (
        "The QQQ rule is independently defined, but its parameters were tuned "
        "through 2026-07-02; applying it here is not untouched OOS."
        if qqq_synchronized
        else "Slope10 was selected after its train grid and this no-regime "
        "control was evaluated after prior validation inspection."
        if not calendar_overlay_enabled
        else "Slope10, exact calendar endpoints and forced period exit were "
        "specified after prior validation inspection."
        if period_exit_enabled
        else "Slope10, exact calendar endpoints and this no-period-exit "
        "ablation were evaluated after prior validation inspection."
    )
    lines = [
        f"# {title}",
        "",
        "Classification: **DESCRIPTIVE_ONLY — validation/OOS contaminated**",
        "",
        *_score_lines(report["backtest_score"]),
        "The current user-directed candidate is evaluated exactly as recorded: "
        "MA60, 10-session stock-versus-SPY MA slope, false-to-true next-open "
        "entry inside the supplied calendar, 8% initial stop, +3R arm, 24% "
        f"trailing stop, no timeout, {exit_description}",
        "",
        "## Portfolio performance",
        "",
        "| Partition | Signals | Trades | Period exits | CAGR | SPY CAGR | Excess CAGR | Sharpe | Sortino | Calmar | MDD | PF | Exposure |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("train", "validation", "best_available_oos", "full"):
        part = report["partitions"][name]
        metrics = part["metrics"]
        summary = metrics["summary"]
        trades = metrics["trade_metrics"]
        lines.append(
            f"| {name} | {part['signals']} | {summary['trades']} | "
            f"{part['exit_states'].get('period_exit', 0)} | "
            f"{_fmt(summary['cagr_pct'])}% | {_fmt(metrics['spy_cagr_pct'])}% | "
            f"{_fmt(metrics['exposure_matched_excess_cagr_pct'])}% | "
            f"{_fmt(metrics['sharpe'], 3)} | {_fmt(metrics['sortino'], 3)} | "
            f"{_fmt(metrics['calmar'], 3)} | {_fmt(summary['max_drawdown_pct'])}% | "
            f"{_fmt(trades['net_profit_factor'], 3)} | "
            f"{_fmt(metrics['average_exposure_pct'])}% |")

    lines += [
        "",
        "## Trade quality",
        "",
        "| Partition | Mean net | Median net | Win rate | Worst | Mean SPY | Mean excess | Excess t | Excess CI | Drop-best-5 | Avg hold |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|",
    ]
    for name in ("train", "validation", "best_available_oos", "full"):
        trade = report["partitions"][name]["metrics"]["trade_metrics"]
        ci = trade.get("excess_bootstrap_95ci_pct")
        ci_text = "n/a" if not ci else f"[{ci[0]:.2f}, {ci[1]:.2f}]"
        lines.append(
            f"| {name} | {_fmt(trade['mean_net_return_pct'])}% | "
            f"{_fmt(trade['median_net_return_pct'])}% | "
            f"{_fmt(100 * trade['net_win_rate'])}% | "
            f"{_fmt(trade['worst_net_trade_pct'])}% | "
            f"{_fmt(trade['mean_matched_spy_return_pct'])}% | "
            f"{_fmt(trade['mean_net_excess_pct'])}% | "
            f"{_fmt(trade['excess_t_statistic'])} | {ci_text} | "
            f"{_fmt(trade['drop_best_five_net_expectancy_pct'])}% | "
            f"{_fmt(trade['average_holding_sessions'])} |")

    lines += ["", "## Cost stress", "",
              "| Partition | 1x CAGR | 2x | 5x | 10x |",
              "|---|---:|---:|---:|---:|"]
    for name in ("train", "validation", "best_available_oos", "full"):
        costs = report["cost_stress"][name]
        lines.append(
            f"| {name} | {_fmt(costs['1']['cagr_pct'])}% | "
            f"{_fmt(costs['2']['cagr_pct'])}% | "
            f"{_fmt(costs['5']['cagr_pct'])}% | "
            f"{_fmt(costs['10']['cagr_pct'])}% |")

    lines += ["", "## Full-period calendar years", "",
              "| Year | Portfolio | SPY | Exposure-matched excess | Exposure |",
              "|---|---:|---:|---:|---:|"]
    years = report["partitions"]["full"]["metrics"]["calendar_years"]
    for year, row in years.items():
        lines.append(
            f"| {year} | {_fmt(row['portfolio_return_pct'])}% | "
            f"{_fmt(row['spy_return_pct'])}% | "
            f"{_fmt(row['exposure_matched_excess_return_pct'])}% | "
            f"{_fmt(row['average_exposure_pct'])}% |")

    robust = report["full_robustness"]
    significance = robust["significance"]
    lines += [
        "",
        "## Statistical and robustness diagnostics",
        "",
        f"- Daily-return t-statistic: {_fmt(significance['t_statistic'], 3)}.",
        f"- Effective sample size: {_fmt(significance['effective_sample_size'], 1)}.",
        f"- PSR versus zero: {_fmt(100 * significance['psr_vs_zero'])}%.",
        f"- Approximate DSR probability across {report['declared_trials']} declared trials: "
        f"{_fmt(100 * significance['approximate_dsr']['probability'])}%.",
        f"- Block-bootstrap CAGR 90% interval: "
        f"{_fmt(100 * robust['block_bootstrap']['cagr']['p05'])}% to "
        f"{_fmt(100 * robust['block_bootstrap']['cagr']['p95'])}%.",
        f"- Monte Carlo MDD 90% interval: "
        f"{_fmt(100 * robust['monte_carlo']['max_drawdown']['p05'])}% to "
        f"{_fmt(100 * robust['monte_carlo']['max_drawdown']['p95'])}%.",
        f"- Positive months: {_fmt(100 * robust['stability']['positive_months'])}%.",
        "",
        "## Bias assessment",
        "",
        "| Risk | Assessment | Evidence |",
        "|---|---|---|",
        f"| Lookahead | Absent in implementation | {lookahead_evidence} |",
        "| Survivorship | Unresolved | PIT membership is enforced, but coverage is incomplete and some former/delisted members have no bars. |",
        f"| Data snooping | Present | {snooping_evidence} |",
        "| Transaction costs | Included | 5 bps commission plus 5 bps slippage each way at 1x; 2x/5x/10x stress reported. |",
        "| Liquidity | Partially controlled | Existing ADV capacity constraints are retained; missing histories remain a limitation. |",
        "| Untouched OOS | Absent | Every available chronological partition is contaminated for this newly combined specification. |",
        "",
        "## Interpretation",
        "",
        report["interpretation"],
        "",
        "## Reproduction",
        "",
        "```bash",
        report["reproduction_command"],
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--sector-json", default="scripts/data/sp500_constituents.json")
    parser.add_argument("--output-dir", default="backtests/current_ma60_candidate_v2/results")
    parser.add_argument("--iterations", type=int, default=1000)
    exit_group = parser.add_mutually_exclusive_group()
    exit_group.add_argument(
        "--disable-period-exit", action="store_true",
        help="Ablation: calendar gates entries only; do not force boundary exits",
    )
    exit_group.add_argument(
        "--qqq-synchronized-exit", action="store_true",
        help="Use QQQ's fill state: end date is exit-open and entry-ineligible",
    )
    exit_group.add_argument(
        "--disable-calendar-overlay", action="store_true",
        help="Control: use every MA60/slope10 signal with no QQQ calendar gate",
    )
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
    period_exit_enabled = not (
        args.disable_period_exit or args.disable_calendar_overlay)
    exit_params = dict(EXIT_PARAMS)
    declared_trials = DECLARED_TRIALS
    spec = current_candidate_spec()
    if not period_exit_enabled:
        exit_params.pop("holding_windows", None)
        spec["exit_params"].pop("holding_windows", None)
        spec["force_exit_outside_calendar"] = False
        spec["period_exit_timing"] = None
        declared_trials += 1
        if args.disable_calendar_overlay:
            spec["calendar_overlay_enabled"] = False
            spec["calendar_windows"] = []
            declared_trials += 2
    elif args.qqq_synchronized_exit:
        exit_params["holding_window_exit_timing"] = "window_end_open"
        spec["exit_params"]["holding_window_exit_timing"] = "window_end_open"
        spec["period_exit_timing"] = "qqq_window_end_open"
        spec["calendar_finite_end_entry_eligible"] = False
        declared_trials += 2

    raw: dict[str, dict] = {}
    partitions: dict[str, dict] = {}
    cost_stress: dict[str, dict] = {}
    for offset, (name, (start, end, price_end)) in enumerate(PERIODS.items()):
        prices = slice_prices(prices_all, start, price_end)
        if args.disable_calendar_overlay:
            signals, counts = build_standalone_signals(
                prices, membership, sectors, start, end,
                ma_period=MA_PERIOD, slope_sessions=SLOPE_SESSIONS)
        else:
            signal_builder = (build_qqq_synchronized_buy_signals
                              if args.qqq_synchronized_exit
                              else build_current_buy_signals)
            signals, counts = signal_builder(
                prices, membership, sectors, start, end)
        result = evaluate_signals(
            signals, prices, iterations=args.iterations,
            seed_offset=1100 + offset, exit_rule=EXIT_RULE,
            exit_params=exit_params, trials=declared_trials,
            simulation_start_date=SIMULATION_STARTS[name])
        raw[name] = result
        partitions[name] = {
            "period": [start, end],
            "price_end": price_end,
            "signal_counts": counts,
            "signals": len(signals),
            "exit_states": exit_state_counts(result["trades"]),
            "metrics": result["metrics"],
        }
        cost_stress[name] = {"1": _compact_cost(result)}
        for multiplier in (2, 5, 10):
            stressed = evaluate_signals(
                signals, prices, cost_multiplier=multiplier,
                iterations=args.iterations, seed_offset=1100 + offset + multiplier * 10,
                exit_rule=EXIT_RULE, exit_params=exit_params,
                trials=declared_trials,
                simulation_start_date=SIMULATION_STARTS[name])
            cost_stress[name][str(multiplier)] = _compact_cost(stressed)

    score = discovery_backtest_score(raw["full"]["score_cell"])
    reproduction = (
        ".venv/bin/python scripts/current_ma60_candidate_backtest.py "
        f"--price-csv {args.price_csv} --coverage-json {args.coverage_json} "
        f"--membership-csv {args.membership_csv} --sector-json {args.sector_json} "
        f"--output-dir {args.output_dir} --iterations {args.iterations}"
        + (" --disable-period-exit" if args.disable_period_exit
           else " --qqq-synchronized-exit" if args.qqq_synchronized_exit
           else " --disable-calendar-overlay" if args.disable_calendar_overlay
           else ""))
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "classification": "DESCRIPTIVE_ONLY_VALIDATION_AND_OOS_CONTAMINATED",
        "candidate_spec": spec,
        "declared_trials": declared_trials,
        "coverage": coverage,
        "partitions": partitions,
        "cost_stress": cost_stress,
        "full_robustness": raw["full"]["score_cell"]["robustness"],
        "backtest_score": score,
        "verdict": "DESCRIPTIVE_ONLY",
        "interpretation": (
            "This run measures the current configuration but cannot validate it. "
            "The 10-session slope was selected after a train grid and failed "
            "validation; the exact calendar and this exit-policy comparison "
            "are also post-hoc. Give primary weight to exposure-matched excess, outlier "
            "trims, cost stress and the absence of untouched OOS, not raw CAGR."),
        "reproduction_command": reproduction,
    }

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    label = ("current_ma60_candidate_qqq_synchronized"
             if args.qqq_synchronized_exit
             else "ma60_slope10_no_qqq_regime"
             if args.disable_calendar_overlay
             else "current_ma60_candidate" if period_exit_enabled
             else "current_ma60_candidate_no_period_exit")
    stem = output / f"{label}_{stamp}"
    json_path = stem.with_suffix(".json")
    markdown_path = stem.with_suffix(".md")
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    for name, result in raw.items():
        _csv(Path(f"{stem}_{name}_signals.csv"), result["signals"])
        _csv(Path(f"{stem}_{name}_trades.csv"), result["trades"])
        _csv(Path(f"{stem}_{name}_equity.csv"), result["equity_curve"])
    print(json.dumps({
        "classification": report["classification"],
        "score": score,
        "partitions": {
            name: {
                "signals": part["signals"],
                "exit_states": part["exit_states"],
                "metrics": part["metrics"],
            }
            for name, part in partitions.items()
        },
        "cost_stress": cost_stress,
        "json": str(json_path),
        "markdown": str(markdown_path),
    }, indent=2))


if __name__ == "__main__":
    main()
