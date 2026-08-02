#!/usr/bin/env python3
"""Trial 522-541 discovery grid for stock-versus-SPY MA percentage slopes."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from cross_sectional_leadership_discovery import discovery_backtest_score
from csv_client import CSVClient
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import slice_prices
from relative_divergence_experiment import (
    PERIODS,
    _compact_variant,
    _score_lines,
    _write_csv,
    build_baseline_signals,
    evaluate_signals,
)
from relative_ma50_slope_experiment import (
    SLOPE_SESSIONS,
    _eligible_prices,
    calculate_relative_ma50_slope,
)

MA_PERIODS = tuple(range(10, 201, 10))
TRIALS_BEFORE = 520
TRIALS_AFTER = 540
MIN_TRAIN_TRADES = 20


def _missing_reason(stock_bars: list[dict], spy_bars: list[dict],
                    as_of_date: str, ma_period: int) -> str:
    required = ma_period + SLOPE_SESSIONS
    stock = _eligible_prices(stock_bars, as_of_date)
    spy = _eligible_prices(spy_bars, as_of_date)
    if len(stock) < required:
        return "insufficient_ticker_history"
    if len(spy) < required:
        return "insufficient_spy_history"
    return "insufficient_common_history"


def annotate_signals(signals: list[dict], prices: dict[str, list[dict]],
                     ma_period: int) -> tuple[list[dict], dict[str, int]]:
    """Attach one grid cell's generic relative-MA fields to signal copies."""
    spy_bars = prices.get("SPY") or []
    counts: dict[str, int] = defaultdict(int)
    output = []
    for signal in signals:
        stock_bars = prices.get(signal["symbol"]) or []
        result = calculate_relative_ma50_slope(
            stock_bars, spy_bars, signal["signal_date"],
            ma_period=ma_period, slope_sessions=SLOPE_SESSIONS)
        row = dict(signal)
        row["relative_ma_period"] = ma_period
        row["relative_ma_slope_sessions"] = SLOPE_SESSIONS
        if result is None:
            reason = _missing_reason(
                stock_bars, spy_bars, signal["signal_date"], ma_period)
            counts[reason] += 1
            row.update({
                "stock_signal_close": None,
                "stock_ma_value": None,
                "stock_ma_20_sessions_ago": None,
                "spy_ma_value": None,
                "spy_ma_20_sessions_ago": None,
                "stock_ma_slope_pct": None,
                "spy_ma_slope_pct": None,
                "relative_ma_slope_pct": None,
                "positive_relative_ma_slope": None,
                "relative_ma_signal_date": None,
                "relative_ma_missing_reason": reason,
            })
        else:
            passed = result["positive_relative_ma_slope"]
            counts["available"] += 1
            counts["positive"] += int(passed)
            counts["negative_control"] += int(not passed)
            row.update({
                "stock_signal_close": result["stock_signal_close"],
                "stock_ma_value": result["stock_ma_value"],
                "stock_ma_20_sessions_ago": result["stock_ma_20_sessions_ago"],
                "spy_ma_value": result["spy_ma_value"],
                "spy_ma_20_sessions_ago": result["spy_ma_20_sessions_ago"],
                "stock_ma_slope_pct": result["stock_ma_slope_pct"],
                "spy_ma_slope_pct": result["spy_ma_slope_pct"],
                "relative_ma_slope_pct": result["relative_ma_slope_pct"],
                "positive_relative_ma_slope": passed,
                "relative_ma_signal_date": result["relative_ma_signal_date"],
                "relative_ma_missing_reason": None,
            })
        output.append(row)
    return output, dict(sorted(counts.items()))


def select_positive(signals: list[dict]) -> list[dict]:
    return [dict(row) for row in signals
            if row.get("positive_relative_ma_slope") is True]


def _signal_key(row: dict) -> tuple[str, str, str]:
    return (row["symbol"], row["signal_date"],
            row.get("fill_date") or row.get("entry_date"))


def _cohort_mean_excess(baseline_trades: list[dict],
                        signals: list[dict]) -> dict:
    states = {_signal_key(row): row.get("positive_relative_ma_slope")
              for row in signals}
    qualifying = []
    rejected = []
    for trade in baseline_trades:
        state = states.get(_signal_key(trade))
        if trade.get("net_excess_vs_spy_pct") is None:
            continue
        if state is True:
            qualifying.append(float(trade["net_excess_vs_spy_pct"]))
        elif state is False:
            rejected.append(float(trade["net_excess_vs_spy_pct"]))
    qualifying_mean = statistics.fmean(qualifying) if qualifying else None
    rejected_mean = statistics.fmean(rejected) if rejected else None
    return {
        "qualifying_trades": len(qualifying),
        "rejected_trades": len(rejected),
        "qualifying_mean_excess_pct": qualifying_mean,
        "rejected_mean_excess_pct": rejected_mean,
        "qualifying_minus_rejected_mean_excess_pct_points": (
            qualifying_mean - rejected_mean
            if qualifying_mean is not None and rejected_mean is not None
            else None),
    }


