#!/usr/bin/env python3
"""Trial 520: strict positive MA50-slope gate on the frozen VCP strategy."""

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
TRIALS_BEFORE = 518
TRIALS_AFTER = 519


def _valid_closes(bars: list[dict], as_of_date: str) -> list[tuple[str, float]]:
    """Return sorted adjusted closes available no later than the as-of date."""
    eligible: dict[str, float] = {}
    for bar in sorted(bars, key=lambda row: str(row.get("date") or "")):
        session = str(bar.get("date") or "")
        try:
            value = float(bar.get("adjClose") or bar.get("close") or 0)
        except (TypeError, ValueError):
            value = 0.0
        if session and session <= as_of_date and value > 0 and math.isfinite(value):
            eligible[session] = value
    return sorted(eligible.items())


def calculate_ma50_slope(
    stock_bars: list[dict],
    as_of_date: str,
    ma_period: int = MA_PERIOD,
    slope_sessions: int = SLOPE_SESSIONS,
) -> dict | None:
    """Calculate a causal strict close/MA and MA-slope state without mutation."""
    if ma_period <= 0 or slope_sessions <= 0:
        raise ValueError("MA period and slope sessions must be positive")
    closes = _valid_closes(stock_bars, as_of_date)
    required = ma_period + slope_sessions
    if len(closes) < required:
        return None
    current_window = [value for _, value in closes[-ma_period:]]
    prior_end = len(closes) - slope_sessions
    prior_window = [value for _, value in closes[
        prior_end - ma_period:prior_end]]
    current_ma = statistics.fmean(current_window)
    prior_ma = statistics.fmean(prior_window)
    signal_close = closes[-1][1]
    slope_pct = (current_ma / prior_ma - 1) * 100
    return {
        "ma_period": ma_period,
        "slope_sessions": slope_sessions,
        "signal_close": signal_close,
        "ma_value": current_ma,
        "ma_20_sessions_ago": prior_ma,
        "ma_slope_pct": slope_pct,
        "positive_ma_slope": bool(
            signal_close > current_ma and current_ma > prior_ma),
        "ma_signal_date": closes[-1][0],
    }


def annotate_signals(
    signals: list[dict], prices: dict[str, list[dict]],
) -> tuple[list[dict], dict[str, int]]:
    """Attach the frozen MA50 state to copied baseline signals."""
    counts: dict[str, int] = defaultdict(int)
    output = []
    for signal in signals:
        result = calculate_ma50_slope(
            prices.get(signal["symbol"]) or [], signal["signal_date"])
        row = dict(signal)
        row["ma50_period"] = MA_PERIOD
        row["ma50_slope_sessions"] = SLOPE_SESSIONS
        if result is None:
            counts["insufficient_history"] += 1
            row.update({
                "signal_close": None,
                "ma50_value": None,
                "ma50_20_sessions_ago": None,
                "ma50_slope_pct": None,
                "positive_ma50_slope": None,
                "ma50_signal_date": None,
                "ma50_missing_reason": "insufficient_history",
            })
        else:
            passed = result["positive_ma_slope"]
            counts["available"] += 1
            counts["positive"] += int(passed)
            counts["negative_control"] += int(not passed)
            row.update({
                "signal_close": result["signal_close"],
                "ma50_value": result["ma_value"],
                "ma50_20_sessions_ago": result["ma_20_sessions_ago"],
                "ma50_slope_pct": result["ma_slope_pct"],
                "positive_ma50_slope": passed,
                "ma50_signal_date": result["ma_signal_date"],
                "ma50_missing_reason": None,
            })
        output.append(row)
    return output, dict(sorted(counts.items()))


def select_signals(signals: list[dict], mode: str) -> list[dict]:
    """Return copied baseline, positive-slope or negative-control signals."""
    if mode == "all":
        return [dict(row) for row in signals]
    if mode == "positive":
        return [dict(row) for row in signals
                if row.get("positive_ma50_slope") is True]
    if mode == "negative_control":
        return [dict(row) for row in signals
                if row.get("positive_ma50_slope") is False]
    raise ValueError(f"unknown mode: {mode}")


def _cohort_comparison(baseline_trades: list[dict]) -> dict:
    qualifying = [row for row in baseline_trades
                  if row.get("positive_ma50_slope") is True]
    rejected = [row for row in baseline_trades
                if row.get("positive_ma50_slope") is False]
    qualifying_metrics = trade_metrics(qualifying)
    rejected_metrics = trade_metrics(rejected)
    left = qualifying_metrics["mean_net_excess_pct"]
    right = rejected_metrics["mean_net_excess_pct"]
    return {
        "qualifying": qualifying_metrics,
        "rejected": rejected_metrics,
        "missing": len(baseline_trades) - len(qualifying) - len(rejected),
        "qualifying_minus_rejected_mean_excess_pct_points": (
            left - right if left is not None and right is not None else None),
    }


