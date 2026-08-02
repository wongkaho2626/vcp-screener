#!/usr/bin/env python3
"""Trial 521: stock MA50 percentage slope versus SPY MA50 slope."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from breadth_regime import DEFAULT_BREADTH_CSV
from cross_sectional_leadership_discovery import discovery_backtest_score
from csv_client import CSVClient
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import slice_prices
from relative_divergence_experiment import (
    PERIODS,
    _compact_variant,
    _comparison,
    _score_lines,
    _write_csv,
    build_baseline_signals,
    evaluate_signals,
    trade_metrics,
)

MA_PERIOD = 50
SLOPE_SESSIONS = 20
PRIMARY_KEY = "primary_relative_ma50_slope20"
TRIALS_BEFORE = 519
TRIALS_AFTER = 520


def _eligible_prices(bars: list[dict], as_of_date: str) -> dict[str, float]:
    """Return valid adjusted closes no later than as-of without mutation."""
    output = {}
    for bar in sorted(bars, key=lambda row: str(row.get("date") or "")):
        session = str(bar.get("date") or "")
        try:
            value = float(bar.get("adjClose") or bar.get("close") or 0)
        except (TypeError, ValueError):
            value = 0.0
        if session and session <= as_of_date and value > 0 and math.isfinite(value):
            output[session] = value
    return output


def calculate_relative_ma50_slope(
    stock_bars: list[dict],
    spy_bars: list[dict],
    as_of_date: str,
    ma_period: int = MA_PERIOD,
    slope_sessions: int = SLOPE_SESSIONS,
) -> dict | None:
    """Compare normalized stock/SPY MA slopes on identical common sessions."""
    if ma_period <= 0 or slope_sessions <= 0:
        raise ValueError("MA period and slope sessions must be positive")
    stock = _eligible_prices(stock_bars, as_of_date)
    spy = _eligible_prices(spy_bars, as_of_date)
    common_dates = sorted(set(stock).intersection(spy))
    required = ma_period + slope_sessions
    if len(common_dates) < required:
        return None
    current_dates = common_dates[-ma_period:]
    prior_end = len(common_dates) - slope_sessions
    prior_dates = common_dates[prior_end - ma_period:prior_end]
    stock_now = statistics.fmean(stock[session] for session in current_dates)
    stock_then = statistics.fmean(stock[session] for session in prior_dates)
    spy_now = statistics.fmean(spy[session] for session in current_dates)
    spy_then = statistics.fmean(spy[session] for session in prior_dates)
    stock_slope = (stock_now / stock_then - 1) * 100
    spy_slope = (spy_now / spy_then - 1) * 100
    divergence = stock_slope - spy_slope
    stock_close = stock[common_dates[-1]]
    return {
        "ma_period": ma_period,
        "slope_sessions": slope_sessions,
        "stock_signal_close": stock_close,
        "stock_ma_value": stock_now,
        "stock_ma_20_sessions_ago": stock_then,
        "spy_ma_value": spy_now,
        "spy_ma_20_sessions_ago": spy_then,
        "stock_ma_slope_pct": stock_slope,
        "spy_ma_slope_pct": spy_slope,
        "relative_ma_slope_pct": divergence,
        "positive_relative_ma_slope": bool(
            stock_close > stock_now and stock_slope > 0 and divergence > 0),
        "relative_ma_signal_date": common_dates[-1],
        "lookback_start_date": prior_dates[0],
    }


def _missing_reason(stock_bars: list[dict], spy_bars: list[dict],
                    as_of_date: str) -> str:
    required = MA_PERIOD + SLOPE_SESSIONS
    stock = _eligible_prices(stock_bars, as_of_date)
    spy = _eligible_prices(spy_bars, as_of_date)
    if len(stock) < required:
        return "insufficient_ticker_history"
    if len(spy) < required:
        return "insufficient_spy_history"
    return "insufficient_common_history"


def annotate_signals(
    signals: list[dict], prices: dict[str, list[dict]],
) -> tuple[list[dict], dict[str, int]]:
    """Attach copied market-relative MA50 slope fields to baseline signals."""
    spy_bars = prices.get("SPY") or []
    counts: dict[str, int] = defaultdict(int)
    output = []
    for signal in signals:
        stock_bars = prices.get(signal["symbol"]) or []
        result = calculate_relative_ma50_slope(
            stock_bars, spy_bars, signal["signal_date"])
        row = dict(signal)
        row["relative_ma50_period"] = MA_PERIOD
        row["relative_ma50_slope_sessions"] = SLOPE_SESSIONS
        if result is None:
            reason = _missing_reason(
                stock_bars, spy_bars, signal["signal_date"])
            counts[reason] += 1
            row.update({
                "stock_signal_close": None,
                "stock_ma50_value": None,
                "stock_ma50_20_sessions_ago": None,
                "spy_ma50_value": None,
                "spy_ma50_20_sessions_ago": None,
                "stock_ma50_slope_pct": None,
                "spy_ma50_slope_pct": None,
                "relative_ma50_slope_pct": None,
                "positive_relative_ma50_slope": None,
                "relative_ma50_signal_date": None,
                "relative_ma50_missing_reason": reason,
            })
        else:
            passed = result["positive_relative_ma_slope"]
            counts["available"] += 1
            counts["positive"] += int(passed)
            counts["negative_control"] += int(not passed)
            row.update({
                "stock_signal_close": result["stock_signal_close"],
                "stock_ma50_value": result["stock_ma_value"],
                "stock_ma50_20_sessions_ago": result["stock_ma_20_sessions_ago"],
                "spy_ma50_value": result["spy_ma_value"],
                "spy_ma50_20_sessions_ago": result["spy_ma_20_sessions_ago"],
                "stock_ma50_slope_pct": result["stock_ma_slope_pct"],
                "spy_ma50_slope_pct": result["spy_ma_slope_pct"],
                "relative_ma50_slope_pct": result["relative_ma_slope_pct"],
                "positive_relative_ma50_slope": passed,
                "relative_ma50_signal_date": result["relative_ma_signal_date"],
                "relative_ma50_missing_reason": None,
            })
        output.append(row)
    return output, dict(sorted(counts.items()))


def select_signals(signals: list[dict], mode: str) -> list[dict]:
    if mode == "all":
        return [dict(row) for row in signals]
    if mode == "positive":
        return [dict(row) for row in signals
                if row.get("positive_relative_ma50_slope") is True]
    if mode == "negative_control":
        return [dict(row) for row in signals
                if row.get("positive_relative_ma50_slope") is False]
    raise ValueError(f"unknown mode: {mode}")


def _cohorts(trades: list[dict]) -> dict:
    qualifying = [row for row in trades
                  if row.get("positive_relative_ma50_slope") is True]
    rejected = [row for row in trades
                if row.get("positive_relative_ma50_slope") is False]
    qualifying_metrics = trade_metrics(qualifying)
    rejected_metrics = trade_metrics(rejected)
    left = qualifying_metrics["mean_net_excess_pct"]
    right = rejected_metrics["mean_net_excess_pct"]
    return {
        "qualifying": qualifying_metrics,
        "rejected": rejected_metrics,
        "missing": len(trades) - len(qualifying) - len(rejected),
        "qualifying_minus_rejected_mean_excess_pct_points": (
            left - right if left is not None and right is not None else None),
    }


def evaluate_partition(name: str, detections: dict,
                       prices_all: dict[str, list[dict]], membership: dict,
                       iterations: int) -> tuple[dict, dict[str, dict]]:
    start, end, price_end = PERIODS[name]
    prices = slice_prices(prices_all, start, price_end)
    baseline, membership_drops = build_baseline_signals(
        detections, prices, membership, start, end)
    annotated, history_counts = annotate_signals(baseline, prices)
    signals = {
        "baseline": select_signals(annotated, "all"),
        PRIMARY_KEY: select_signals(annotated, "positive"),
        "negative_control": select_signals(annotated, "negative_control"),
    }
    raw = {key: evaluate_signals(rows, prices, iterations=iterations)
           for key, rows in signals.items()}
    comparison = _comparison(
        raw["baseline"], raw[PRIMARY_KEY], raw["negative_control"])
    cohorts = _cohorts(raw["baseline"]["trades"])
    comparison["baseline_qualifying_minus_rejected_mean_excess_pct_points"] = (
        cohorts["qualifying_minus_rejected_mean_excess_pct_points"])
    costs = {}
    for multiplier in (2, 5, 10):
        costs[str(multiplier)] = {
            "baseline": _compact_variant(evaluate_signals(
                signals["baseline"], prices, cost_multiplier=multiplier,
                iterations=max(200, iterations // 5))),
            "primary": _compact_variant(evaluate_signals(
                signals[PRIMARY_KEY], prices, cost_multiplier=multiplier,
                iterations=max(200, iterations // 5))),
        }
    return {
        "period": [start, end],
        "price_end_for_exit_bookkeeping": price_end,
        "membership_drops": membership_drops,
        "history_counts": history_counts,
        "variants": {key: _compact_variant(value) for key, value in raw.items()},
        "comparison": comparison,
        "baseline_trade_cohorts": cohorts,
        "cost_stress": costs,
    }, raw


def _decision(partitions: dict, raw: dict[str, dict[str, dict]]) -> tuple[str, dict]:
    checks = {}
    for name in PERIODS:
        comparison = partitions[name]["comparison"]
        trade = raw[name][PRIMARY_KEY]["metrics"]["trade_metrics"]
        checks[name] = {
            "net_cagr_lift>0": comparison["net_cagr_lift_pct_points"] > 0,
            "exposure_matched_excess_cagr_lift>0": (
                comparison["exposure_matched_excess_cagr_lift_pct_points"] > 0),
            "baseline_pass_minus_fail_excess>0": (
                comparison[
                    "baseline_qualifying_minus_rejected_mean_excess_pct_points"]
                is not None and comparison[
                    "baseline_qualifying_minus_rejected_mean_excess_pct_points"] > 0),
            "drop_best_five_expectancy>0": (
                trade["drop_best_five_net_expectancy_pct"] is not None
                and trade["drop_best_five_net_expectancy_pct"] > 0),
        }
    oos = raw["best_available_oos"][PRIMARY_KEY]
    oos_comparison = partitions["best_available_oos"]["comparison"]
    oos_checks = {
        "oos_trades>=30": len(oos["trades"]) >= 30,
        "oos_cagr>0": oos["metrics"]["summary"]["cagr_pct"] > 0,
        "oos_mdd_not_worse_by_more_than_2pp": (
            oos_comparison["mdd_change_pct_points"] >= -2),
        "oos_5x_cost_cagr>0": (
            partitions["best_available_oos"]["cost_stress"]["5"]
            ["primary"]["metrics"]["summary"]["cagr_pct"] > 0),
    }
    improves = (all(checks["train"].values())
                and all(checks["validation"].values())
                and all(checks["best_available_oos"].values())
                and all(oos_checks.values()))
    consistently_worse = all(
        not checks[name]["net_cagr_lift>0"]
        and not checks[name]["baseline_pass_minus_fail_excess>0"]
        for name in checks)
    verdict = "IMPROVES" if improves else (
        "WORSENS" if consistently_worse else "INCONCLUSIVE")
    return verdict, {"fold_checks": checks, "oos_checks": oos_checks}


def render_markdown(report: dict) -> str:
    lines = ["# Trial 521 — Stock-versus-SPY MA50 Slope Gate", "",
             f"Final verdict: **{report['verdict']}**", "",
             *_score_lines(report["backtest_score"]),
             "The primary compares percentage MA50 changes over 20 aligned "
             "common sessions. Stock slope must be positive and strictly above "
             "SPY slope; stock close must also exceed stock SMA50.", "",
             "## Fold results", "",
             "| Fold | Variant | Signals | Trades | CAGR | Sharpe | Sortino | MDD | Excess CAGR | Mean trade excess | PF | Drop-best-5 |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for partition, cell in report["partitions"].items():
        for variant, result in cell["variants"].items():
            metrics = result["metrics"]
            trade = metrics["trade_metrics"]
            lines.append(
                f"| {partition} | {variant} | {result['signals']} | "
                f"{result['trades']} | {metrics['summary']['cagr_pct']:.2f}% | "
                f"{metrics['sharpe'] or 0:.3f} | {metrics['sortino'] or 0:.3f} | "
                f"{metrics['summary']['max_drawdown_pct']:.2f}% | "
                f"{metrics['exposure_matched_excess_cagr_pct']:.2f}% | "
                f"{trade['mean_net_excess_pct'] or 0:.2f}% | "
                f"{trade['net_profit_factor'] or 0:.3f} | "
                f"{trade['drop_best_five_net_expectancy_pct'] or 0:.2f}% |")
    lines += ["", "## Primary lift", "",
              "| Fold | Retained signals | CAGR lift | Excess CAGR lift | Pass-minus-fail excess | MDD change |",
              "|---|---:|---:|---:|---:|---:|"]
    for partition, cell in report["partitions"].items():
        comparison = cell["comparison"]
        lines.append(
            f"| {partition} | {comparison['retained_signal_pct']:.1f}% | "
            f"{comparison['net_cagr_lift_pct_points']:.2f} pp | "
            f"{comparison['exposure_matched_excess_cagr_lift_pct_points']:.2f} pp | "
            f"{comparison['baseline_qualifying_minus_rejected_mean_excess_pct_points'] or 0:.2f} pp | "
            f"{comparison['mdd_change_pct_points']:.2f} pp |")
    lines += ["", "## Counts and missing history", "",
              "| Fold | Available | Positive | Negative | Missing | PIT detection/signal/fill drops |",
              "|---|---:|---:|---:|---:|---:|"]
    for partition, cell in report["partitions"].items():
        counts = cell["history_counts"]
        missing = sum(value for key, value in counts.items()
                      if key not in ("available", "positive", "negative_control"))
        drops = cell["membership_drops"]
        lines.append(
            f"| {partition} | {counts.get('available', 0)} | "
            f"{counts.get('positive', 0)} | {counts.get('negative_control', 0)} | "
            f"{missing} | {drops['detection_date']}/{drops['signal_date']}/{drops['fill_date']} |")
    oos = report["partitions"]["best_available_oos"]
    trade = oos["variants"][PRIMARY_KEY]["metrics"]["trade_metrics"]
    lines += ["", "## Best-available OOS robustness", "",
              f"- Mean matched-SPY excess: {trade['mean_net_excess_pct']:.2f}% "
              f"(bootstrap 95% CI {trade['excess_bootstrap_95ci_pct']}; "
              f"clustered t {trade['entry_month_clustered_t']:.2f}).",
              f"- Drop-best-five expectancy: {trade['drop_best_five_net_expectancy_pct']:.2f}%; "
              f"winsorized: {trade['winsorized_net_expectancy_pct']:.2f}%.", "",
              "| Cost | Baseline CAGR | Primary CAGR | Baseline MDD | Primary MDD |",
              "|---:|---:|---:|---:|---:|"]
    for multiplier, cells in oos["cost_stress"].items():
        baseline = cells["baseline"]["metrics"]["summary"]
        primary = cells["primary"]["metrics"]["summary"]
        lines.append(f"| {multiplier}x | {baseline['cagr_pct']:.2f}% | "
                     f"{primary['cagr_pct']:.2f}% | "
                     f"{baseline['max_drawdown_pct']:.2f}% | "
                     f"{primary['max_drawdown_pct']:.2f}% |")
    lines += ["", "## Best-available OOS calendar years", "",
              "| Year | Baseline return | Primary return | Baseline excess | Primary excess |",
              "|---:|---:|---:|---:|---:|"]
    baseline_years = oos["variants"]["baseline"]["metrics"]["calendar_years"]
    primary_years = oos["variants"][PRIMARY_KEY]["metrics"]["calendar_years"]
    for year in sorted(set(baseline_years).intersection(primary_years)):
        baseline_year = baseline_years[year]
        primary_year = primary_years[year]
        lines.append(
            f"| {year} | {baseline_year['portfolio_return_pct']:.2f}% | "
            f"{primary_year['portfolio_return_pct']:.2f}% | "
            f"{baseline_year['exposure_matched_excess_return_pct']:.2f}% | "
            f"{primary_year['exposure_matched_excess_return_pct']:.2f}% |")
    lines += ["", "## Decision checks", ""]
    for partition, checks in report["decision_checks"]["fold_checks"].items():
        lines += [f"### {partition}", ""]
        lines.extend(f"- {'PASS' if passed else 'FAIL'} — {name}"
                     for name, passed in checks.items())
        lines.append("")
    lines += ["### OOS economics", ""]
    lines.extend(f"- {'PASS' if passed else 'FAIL'} — {name}"
                 for name, passed in report["decision_checks"]["oos_checks"].items())
    lines += ["", "## Interpretation", "", report["interpretation"], "",
              "The final partition is best-available rather than untouched OOS; "
              "incomplete delisted coverage and prior trend/relative-strength "
              "research remain material limitations.", "", "## Reproduction", "",
              "```bash", report["reproduction_command"], "```", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--breadth-csv", default=DEFAULT_BREADTH_CSV)
    parser.add_argument("--output-dir", default="backtests/relative_ma50_slope_v2/results")
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
    partitions, raw = {}, {}
    for partition in PERIODS:
        partitions[partition], raw[partition] = evaluate_partition(
            partition, detections, prices_all, membership, args.iterations)
    verdict, decision_checks = _decision(partitions, raw)
    score = discovery_backtest_score(
        raw["best_available_oos"][PRIMARY_KEY]["score_cell"])
    oos = partitions["best_available_oos"]
    primary = oos["variants"][PRIMARY_KEY]["metrics"]
    comparison = oos["comparison"]
    interpretation = (
        f"The gate retained {comparison['retained_signal_pct']:.1f}% of OOS "
        f"signals, changed CAGR by {comparison['net_cagr_lift_pct_points']:.2f} "
        f"percentage points to {primary['summary']['cagr_pct']:.2f}%, and "
        "changed baseline qualifying-minus-rejected matched excess by "
        f"{comparison['baseline_qualifying_minus_rejected_mean_excess_pct_points']:.2f} "
        "points. The verdict uses the frozen multi-fold economic checks.")
    reproduction = (
        f".venv/bin/python scripts/relative_ma50_slope_experiment.py "
        f"{args.backtest_json} --price-csv {args.price_csv} "
        f"--coverage-json {args.coverage_json} "
        f"--membership-csv {args.membership_csv} --breadth-csv {args.breadth_csv} "
        f"--output-dir {args.output_dir} --iterations {args.iterations}")
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/relative_ma50_slope_v2/frozen_spec.md",
        "classification": "fixed_aligned_relative_ma50_slope_evaluation",
        "parameters": {"ma_period": MA_PERIOD,
                       "slope_sessions": SLOPE_SESSIONS,
                       "alignment": "actual common stock/SPY dates <= signal date",
                       "comparison": "percentage MA change",
                       "strict_stock_positive": True,
                       "strict_stock_above_spy": True,
                       "strict_close_above_stock_ma": True},
        "coverage": coverage,
        "trials_before": TRIALS_BEFORE,
        "trials_after": TRIALS_AFTER,
        "partitions": partitions,
        "decision_checks": decision_checks,
        "backtest_score": score,
        "verdict": verdict,
        "interpretation": interpretation,
        "reproduction_command": reproduction,
    }
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = output / f"relative_ma50_slope_{stamp}.json"
    md_path = output / f"relative_ma50_slope_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    md_path.write_text(render_markdown(report))
    for partition, variants in raw.items():
        for variant, result in variants.items():
            prefix = output / f"relative_ma50_slope_{stamp}_{partition}_{variant}"
            _write_csv(prefix.with_name(prefix.name + "_signals.csv"), result["signals"])
            _write_csv(prefix.with_name(prefix.name + "_trades.csv"), result["trades"])
            _write_csv(prefix.with_name(prefix.name + "_equity.csv"), result["equity_curve"])
    print(json.dumps({"verdict": verdict, "decision_checks": decision_checks,
                      "score": score}, indent=2))
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