def _cell(period: int, annotated: list[dict], counts: dict[str, int],
          baseline: dict, prices: dict[str, list[dict]],
          iterations: int) -> tuple[dict, dict]:
    positive = select_positive(annotated)
    result = evaluate_signals(positive, prices, iterations=iterations)
    baseline_metrics = baseline["metrics"]
    metrics = result["metrics"]
    cohorts = _cohort_mean_excess(baseline["trades"], annotated)
    difference = cohorts["qualifying_minus_rejected_mean_excess_pct_points"]
    checks = {
        "executed_trades>=20": len(result["trades"]) >= MIN_TRAIN_TRADES,
        "net_cagr_lift>0": (
            metrics["summary"]["cagr_pct"]
            > baseline_metrics["summary"]["cagr_pct"]),
        "exposure_matched_excess_cagr_lift>0": (
            metrics["exposure_matched_excess_cagr_pct"]
            > baseline_metrics["exposure_matched_excess_cagr_pct"]),
        "baseline_pass_minus_fail_excess>0": (
            difference is not None and difference > 0),
        "drop_best_five_expectancy>0": (
            metrics["trade_metrics"]["drop_best_five_net_expectancy_pct"]
            is not None
            and metrics["trade_metrics"]["drop_best_five_net_expectancy_pct"] > 0),
    }
    compact = {
        "ma_period": period,
        "slope_sessions": SLOPE_SESSIONS,
        "history_counts": counts,
        "signals": len(positive),
        "trades": len(result["trades"]),
        "retained_signal_pct": (
            100 * len(positive) / len(annotated) if annotated else None),
        "metrics": metrics,
        "cohorts": cohorts,
        "cagr_lift_pct_points": (
            metrics["summary"]["cagr_pct"]
            - baseline_metrics["summary"]["cagr_pct"]),
        "exposure_matched_excess_cagr_lift_pct_points": (
            metrics["exposure_matched_excess_cagr_pct"]
            - baseline_metrics["exposure_matched_excess_cagr_pct"]),
        "checks": checks,
        "qualified": all(checks.values()),
    }
    return compact, result


def _evaluate_fixed_period(name: str, period: int, detections: dict,
                           prices_all: dict[str, list[dict]], membership: dict,
                           iterations: int) -> tuple[dict, dict[str, dict]]:
    start, end, price_end = PERIODS[name]
    prices = slice_prices(prices_all, start, price_end)
    base_signals, membership_drops = build_baseline_signals(
        detections, prices, membership, start, end)
    annotated, counts = annotate_signals(base_signals, prices, period)
    baseline = evaluate_signals(base_signals, prices, iterations=iterations)
    cell, primary = _cell(
        period, annotated, counts, baseline, prices, iterations)
    return {
        "period": [start, end],
        "membership_drops": membership_drops,
        "baseline": _compact_variant(baseline),
        "primary": _compact_variant(primary),
        "cell": cell,
    }, {"baseline": baseline, "primary": primary}


def select_grid_candidates(cells: list[dict]) -> tuple[list[dict], int | None, dict]:
    """Apply the frozen all-gates rule and deterministic objective/tie-break."""
    qualified = sorted(
        (cell for cell in cells if cell["qualified"]),
        key=lambda cell: (
            -cell["exposure_matched_excess_cagr_lift_pct_points"],
            cell["ma_period"]),
    )
    selected_period = qualified[0]["ma_period"] if qualified else None
    diagnostic = sorted(
        (cell for cell in cells if cell["trades"] >= MIN_TRAIN_TRADES),
        key=lambda cell: (
            -cell["exposure_matched_excess_cagr_lift_pct_points"],
            cell["ma_period"]),
    )
    diagnostic_leader = diagnostic[0] if diagnostic else max(
        cells, key=lambda cell: (cell["trades"], -cell["ma_period"]))
    return qualified, selected_period, diagnostic_leader