def evaluate_partition(
    name: str,
    detections: dict,
    prices_all: dict[str, list[dict]],
    membership: dict,
    iterations: int,
) -> tuple[dict, dict[str, dict]]:
    start, end, price_end = PERIODS[name]
    prices = slice_prices(prices_all, start, price_end)
    baseline_signals, membership_drops = build_baseline_signals(
        detections, prices, membership, start, end)
    annotated, history_counts = annotate_signals(baseline_signals, prices)
    signals = {
        "baseline": select_signals(annotated, "all"),
        "primary_ma50_slope20": select_signals(annotated, "positive"),
        "negative_control": select_signals(annotated, "negative_control"),
    }
    raw = {
        variant: evaluate_signals(rows, prices, iterations=iterations)
        for variant, rows in signals.items()
    }
    comparison = _comparison(
        raw["baseline"], raw["primary_ma50_slope20"],
        raw["negative_control"])
    cohorts = _cohort_comparison(raw["baseline"]["trades"])
    comparison["baseline_qualifying_minus_rejected_mean_excess_pct_points"] = (
        cohorts["qualifying_minus_rejected_mean_excess_pct_points"])
    costs = {}
    for multiplier in (2, 5, 10):
        costs[str(multiplier)] = {
            "baseline": _compact_variant(evaluate_signals(
                signals["baseline"], prices, cost_multiplier=multiplier,
                iterations=max(200, iterations // 5))),
            "primary": _compact_variant(evaluate_signals(
                signals["primary_ma50_slope20"], prices,
                cost_multiplier=multiplier,
                iterations=max(200, iterations // 5))),
        }
    report = {
        "period": [start, end],
        "price_end_for_exit_bookkeeping": price_end,
        "membership_drops": membership_drops,
        "history_counts": history_counts,
        "variants": {key: _compact_variant(value) for key, value in raw.items()},
        "comparison": comparison,
        "baseline_trade_cohorts": cohorts,
        "cost_stress": costs,
    }
    return report, raw


def _decision(partitions: dict, raw: dict[str, dict[str, dict]]) -> tuple[str, dict]:
    checks = {}
    for name in ("train", "validation", "best_available_oos"):
        comparison = partitions[name]["comparison"]
        primary = raw[name]["primary_ma50_slope20"]
        trade = primary["metrics"]["trade_metrics"]
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
    oos = raw["best_available_oos"]["primary_ma50_slope20"]
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
    improves = (
        all(checks["train"].values())
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
    lines = [
        "# Trial 520 — Positive MA50 Slope Gate", "",
        f"Final verdict: **{report['verdict']}**", "",
        *_score_lines(report["backtest_score"]),
        "The single frozen primary requires close above SMA50 and SMA50 today "
        "strictly above its value 20 stock sessions earlier. No alternative "
        "window or threshold was searched.", "",
        "## Fold results", "",
        "| Fold | Variant | Signals | Trades | CAGR | Sharpe | Sortino | MDD | Exposure-matched excess CAGR | Mean trade excess | PF |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
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
                f"{trade['net_profit_factor'] or 0:.3f} |")
    lines += ["", "## Primary lift and matched cohorts", "",
              "| Fold | Retained signals | CAGR lift | Excess CAGR lift | Pass-minus-fail mean excess | MDD change |",
              "|---|---:|---:|---:|---:|---:|"]
    for partition, cell in report["partitions"].items():
        comparison = cell["comparison"]
        lines.append(
            f"| {partition} | {comparison['retained_signal_pct']:.1f}% | "
            f"{comparison['net_cagr_lift_pct_points']:.2f} pp | "
            f"{comparison['exposure_matched_excess_cagr_lift_pct_points']:.2f} pp | "
            f"{comparison['baseline_qualifying_minus_rejected_mean_excess_pct_points'] or 0:.2f} pp | "
            f"{comparison['mdd_change_pct_points']:.2f} pp |")
    lines += ["", "## Signal counts and exclusions", "",
              "| Fold | Available | Positive | Negative | Missing | PIT detection/signal/fill drops |",
              "|---|---:|---:|---:|---:|---:|"]
    for partition, cell in report["partitions"].items():
        counts = cell["history_counts"]
        drops = cell["membership_drops"]
        lines.append(
            f"| {partition} | {counts.get('available', 0)} | "
            f"{counts.get('positive', 0)} | {counts.get('negative_control', 0)} | "
            f"{counts.get('insufficient_history', 0)} | "
            f"{drops['detection_date']}/{drops['signal_date']}/{drops['fill_date']} |")
    lines += ["", "## Decision checks", ""]
    for partition, checks in report["decision_checks"]["fold_checks"].items():
        lines.append(f"### {partition}")
        lines.append("")
        lines.extend(f"- {'PASS' if passed else 'FAIL'} — {name}"
                     for name, passed in checks.items())
        lines.append("")
    lines += ["### Best-available OOS economic checks", ""]
    lines.extend(f"- {'PASS' if passed else 'FAIL'} — {name}"
                 for name, passed in report["decision_checks"]["oos_checks"].items())
    oos = report["partitions"]["best_available_oos"]
    primary = oos["variants"]["primary_ma50_slope20"]["metrics"]
    trade = primary["trade_metrics"]
    lines += ["", "## Best-available OOS robustness", "",
              f"- Mean net trade return: {trade['mean_net_return_pct']:.2f}%.",
              f"- Mean matched-SPY excess: {trade['mean_net_excess_pct']:.2f}% "
              f"(bootstrap 95% CI {trade['excess_bootstrap_95ci_pct']}; "
              f"entry-month clustered t {trade['entry_month_clustered_t']:.2f}).",
              f"- Drop-best-five expectancy: {trade['drop_best_five_net_expectancy_pct']:.2f}%; "
              f"winsorized expectancy: {trade['winsorized_net_expectancy_pct']:.2f}%.", "",
              "| Cost multiplier | Baseline CAGR | Primary CAGR | Baseline MDD | Primary MDD |",
              "|---:|---:|---:|---:|---:|"]
    for multiplier, cells in oos["cost_stress"].items():
        baseline_metrics = cells["baseline"]["metrics"]["summary"]
        primary_metrics = cells["primary"]["metrics"]["summary"]
        lines.append(
            f"| {multiplier}x | {baseline_metrics['cagr_pct']:.2f}% | "
            f"{primary_metrics['cagr_pct']:.2f}% | "
            f"{baseline_metrics['max_drawdown_pct']:.2f}% | "
            f"{primary_metrics['max_drawdown_pct']:.2f}% |")
    lines += ["", "## Best-available OOS calendar years", "",
              "| Year | Baseline return | Primary return | Baseline excess | Primary excess |",
              "|---:|---:|---:|---:|---:|"]
    baseline_years = oos["variants"]["baseline"]["metrics"]["calendar_years"]
    primary_years = primary["calendar_years"]
    for year in sorted(set(baseline_years).intersection(primary_years)):
        baseline_year = baseline_years[year]
        primary_year = primary_years[year]
        lines.append(
            f"| {year} | {baseline_year['portfolio_return_pct']:.2f}% | "
            f"{primary_year['portfolio_return_pct']:.2f}% | "
            f"{baseline_year['exposure_matched_excess_return_pct']:.2f}% | "
            f"{primary_year['exposure_matched_excess_return_pct']:.2f}% |")
    lines += ["", "## Interpretation", "", report["interpretation"], "",
              "This is overlapping trend evidence, the final partition is "
              "previously contaminated, and incomplete delisted coverage "
              "retains the survivorship cap.", "", "## Reproduction", "",
              "```bash", report["reproduction_command"], "```", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--breadth-csv", default=DEFAULT_BREADTH_CSV)
    parser.add_argument("--output-dir", default="backtests/ma50_slope_v2/results")
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

    partitions = {}
    raw = {}
    for partition in ("train", "validation", "best_available_oos"):
        partitions[partition], raw[partition] = evaluate_partition(
            partition, detections, prices_all, membership, args.iterations)
    verdict, decision_checks = _decision(partitions, raw)
    score = discovery_backtest_score(
        raw["best_available_oos"]["primary_ma50_slope20"]["score_cell"])
    oos = partitions["best_available_oos"]
    oos_primary = oos["variants"]["primary_ma50_slope20"]["metrics"]
    oos_comparison = oos["comparison"]
    interpretation = (
        f"The primary retained {oos_comparison['retained_signal_pct']:.1f}% of "
        f"best-available OOS signals and changed CAGR by "
        f"{oos_comparison['net_cagr_lift_pct_points']:.2f} percentage points. "
        f"Its net CAGR was {oos_primary['summary']['cagr_pct']:.2f}% and its "
        f"baseline qualifying-minus-rejected matched excess difference was "
        f"{oos_comparison['baseline_qualifying_minus_rejected_mean_excess_pct_points']:.2f} "
        "percentage points. The verdict follows the frozen multi-fold and "
        "economic checks, not a single headline return.")
    reproduction = (
        f".venv/bin/python scripts/ma50_slope_experiment.py {args.backtest_json} "
        f"--price-csv {args.price_csv} --coverage-json {args.coverage_json} "
        f"--membership-csv {args.membership_csv} --breadth-csv {args.breadth_csv} "
        f"--output-dir {args.output_dir} --iterations {args.iterations}")
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/ma50_slope_v2/frozen_spec.md",
        "classification": "fixed_three_fold_ma50_slope_evaluation",
        "parameters": {"ma_period": MA_PERIOD,
                       "slope_sessions": SLOPE_SESSIONS,
                       "strict_close_above_ma": True,
                       "strict_positive_slope": True,
                       "signal_timing": "signal-date close; existing next open"},
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
    json_path = output / f"ma50_slope_{stamp}.json"
    md_path = output / f"ma50_slope_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    md_path.write_text(render_markdown(report))
    for partition, variants in raw.items():
        for variant, result in variants.items():
            prefix = output / f"ma50_slope_{stamp}_{partition}_{variant}"
            _write_csv(prefix.with_name(prefix.name + "_signals.csv"), result["signals"])
            _write_csv(prefix.with_name(prefix.name + "_trades.csv"), result["trades"])
            _write_csv(prefix.with_name(prefix.name + "_equity.csv"), result["equity_curve"])
    print(json.dumps({"verdict": verdict, "decision_checks": decision_checks,
                      "score": score}, indent=2))
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
