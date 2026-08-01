#!/usr/bin/env python3
"""Verify the frozen Trial-288 existing-data exploratory replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics as st
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from csv_client import CSVClient
from edge_rank import DEFAULT_W_EXT, DEFAULT_W_RS
from linear_timing_discovery import (
    build_rows,
    signals_with_decay,
    threshold_from_rows,
    trade_stats,
    trim_stats,
)
from membership import is_member, load_membership
from pivot_retest_experiment import filter_detections, slice_prices
from portfolio_backtest import Config, run_portfolio
from portfolio_robustness import (
    deflated_sharpe,
    effective_sample_size,
    max_drawdown,
    probabilistic_sharpe,
    sharpe,
)


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_cell(signals: list[dict], prices: dict, cost_multiplier: float = 1) -> dict:
    cfg = Config(
        commission_bps=5.0 * cost_multiplier,
        slippage_bps=5.0 * cost_multiplier,
    )
    with patch("portfolio_backtest._candidate_signals", return_value=signals):
        portfolio = run_portfolio({}, prices, cfg, exit_rule="model_decay")
    return {
        "summary": portfolio["summary"],
        "trade_stats": trade_stats(portfolio["trades"]),
        "drop_top_5": trim_stats(portfolio["trades"], 5),
        "trades": portfolio["trades"],
        "equity_curve": portfolio["equity_curve"],
    }


def decimal_cagr(values: list[float]) -> float:
    if not values:
        return 0.0
    wealth = math.prod(1 + value for value in values)
    return wealth ** (252 / len(values)) - 1 if wealth > 0 else -1.0


def period_metrics(curve: list[dict], start: str, end: str) -> dict:
    rows = [row for row in curve if start <= row["date"] <= end]
    returns = [float(row["portfolio_return"]) for row in rows]
    if not returns:
        return {"start": start, "end": end, "observations": 0}
    months: dict[str, list[float]] = {}
    for row, value in zip(rows, returns):
        months.setdefault(row["date"][:7], []).append(value)
    monthly = [math.prod(1 + value for value in values) - 1 for values in months.values()]
    return {
        "start": start,
        "end": end,
        "observations": len(returns),
        "total_return_pct": (math.prod(1 + value for value in returns) - 1) * 100,
        "cagr_pct": decimal_cagr(returns) * 100,
        "sharpe": sharpe(returns),
        "max_drawdown_pct": max_drawdown(returns)[0] * 100,
        "positive_months_pct": (
            sum(value > 0 for value in monthly) / len(monthly) * 100 if monthly else None
        ),
    }


def trade_bootstrap(trades: list[dict], iterations: int = 5000) -> dict:
    values = [float(trade["net_return_pct"]) for trade in trades]
    rng = random.Random(20260801)
    expectancies, factors = [], []
    for _ in range(iterations):
        sample = rng.choices(values, k=len(values))
        expectancies.append(st.fmean(sample))
        gains = sum(value for value in sample if value > 0)
        losses = -sum(value for value in sample if value < 0)
        factors.append(gains / losses if losses else float("inf"))

    def quantile(values_: list[float], q: float) -> float:
        finite = sorted(value for value in values_ if math.isfinite(value))
        pos = (len(finite) - 1) * q
        lo, hi = math.floor(pos), math.ceil(pos)
        return finite[lo] if lo == hi else finite[lo] * (hi - pos) + finite[hi] * (pos - lo)

    return {
        "iterations": iterations,
        "expectancy_pct": {
            "p05": quantile(expectancies, .05),
            "median": quantile(expectancies, .50),
            "p95": quantile(expectancies, .95),
            "probability_nonpositive": sum(value <= 0 for value in expectancies) / iterations,
        },
        "profit_factor": {
            "p05": quantile(factors, .05),
            "median": quantile(factors, .50),
            "p95": quantile(factors, .95),
        },
    }


def ljung_box(returns: list[float], lag: int = 10) -> dict:
    n = len(returns)
    mean = st.fmean(returns)
    denom = sum((value - mean) ** 2 for value in returns)
    correlations = []
    for offset in range(1, min(lag, n - 1) + 1):
        numerator = sum(
            (returns[index] - mean) * (returns[index - offset] - mean)
            for index in range(offset, n)
        )
        correlations.append(numerator / denom if denom else 0.0)
    statistic = n * (n + 2) * sum(
        correlation * correlation / (n - offset)
        for offset, correlation in enumerate(correlations, 1)
    )
    try:
        from scipy.stats import chi2
        p_value = float(chi2.sf(statistic, len(correlations)))
    except Exception:
        degrees = len(correlations)
        # Exact chi-square survival function for positive even degrees of
        # freedom: Q(k/2, x/2) = exp(-x/2) * sum_0^(k/2-1) (x/2)^j/j!.
        p_value = (
            math.exp(-statistic / 2) * sum(
                (statistic / 2) ** term / math.factorial(term)
                for term in range(degrees // 2)
            )
            if degrees > 0 and degrees % 2 == 0 else None
        )
    return {"lag": len(correlations), "statistic": statistic, "p_value": p_value}


def score(report: dict, sensitivity_rows: list[dict]) -> dict:
    robust = report["internal_holdout"]["cell"]["robustness"]
    stats = report["internal_holdout"]["cell"]["trade_stats"]
    trimmed = report["internal_holdout"]["cell"]["drop_top_5"]
    t_stat = robust["significance"]["t_statistic"]
    psr = robust["significance"]["psr_vs_zero"]
    dsr = robust["significance"]["approximate_dsr"]["probability"]
    sharpe_value = robust["risk_adjusted"]["sharpe"]
    sortino = robust["risk_adjusted"]["sortino"]
    calmar = robust["risk_adjusted"]["calmar"]
    mdd = abs(robust["risk"]["max_drawdown"])
    positive_months = robust["stability"]["positive_months"]

    a_t = 8 if t_stat > 3 else 6 if t_stat > 2 else 4 if t_stat > 1.65 else 0
    a_psr = 7 if psr > .95 else 5 if psr > .90 else 3 if psr > .80 else 0
    a_dsr = 8 if dsr > .95 else 4 if dsr > .50 else 0
    a_sample = 7 if stats["trades"] >= 30 and robust["sample"]["observations"] >= 756 else 4
    a = a_t + a_psr + a_dsr + a_sample

    b_sharpe = 10 if sharpe_value > 2 else 7 if sharpe_value > 1 else 4 if sharpe_value > .5 else 0
    b_adjusted = 8 if max(sortino / 2.5, calmar / 2) >= 1 else 5 if (sortino > 1.5 or calmar > 1) else 3 if (sortino > .7 or calmar > .5) else 0
    b_mdd = 7 if mdd < .10 else 5 if mdd < .20 else 3 if mdd < .30 else 0
    b = b_sharpe + b_adjusted + b_mdd

    bootstrap = robust["block_bootstrap"]["cagr"]
    c_wfa = 0  # first/second fold efficiency is not meaningful with a nonpositive first fold
    c_bootstrap = 8 if bootstrap["p05"] > 0 else 4 if bootstrap["median"] > 0 else 0
    sensitivity_cagrs = [row["cagr_pct"] for row in sensitivity_rows]
    positive_share = sum(value > 0 for value in sensitivity_cagrs) / len(sensitivity_cagrs)
    c_sensitivity = 7 if min(sensitivity_cagrs) > 0 else 4 if positive_share >= .5 else 0
    c = c_wfa + c_bootstrap + c_sensitivity

    pf = stats["profit_factor"] or 0
    d_pf = 7 if pf > 2 else 5 if pf > 1.5 else 3 if pf > 1.2 else 0
    d_coherence = 6 if stats["expectancy_pct"] > 0 and trimmed["expectancy_pct"] > 0 else 3 if stats["expectancy_pct"] > 0 else 0
    d_consistency = 7 if positive_months > .65 else 5 if positive_months > .55 else 3 if positive_months > .50 else 0
    d = d_pf + d_coherence + d_consistency
    raw = a + b + c + d
    return {
        "A": {"t_stat": a_t, "psr": a_psr, "dsr": a_dsr, "sample": a_sample, "total": a, "max": 30},
        "B": {"sharpe": b_sharpe, "sortino_or_calmar": b_adjusted, "drawdown": b_mdd, "total": b, "max": 25},
        "C": {"wfa": c_wfa, "bootstrap": c_bootstrap, "sensitivity": c_sensitivity, "total": c, "max": 25},
        "D": {"profit_factor": d_pf, "coherence": d_coherence, "consistency": d_consistency, "total": d, "max": 20},
        "raw_score_ignoring_survivorship_cap": raw,
        "caps": {"unresolved_survivorship": 20},
        "final_score": min(raw, 20),
    }


def markdown(payload: dict) -> str:
    main = payload["primary"]
    robust = main["robustness"]
    stats = main["trade_stats"]
    score_ = payload["score"]
    costs = payload["cost_stress"]
    folds = payload["folds"]
    sensitivity = payload["parameter_sensitivity"]
    lines = [
        "# Backtest Verification Report — Existing-Data Exploratory Replay", "",
        f"Generated: {payload['generated_at']}", "",
        "## Backtest Score", "",
        f"**Raw score ignoring the survivorship cap: {score_['raw_score_ignoring_survivorship_cap']}/100.**  ",
        f"**Rubric score after the unresolved-survivorship hard cap: {score_['final_score']}/100 — Reject.**", "",
        "| Component | Score | Max |", "|---|---:|---:|",
        f"| A. Statistical validity | {score_['A']['total']} | 30 |",
        f"| B. Risk-adjusted performance | {score_['B']['total']} | 25 |",
        f"| C. Robustness / later-data evidence | {score_['C']['total']} | 25 |",
        f"| D. Trade quality / consistency | {score_['D']['total']} | 20 |",
        f"| **Raw total** | **{score_['raw_score_ignoring_survivorship_cap']}** | **100** |", "",
        "## Executive summary", "",
        f"The frozen Trial 288 replay produced {stats['trades']} trades, {main['summary']['cagr_pct']:.2f}% net CAGR, "
        f"{robust['risk_adjusted']['sharpe']:.3f} Sharpe, {stats['profit_factor']:.3f} profit factor and "
        f"{main['summary']['max_drawdown_pct']:.2f}% MDD. It fails the 20% CAGR requirement even before applying any survivorship cap.", "",
        "The result is exploratory, not untouched OOS. A benchmark date-alignment defect was corrected before opening 2022–2026 outcomes; the old Trial 288 coefficients are invalidated, while its rule and frozen fit/calibration chronology are unchanged.", "",
        "## Performance and significance", "",
        "| Metric | Value | Status |", "|---|---:|---|",
        f"| Net CAGR | {main['summary']['cagr_pct']:.2f}% | FAIL vs 20% |",
        f"| Total return | {main['summary']['total_return_pct']:.2f}% | Weak |",
        f"| Trades | {stats['trades']} | Pass 30-trade count only |",
        f"| Sharpe / Sortino / Calmar | {robust['risk_adjusted']['sharpe']:.3f} / {robust['risk_adjusted']['sortino']:.3f} / {robust['risk_adjusted']['calmar']:.3f} | Fail |",
        f"| MDD / duration | {main['summary']['max_drawdown_pct']:.2f}% / {robust['risk']['max_drawdown_duration_days']} days | Magnitude low, recovery poor |",
        f"| PF / expectancy | {stats['profit_factor']:.3f} / {stats['expectancy_pct']:.3f}% | Fail PF |",
        f"| Win rate / payoff | {stats['win_rate']*100:.1f}% / {stats['payoff_ratio']:.3f} | Marginal |",
        f"| t-stat / PSR | {robust['significance']['t_statistic']:.3f} / {robust['significance']['psr_vs_zero']*100:.1f}% | Not significant |",
        f"| DSR probability (>=289 trials) | {payload['dsr_289']['probability']*100:.2f}% | Fail |",
        f"| Ljung–Box(10) p-value | {payload['ljung_box']['p_value']:.4f} | Serial dependence present if <0.05 |",
        f"| Positive months / quarters | {robust['stability']['positive_months']*100:.1f}% / {robust['stability']['positive_quarters']*100:.1f}% | Fail |", "",
        "## Robustness", "",
        f"Drop-top-five expectancy is {main['drop_top_5']['expectancy_pct']:.2f}% (PF {main['drop_top_5']['profit_factor']:.3f}); "
        f"drop-top-ten expectancy is {main['drop_top_10']['expectancy_pct']:.2f}% (PF {main['drop_top_10']['profit_factor']:.3f}). The positive headline expectancy is outlier-dependent.", "",
        f"Block-bootstrap CAGR 5th/median/95th percentiles are {robust['block_bootstrap']['cagr']['p05']*100:.2f}% / "
        f"{robust['block_bootstrap']['cagr']['median']*100:.2f}% / {robust['block_bootstrap']['cagr']['p95']*100:.2f}%. "
        f"Trade-bootstrap probability of nonpositive expectancy is {payload['trade_bootstrap']['expectancy_pct']['probability_nonpositive']*100:.1f}%.", "",
        "### Cost stress", "", "| Costs | Trades | CAGR | PF | MDD |", "|---|---:|---:|---:|---:|",
    ]
    for row in costs:
        lines.append(f"| {row['cost_multiplier']}x | {row['trades']} | {row['cagr_pct']:.2f}% | {row['profit_factor']:.3f} | {row['max_drawdown_pct']:.2f}% |")
    lines += ["", "### Chronological folds", "", "| Fold | CAGR | Sharpe | MDD | Positive months |", "|---|---:|---:|---:|---:|"]
    for row in folds:
        lines.append(f"| {row['start']}…{row['end']} | {row['cagr_pct']:.2f}% | {row['sharpe']:.3f} | {row['max_drawdown_pct']:.2f}% | {row['positive_months_pct']:.1f}% |")
    lines += [
        "", f"Across all prespecified neighbouring threshold cells, CAGR ranges from {min(row['cagr_pct'] for row in sensitivity):.2f}% to "
        f"{max(row['cagr_pct'] for row in sensitivity):.2f}%; every cell has negative drop-top-five expectancy. Parameter sensitivity is saved separately and is diagnostic only; no neighbouring cell replaces the frozen p85/p50 primary result.", "",
        "## Bias assessment", "",
        "| Bias | Status | Evidence |", "|---|---|---|",
        "| Lookahead | Absent after correction | Historical SPY is date-aligned at or before the stock as-of date; regression-tested. Signal date precedes every fill. |",
        "| Survivorship | Present / unresolved | Existing PIT reconstruction has 91.31% member-day coverage, not complete delisted coverage. |",
        "| Data snooping | Present as multiplicity risk | This is a later-data replay of a selected candidate after at least 288 earlier trials; DSR fails. |",
        "| Costs | Included and stressed | 5 bps commission + 5 bps slippage per side at baseline; 2x/5x/10x reported. |",
        "| Asset / leverage | Absent | Individual stocks only, no SPY trades and no leverage or sizing changes. |", "",
        "## Verdict", "",
        f"**{score_['raw_score_ignoring_survivorship_cap']}/100 before the requested cap waiver; {score_['final_score']}/100 under the rubric. Reject.** "
        "The later existing data does not rescue Trial 288: net CAGR is 0.05%, statistical confidence is absent, and removing the largest winners turns expectancy negative. The original goal is not complete.", "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("detector_json")
    parser.add_argument("replay_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--membership-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    detector = json.loads(Path(args.detector_json).read_text())
    replay = json.loads(Path(args.replay_json).read_text())
    detections = detector.get("detections_by_ticker") or {}
    membership = load_membership(args.membership_csv)
    client = CSVClient(args.price_csv)
    prices_all = {
        row["symbol"]: list(reversed(client.get_historical_prices(
            row["symbol"], days=100_000,
        )["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]
    }
    periods = replay["periods"]
    fit_dets, _ = filter_detections(detections, membership, *periods["fit"])
    calibration_dets, _ = filter_detections(detections, membership, *periods["calibration"])
    holdout_dets, _ = filter_detections(detections, membership, *periods["holdout"])
    fit_rows = build_rows(
        fit_dets, slice_prices(prices_all, periods["fit"][0], periods["fit_price_end"]),
        with_labels=True, label_mode="forward20",
    )
    if len(fit_rows) != replay["model"]["fit_rows"]:
        raise SystemExit("fit-row parity failed")
    calibration_rows = build_rows(
        calibration_dets,
        slice_prices(prices_all, periods["calibration"][0], periods["calibration_price_end"]),
        with_labels=False,
    )
    holdout_prices = slice_prices(prices_all, *periods["holdout"])
    holdout_rows = build_rows(holdout_dets, holdout_prices, with_labels=False)
    model = replay["model"]
    main_signals = signals_with_decay(
        holdout_rows, model,
        replay["calibration"]["entry_threshold"],
        replay["calibration"]["exit_threshold"],
    )
    if len(main_signals) != replay["internal_holdout"]["selected_signals"]:
        raise SystemExit("signal parity failed")
    main = run_cell(main_signals, holdout_prices)
    expected = replay["internal_holdout"]["cell"]["summary"]
    if main["summary"]["trades"] != expected["trades"] or abs(main["summary"]["end_value"] - expected["end_value"]) > .01:
        raise SystemExit("portfolio parity failed")

    cost_rows = []
    for multiplier in (1, 2, 5, 10):
        cell = run_cell(main_signals, holdout_prices, multiplier)
        cost_rows.append({
            "cost_multiplier": multiplier,
            "trades": cell["trade_stats"]["trades"],
            "cagr_pct": cell["summary"]["cagr_pct"],
            "total_return_pct": cell["summary"]["total_return_pct"],
            "profit_factor": cell["trade_stats"]["profit_factor"],
            "expectancy_pct": cell["trade_stats"]["expectancy_pct"],
            "max_drawdown_pct": cell["summary"]["max_drawdown_pct"],
        })

    sensitivity_rows = []
    cells = [
        *(('entry_percentile', value, value, 50) for value in (80, 82.5, 85, 87.5, 90)),
        *(('exit_percentile', value, 85, value) for value in (40, 45, 55, 60)),
    ]
    for dimension, value, entry_percentile, exit_percentile in cells:
        entry_threshold = threshold_from_rows(calibration_rows, model, entry_percentile)
        exit_threshold = threshold_from_rows(calibration_rows, model, exit_percentile)
        signals = signals_with_decay(holdout_rows, model, entry_threshold, exit_threshold)
        cell = run_cell(signals, holdout_prices)
        sensitivity_rows.append({
            "dimension": dimension,
            "value": value,
            "entry_percentile": entry_percentile,
            "exit_percentile": exit_percentile,
            "signals": len(signals),
            "trades": cell["trade_stats"]["trades"],
            "cagr_pct": cell["summary"]["cagr_pct"],
            "sharpe": sharpe([float(row["portfolio_return"]) for row in cell["equity_curve"]]),
            "profit_factor": cell["trade_stats"]["profit_factor"],
            "drop_top_5_expectancy_pct": cell["drop_top_5"]["expectancy_pct"],
            "max_drawdown_pct": cell["summary"]["max_drawdown_pct"],
        })

    folds = [
        period_metrics(main["equity_curve"], "2022-01-01", "2023-12-31"),
        period_metrics(main["equity_curve"], "2024-01-01", "2026-03-31"),
    ]
    returns = [float(row["portfolio_return"]) for row in main["equity_curve"]]
    benchmark_total = math.prod(1 + float(row["spy_return"]) for row in main["equity_curve"]) - 1
    matched_total = math.prod(1 + float(row["exposure_matched_spy_return"]) for row in main["equity_curve"]) - 1
    trade_boot = trade_bootstrap(main["trades"])
    dsr_289 = deflated_sharpe(returns, 289)
    score_payload = score(replay, sensitivity_rows)
    causality = {
        "all_signal_before_fill": all(
            trade["signal_date"] < trade["entry_date"] for trade in main["trades"]
        ),
        "all_signal_members": all(
            is_member(membership, trade["symbol"], trade["signal_date"])
            for trade in main["trades"]
        ),
        "all_fill_members": all(
            is_member(membership, trade["symbol"], trade["entry_date"])
            for trade in main["trades"]
        ),
        "spy_trades": sum(trade["symbol"] == "SPY" for trade in main["trades"]),
    }
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "classification": "exploratory_nonqualifying",
        "inputs": {
            "detector_json": args.detector_json,
            "detector_sha256": sha256(args.detector_json),
            "replay_json": args.replay_json,
            "replay_sha256": sha256(args.replay_json),
            "price_csv": args.price_csv,
            "price_sha256": sha256(args.price_csv),
        },
        "primary": replay["internal_holdout"]["cell"],
        "cost_stress": cost_rows,
        "parameter_sensitivity": sensitivity_rows,
        "folds": folds,
        "trade_bootstrap": trade_boot,
        "dsr_289": dsr_289,
        "ljung_box": ljung_box(returns),
        "effective_sample_size": effective_sample_size(returns)[0],
        "psr_recomputed": probabilistic_sharpe(returns),
        "benchmark": {
            "spy_total_return_pct": benchmark_total * 100,
            "exposure_matched_spy_total_return_pct": matched_total * 100,
        },
        "causality": causality,
        "score": score_payload,
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "verification_metrics.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    pd.DataFrame(cost_rows).to_csv(out / "cost_stress.csv", index=False)
    pd.DataFrame(sensitivity_rows).to_csv(out / "parameter_sensitivity.csv", index=False)
    pd.DataFrame(folds).to_csv(out / "folds.csv", index=False)
    (out / "verification_report.md").write_text(markdown(payload))
    print(json.dumps({
        "primary": replay["internal_holdout"]["cell"]["summary"],
        "score": score_payload,
        "cost_stress": cost_rows,
        "folds": folds,
        "causality": causality,
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