def render_markdown(report: dict) -> str:
    highest_cagr = max(
        report["train_grid"], key=lambda cell: cell["metrics"]["summary"]["cagr_pct"])
    lines = ["# Trial 522–541 — Relative-MA Period Grid", "",
             f"Family verdict: **{report['verdict']}**", "",
             *_score_lines(report["backtest_score"]),
             "This is a train-only discovery grid. Slope window stays fixed at "
             "20 sessions; only MA period changes from 10 to 200 by 10.", "",
             "## Train grid", "",
             "| MA | Signals | Trades | CAGR | CAGR lift | Excess CAGR | Excess lift | Sharpe | PF | Pass-fail excess | Drop-best-5 | Gate |",
             "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for cell in report["train_grid"]:
        metrics = cell["metrics"]
        trade = metrics["trade_metrics"]
        drop_five = trade["drop_best_five_net_expectancy_pct"]
        drop_five_text = (f"{drop_five:.2f}%"
                          if drop_five is not None else "unavailable")
        lines.append(
            f"| {cell['ma_period']} | {cell['signals']} | {cell['trades']} | "
            f"{metrics['summary']['cagr_pct']:.2f}% | "
            f"{cell['cagr_lift_pct_points']:.2f} pp | "
            f"{metrics['exposure_matched_excess_cagr_pct']:.2f}% | "
            f"{cell['exposure_matched_excess_cagr_lift_pct_points']:.2f} pp | "
            f"{metrics['sharpe'] or 0:.3f} | "
            f"{trade['net_profit_factor'] or 0:.3f} | "
            f"{cell['cohorts']['qualifying_minus_rejected_mean_excess_pct_points'] or 0:.2f} pp | "
            f"{drop_five_text} | "
            f"{'PASS' if cell['qualified'] else 'FAIL'} |")
    leader = report["diagnostic_leader"]
    lines += ["", "## Selection", "",
              f"Qualified cells: **{len(report['qualified_periods'])}**.",
              f"Selected period: **{report['selected_period'] if report['selected_period'] is not None else 'none'}**.",
              f"Diagnostic leader among cells with at least 20 trades: **MA{leader['ma_period']}**; "
              f"excess-CAGR lift {leader['exposure_matched_excess_cagr_lift_pct_points']:.2f} pp.", "",
              f"Highest raw train CAGR was **MA{highest_cagr['ma_period']} at "
              f"{highest_cagr['metrics']['summary']['cagr_pct']:.2f}%**, but it had "
              f"only {highest_cagr['trades']} trades and drop-best-five expectancy "
              f"{highest_cagr['metrics']['trade_metrics']['drop_best_five_net_expectancy_pct']:.2f}%, "
              "so it was ineligible.", "",
              "Diagnostic leadership is not validation and cannot override a failed gate.", "",
              "## Diagnostic-leader checks", ""]
    lines.extend(f"- {'PASS' if passed else 'FAIL'} — {name}"
                 for name, passed in leader["checks"].items())
    lines += ["", "## Sequential access", "",
              f"Validation accessed: **{'YES' if report['validation_accessed'] else 'NO'}**  ",
              f"Best-available OOS accessed: **{'YES' if report['best_available_oos_accessed'] else 'NO'}**", "",
              "## Interpretation", "", report["interpretation"], "",
              "The grid is multiple-comparison discovery with previously "
              "contaminated MA50 evidence. No displayed winner is prespecified "
              "or deployable without passing the frozen sequence.", "",
              "## Reproduction", "", "```bash", report["reproduction_command"],
              "```", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--output-dir", default="backtests/relative_ma_grid_v2/results")
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
    detections = json.loads(Path(args.backtest_json).read_text())["detections_by_ticker"]
    membership = load_membership(args.membership_csv)

    start, end, price_end = PERIODS["train"]
    train_prices = slice_prices(prices_all, start, price_end)
    base_signals, membership_drops = build_baseline_signals(
        detections, train_prices, membership, start, end)
    baseline = evaluate_signals(base_signals, train_prices, iterations=args.iterations)
    cells = []
    raw_cells = {}
    for period in MA_PERIODS:
        annotated, counts = annotate_signals(base_signals, train_prices, period)
        cell, raw_cells[period] = _cell(
            period, annotated, counts, baseline, train_prices, args.iterations)
        cells.append(cell)
    qualified, selected_period, diagnostic_leader = select_grid_candidates(cells)

    partitions = {}
    raw_partitions = {}
    validation_accessed = selected_period is not None
    validation_passed = False
    best_oos_accessed = False
    if selected_period is not None:
        partitions["validation"], raw_partitions["validation"] = _evaluate_fixed_period(
            "validation", selected_period, detections, prices_all,
            membership, args.iterations)
        validation_cell = partitions["validation"]["cell"]
        validation_passed = (
            validation_cell["trades"] >= 30
            and validation_cell["checks"]["net_cagr_lift>0"]
            and validation_cell["checks"]["exposure_matched_excess_cagr_lift>0"]
            and validation_cell["checks"]["baseline_pass_minus_fail_excess>0"]
            and validation_cell["checks"]["drop_best_five_expectancy>0"]
            and (partitions["validation"]["primary"]["metrics"]["summary"]
                 ["max_drawdown_pct"] - partitions["validation"]["baseline"]
                 ["metrics"]["summary"]["max_drawdown_pct"] >= -2))
        best_oos_accessed = validation_passed
    if best_oos_accessed:
        partitions["best_available_oos"], raw_partitions["best_available_oos"] = (
            _evaluate_fixed_period(
                "best_available_oos", selected_period, detections, prices_all,
                membership, args.iterations))

    score = discovery_backtest_score(raw_cells[diagnostic_leader["ma_period"]]["score_cell"])
    if selected_period is None:
        verdict = "NO_QUALIFYING_WINNER"
        interpretation = (
            "No train grid cell satisfied the five frozen gates. Validation "
            "and best-available OOS therefore remained sealed; the diagnostic "
            "leader is reported only to show why it failed.")
    elif not validation_passed:
        verdict = "VALIDATION_FAIL"
        interpretation = (
            f"MA{selected_period} qualified on train but failed the frozen "
            "validation gate, so best-available OOS remained sealed.")
    else:
        oos_cell = partitions["best_available_oos"]["cell"]
        oos_primary = partitions["best_available_oos"]["primary"]["metrics"]
        improves = (oos_cell["checks"]["net_cagr_lift>0"]
                    and oos_cell["checks"]["exposure_matched_excess_cagr_lift>0"]
                    and oos_cell["checks"]["baseline_pass_minus_fail_excess>0"]
                    and oos_cell["checks"]["drop_best_five_expectancy>0"]
                    and oos_cell["trades"] >= 30
                    and oos_primary["summary"]["cagr_pct"] > 0)
        verdict = "IMPROVES" if improves else "INCONCLUSIVE"
        interpretation = (
            f"MA{selected_period} reached best-available OOS; the final verdict "
            "uses only its frozen OOS economic checks.")
    reproduction = (
        f".venv/bin/python scripts/relative_ma_grid_experiment.py "
        f"{args.backtest_json} --price-csv {args.price_csv} "
        f"--coverage-json {args.coverage_json} "
        f"--membership-csv {args.membership_csv} "
        f"--output-dir {args.output_dir} --iterations {args.iterations}")
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/relative_ma_grid_v2/frozen_spec.md",
        "classification": "train_only_relative_ma_period_grid",
        "parameters": {"ma_periods": MA_PERIODS,
                       "slope_sessions": SLOPE_SESSIONS,
                       "grid_step": 10,
                       "selection_objective": "max train exposure-matched excess CAGR lift among fully qualified cells"},
        "coverage": coverage,
        "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": len(MA_PERIODS),
        "trials_after": TRIALS_AFTER,
        "train_period": [start, end],
        "train_membership_drops": membership_drops,
        "train_baseline": _compact_variant(baseline),
        "train_grid": cells,
        "qualified_periods": [cell["ma_period"] for cell in qualified],
        "selected_period": selected_period,
        "diagnostic_leader": diagnostic_leader,
        "validation_accessed": validation_accessed,
        "validation_passed": validation_passed,
        "best_available_oos_accessed": best_oos_accessed,
        "later_partitions": partitions,
        "backtest_score": score,
        "verdict": verdict,
        "interpretation": interpretation,
        "reproduction_command": reproduction,
    }
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = output / f"relative_ma_grid_{stamp}.json"
    md_path = output / f"relative_ma_grid_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    md_path.write_text(render_markdown(report))
    _write_csv(output / f"relative_ma_grid_{stamp}_baseline_signals.csv", baseline["signals"])
    _write_csv(output / f"relative_ma_grid_{stamp}_baseline_trades.csv", baseline["trades"])
    _write_csv(output / f"relative_ma_grid_{stamp}_baseline_equity.csv", baseline["equity_curve"])
    for period, result in raw_cells.items():
        prefix = output / f"relative_ma_grid_{stamp}_ma{period}"
        _write_csv(prefix.with_name(prefix.name + "_signals.csv"), result["signals"])
        _write_csv(prefix.with_name(prefix.name + "_trades.csv"), result["trades"])
        _write_csv(prefix.with_name(prefix.name + "_equity.csv"), result["equity_curve"])
    print(json.dumps({"verdict": verdict,
                      "qualified_periods": report["qualified_periods"],
                      "selected_period": selected_period,
                      "diagnostic_leader": diagnostic_leader["ma_period"],
                      "validation_accessed": validation_accessed,
                      "best_available_oos_accessed": best_oos_accessed,
                      "score": score}, indent=2))
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
