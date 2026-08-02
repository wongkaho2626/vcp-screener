#!/usr/bin/env python3
"""Trial 505-518 positive stock/SPY relative-divergence confirmation gate."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from breadth_regime import DEFAULT_BREADTH_CSV, breadth_on_date, load_breadth
from cross_sectional_leadership_discovery import discovery_backtest_score
from csv_client import CSVClient
from membership import DEFAULT_MEMBERSHIP_CSV, is_member, load_membership
from pivot_retest_experiment import (
    filter_detections,
    slice_prices,
    trade_stats,
    trim_stats,
)
from portfolio_backtest import Config, _candidate_signals, run_portfolio
from portfolio_robustness import analyze
from trade_simulator import _bootstrap_ci, _t_stat

PRIMARY_LOOKBACK = 20
LOOKBACK_SENSITIVITY = (5, 10, 40, 60)
THRESHOLD_SENSITIVITY = (2.0, 5.0)
TRIALS_BEFORE = 504
TRIALS_AFTER = 518
DENSITY_MIN = 30
PERIODS = {
    "train": ("2016-07-01", "2018-06-30", "2018-12-31"),
    "validation": ("2019-01-01", "2021-12-31", "2022-03-31"),
    "best_available_oos": ("2022-01-01", "2026-03-31", "2026-06-30"),
}


def _adjusted_close(bar: dict) -> float:
    """Prefer adjusted close and fall back to the repository close field."""
    try:
        value = float(bar.get("adjClose") or bar.get("close") or 0)
    except (TypeError, ValueError):
        return 0.0
    return value if math.isfinite(value) and value > 0 else 0.0


def _eligible_prices(bars: list[dict], as_of_date: str) -> dict[str, float]:
    """Return valid dated closes no later than as-of without mutating input."""
    eligible: dict[str, float] = {}
    for bar in sorted(bars, key=lambda row: str(row.get("date") or "")):
        date = str(bar.get("date") or "")
        price = _adjusted_close(bar)
        if date and date <= as_of_date and price > 0:
            eligible[date] = price
    return eligible


def calculate_relative_divergence(
    stock_bars: list[dict],
    spy_bars: list[dict],
    as_of_date: str,
    lookback: int = PRIMARY_LOOKBACK,
    threshold_pct: float = 0.0,
) -> dict | None:
    """Calculate a strict stock-positive/common-date stock-minus-SPY return.

    Both return legs use the same two actual trading dates. The end observation
    is the latest common valid date no later than ``as_of_date`` and the start
    is exactly ``lookback`` common observations earlier.
    """
    if lookback <= 0:
        raise ValueError("lookback must be positive")
    if threshold_pct < 0:
        raise ValueError("divergence threshold cannot be negative")
    stock = _eligible_prices(stock_bars, as_of_date)
    spy = _eligible_prices(spy_bars, as_of_date)
    common_dates = sorted(set(stock).intersection(spy))
    if len(common_dates) <= lookback:
        return None
    end_date = common_dates[-1]
    start_date = common_dates[-1 - lookback]
    stock_return = stock[end_date] / stock[start_date] - 1
    spy_return = spy[end_date] / spy[start_date] - 1
    divergence = stock_return - spy_return
    threshold = threshold_pct / 100
    clears_threshold = (
        divergence > threshold
        and not math.isclose(divergence, threshold, rel_tol=0, abs_tol=1e-12)
    )
    return {
        "lookback": lookback,
        "stock_return_pct": stock_return * 100,
        "spy_return_pct": spy_return * 100,
        "relative_divergence_pct": divergence * 100,
        "positive_divergence": bool(stock_return > 0 and clears_threshold),
        "divergence_signal_date": end_date,
        "lookback_start_date": start_date,
        "threshold_pct": threshold_pct,
    }


def _missing_reason(stock_bars: list[dict], spy_bars: list[dict],
                    as_of_date: str, lookback: int) -> str:
    stock = _eligible_prices(stock_bars, as_of_date)
    spy = _eligible_prices(spy_bars, as_of_date)
    if len(stock) <= lookback:
        return "insufficient_ticker_history"
    if len(spy) <= lookback:
        return "insufficient_spy_history"
    return "insufficient_common_history"


def annotate_signals(
    signals: list[dict], prices: dict[str, list[dict]], *,
    lookback: int = PRIMARY_LOOKBACK, threshold_pct: float = 0.0,
) -> tuple[list[dict], dict[str, int]]:
    """Attach immutable divergence fields to every otherwise eligible order."""
    spy = prices.get("SPY") or []
    counts: dict[str, int] = defaultdict(int)
    annotated = []
    for signal in signals:
        result = calculate_relative_divergence(
            prices.get(signal["symbol"]) or [], spy, signal["signal_date"],
            lookback=lookback, threshold_pct=threshold_pct,
        )
        row = dict(signal)
        row["rs_divergence_lookback"] = lookback
        if result is None:
            reason = _missing_reason(
                prices.get(signal["symbol"]) or [], spy,
                signal["signal_date"], lookback)
            counts[reason] += 1
            row.update({
                "stock_lookback_return_pct": None,
                "spy_lookback_return_pct": None,
                "relative_divergence_pct": None,
                "positive_rs_divergence": None,
                "divergence_signal_date": None,
                "divergence_missing_reason": reason,
            })
        else:
            counts["available"] += 1
            counts["positive"] += int(result["positive_divergence"])
            counts["negative_control"] += int(not result["positive_divergence"])
            row.update({
                "stock_lookback_return_pct": result["stock_return_pct"],
                "spy_lookback_return_pct": result["spy_return_pct"],
                "relative_divergence_pct": result["relative_divergence_pct"],
                "positive_rs_divergence": result["positive_divergence"],
                "divergence_signal_date": result["divergence_signal_date"],
                "divergence_missing_reason": None,
            })
        annotated.append(row)
    return annotated, dict(sorted(counts.items()))


def select_signals(signals: list[dict], mode: str) -> list[dict]:
    """Return a copied all/pass/fail signal set; missing is in neither cohort."""
    if mode == "all":
        return [dict(signal) for signal in signals]
    if mode == "positive":
        return [dict(signal) for signal in signals
                if signal.get("positive_rs_divergence") is True]
    if mode == "negative_control":
        return [dict(signal) for signal in signals
                if signal.get("positive_rs_divergence") is False]
    raise ValueError(f"unknown signal mode: {mode}")


def build_baseline_signals(
    detections: dict, prices: dict[str, list[dict]], membership: dict,
    start: str, end: str,
) -> tuple[list[dict], dict[str, int]]:
    """Build frozen pullback signals and enforce PIT on detection/signal/fill."""
    selected, detection_drops = filter_detections(
        detections, membership, start, end)
    candidates = _candidate_signals(selected, prices, Config(), entry_rule="pullback")
    date_candidates = [signal for signal in candidates
                       if start <= signal["signal_date"] <= end]
    signal_drops = 0
    fill_drops = 0
    kept = []
    for signal in date_candidates:
        if not is_member(membership, signal["symbol"], signal["signal_date"]):
            signal_drops += 1
            continue
        if not is_member(membership, signal["symbol"], signal["fill_date"]):
            fill_drops += 1
            continue
        kept.append(signal)
    return kept, {
        "detection_date": detection_drops,
        "signal_date": signal_drops,
        "fill_date": fill_drops,
        "outside_signal_partition": len(candidates) - len(date_candidates),
    }


def _signal_key(row: dict) -> tuple[str, str, str]:
    return (row["symbol"], row["signal_date"], row.get("fill_date") or row.get("entry_date"))


def _exact_spy_return(spy_bars: list[dict], start: str, end: str) -> float | None:
    prices = {bar["date"]: _adjusted_close(bar) for bar in spy_bars}
    if prices.get(start, 0) <= 0 or prices.get(end, 0) <= 0:
        return None
    return (prices[end] / prices[start] - 1) * 100


def enrich_trades(
    trades: list[dict], signals: list[dict], prices: dict[str, list[dict]],
    cfg: Config,
) -> list[dict]:
    """Attach signal state plus gross/net and exact-date SPY trade returns."""
    signal_map = {_signal_key(signal): signal for signal in signals}
    index = {symbol: {bar["date"]: pos for pos, bar in enumerate(bars)}
             for symbol, bars in prices.items()}
    cost = (cfg.commission_bps + cfg.slippage_bps) / 10_000
    enriched = []
    for trade in trades:
        signal = signal_map.get((trade["symbol"], trade["signal_date"], trade["entry_date"])) or {}
        raw_entry = float(trade["entry_price"]) / (1 + cost)
        raw_exit = float(trade["exit_price"]) / (1 - cost) if cost < 1 else 0.0
        gross = (raw_exit / raw_entry - 1) * 100 if raw_entry > 0 else None
        spy_return = _exact_spy_return(
            prices.get("SPY") or [], trade["entry_date"], trade["exit_date"])
        positions = index.get(trade["symbol"]) or {}
        entry_pos = positions.get(trade["entry_date"])
        exit_pos = positions.get(trade["exit_date"])
        hold = exit_pos - entry_pos if entry_pos is not None and exit_pos is not None else None
        row = dict(trade)
        for key in (
            "rs_divergence_lookback", "stock_lookback_return_pct",
            "spy_lookback_return_pct", "relative_divergence_pct",
            "positive_rs_divergence", "divergence_signal_date",
            "divergence_missing_reason",
            "ma50_period", "ma50_slope_sessions", "signal_close",
            "ma50_value", "ma50_20_sessions_ago", "ma50_slope_pct",
            "positive_ma50_slope", "ma50_signal_date",
            "ma50_missing_reason",
            "relative_ma50_period", "relative_ma50_slope_sessions",
            "stock_signal_close", "stock_ma50_value",
            "stock_ma50_20_sessions_ago", "spy_ma50_value",
            "spy_ma50_20_sessions_ago", "stock_ma50_slope_pct",
            "spy_ma50_slope_pct", "relative_ma50_slope_pct",
            "positive_relative_ma50_slope", "relative_ma50_signal_date",
            "relative_ma50_missing_reason",
            "relative_ma_period", "relative_ma_slope_sessions",
            "stock_ma_value", "stock_ma_20_sessions_ago",
            "spy_ma_value", "spy_ma_20_sessions_ago",
            "stock_ma_slope_pct", "spy_ma_slope_pct",
            "relative_ma_slope_pct", "positive_relative_ma_slope",
            "relative_ma_signal_date", "relative_ma_missing_reason",
        ):
            row[key] = signal.get(key)
        row.update({
            "gross_return_pct": gross,
            "net_return_pct": float(trade["net_return_pct"]),
            "estimated_cost_drag_pct": (gross - float(trade["net_return_pct"]))
            if gross is not None else None,
            "matched_spy_return_pct": spy_return,
            "gross_excess_vs_spy_pct": gross - spy_return
            if gross is not None and spy_return is not None else None,
            "net_excess_vs_spy_pct": float(trade["net_return_pct"]) - spy_return
            if spy_return is not None else None,
            "hold_sessions": hold,
        })
        enriched.append(row)
    return enriched


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _profit_factor(values: list[float]) -> float | None:
    gains = sum(value for value in values if value > 0)
    losses = -sum(value for value in values if value < 0)
    return gains / losses if losses > 0 else None


def _clustered_se(values: list[float], clusters: list[str]) -> float | None:
    """One-way entry-month cluster-robust standard error of the mean."""
    if len(values) < 2 or len(values) != len(clusters):
        return None
    groups: dict[str, list[float]] = defaultdict(list)
    for value, cluster in zip(values, clusters):
        groups[cluster].append(value)
    if len(groups) < 2:
        return None
    mean = statistics.fmean(values)
    summed = sum(sum(value - mean for value in group) ** 2
                 for group in groups.values())
    correction = len(groups) / (len(groups) - 1)
    return math.sqrt(correction * summed / (len(values) ** 2))


def _winsorized_mean(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    low = ordered[int(.05 * (len(ordered) - 1))]
    high = ordered[int(.95 * (len(ordered) - 1))]
    return statistics.fmean(min(high, max(low, value)) for value in values)


def _average_ranks(values: list[float]) -> list[float]:
    """Return deterministic average ranks without requiring SciPy."""
    ranks = [0.0] * len(values)
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        average_rank = (index + 1 + end) / 2
        for original_index, _ in ordered[index:end]:
            ranks[original_index] = average_rank
        index = end
    return ranks


def _spearman_correlation(left: list[float], right: list[float]) -> float | None:
    """Calculate a tie-aware Spearman correlation using only the standard library."""
    if len(left) != len(right) or len(left) < 2:
        return None
    left_ranks = _average_ranks(left)
    right_ranks = _average_ranks(right)
    left_mean = statistics.fmean(left_ranks)
    right_mean = statistics.fmean(right_ranks)
    covariance = sum((x - left_mean) * (y - right_mean)
                     for x, y in zip(left_ranks, right_ranks))
    left_scale = math.sqrt(sum((x - left_mean) ** 2 for x in left_ranks))
    right_scale = math.sqrt(sum((y - right_mean) ** 2 for y in right_ranks))
    if left_scale == 0 or right_scale == 0:
        return None
    return covariance / (left_scale * right_scale)


def trade_metrics(trades: list[dict]) -> dict:
    """Rich trade statistics compatible with repository percentage returns."""
    gross = [float(row["gross_return_pct"]) for row in trades
             if row.get("gross_return_pct") is not None]
    net = [float(row["net_return_pct"]) for row in trades]
    excess = [float(row["net_excess_vs_spy_pct"]) for row in trades
              if row.get("net_excess_vs_spy_pct") is not None]
    spy = [float(row["matched_spy_return_pct"]) for row in trades
           if row.get("matched_spy_return_pct") is not None]
    months = [str(row["entry_date"])[:7] for row in trades
              if row.get("net_excess_vs_spy_pct") is not None]
    se = statistics.stdev(excess) / math.sqrt(len(excess)) if len(excess) >= 2 else None
    cluster_se = _clustered_se(excess, months)
    top_trimmed = sorted(net, reverse=True)[5:]
    bottom_trimmed = sorted(net)[5:]
    return {
        "trades": len(trades),
        "mean_gross_return_pct": _mean(gross),
        "median_gross_return_pct": statistics.median(gross) if gross else None,
        "gross_win_rate": sum(value > 0 for value in gross) / len(gross) if gross else None,
        "gross_profit_factor": _profit_factor(gross),
        "mean_net_return_pct": _mean(net),
        "median_net_return_pct": statistics.median(net) if net else None,
        "net_win_rate": sum(value > 0 for value in net) / len(net) if net else None,
        "net_profit_factor": _profit_factor(net),
        "worst_net_trade_pct": min(net) if net else None,
        "mean_matched_spy_return_pct": _mean(spy),
        "mean_net_excess_pct": _mean(excess),
        "median_net_excess_pct": statistics.median(excess) if excess else None,
        "excess_win_rate": sum(value > 0 for value in excess) / len(excess) if excess else None,
        "excess_t_statistic": _t_stat(excess),
        "excess_standard_error_pct": se,
        "entry_month_clustered_se_pct": cluster_se,
        "entry_month_clustered_t": (_mean(excess) / cluster_se
                                      if excess and cluster_se not in (None, 0) else None),
        "excess_bootstrap_95ci_pct": _bootstrap_ci(excess),
        "average_holding_sessions": _mean([
            float(row["hold_sessions"]) for row in trades
            if row.get("hold_sessions") is not None]),
        "estimated_mean_cost_drag_pct": _mean([
            float(row["estimated_cost_drag_pct"]) for row in trades
            if row.get("estimated_cost_drag_pct") is not None]),
        "drop_best_five_net_expectancy_pct": _mean(top_trimmed),
        "drop_worst_five_net_expectancy_pct": _mean(bottom_trimmed),
        "winsorized_net_expectancy_pct": _winsorized_mean(net),
    }


def _annual_rows(curve: list[dict]) -> dict[str, dict]:
    output = {}
    years = sorted({row["date"][:4] for row in curve})
    for year in years:
        rows = [row for row in curve if row["date"].startswith(year)]
        output[year] = {
            "portfolio_return_pct": (math.prod(1 + float(row["portfolio_return"])
                                                for row in rows) - 1) * 100,
            "spy_return_pct": (math.prod(1 + float(row["spy_return"])
                                          for row in rows) - 1) * 100,
            "exposure_matched_excess_return_pct": (
                math.prod(1 + float(row["exposure_matched_excess_return"])
                          for row in rows) - 1) * 100,
            "average_exposure_pct": _mean([
                float(row["gross_exposure_pct"]) for row in rows]),
        }
    return output


def portfolio_metrics(portfolio: dict, enriched: list[dict], cfg: Config,
                      iterations: int) -> tuple[dict, dict]:
    curve = portfolio["equity_curve"]
    returns = [float(row["portfolio_return"]) for row in curve]
    excess = [float(row["exposure_matched_excess_return"]) for row in curve]
    dates = pd.Series([row["date"] for row in curve])
    robust = analyze(dates, returns, TRIALS_AFTER, iterations, 10, 20260802, .70)
    excess_robust = analyze(
        dates, excess, TRIALS_AFTER, iterations, 10, 20260803, .70)
    average_equity = _mean([float(row["equity"]) for row in curve]) or cfg.initial_cash
    traded_notional = sum(
        float(row["shares"]) * (float(row["entry_price"]) + float(row["exit_price"]))
        for row in enriched)
    cost_rate = (cfg.commission_bps + cfg.slippage_bps) / 10_000
    estimated_costs = sum(
        float(row["shares"]) * (
            float(row["entry_price"]) / (1 + cost_rate) * cost_rate
            + float(row["exit_price"]) / (1 - cost_rate) * cost_rate)
        for row in enriched) if cost_rate < 1 else None
    metrics = {
        "summary": portfolio["summary"],
        "annual_volatility_pct": robust["performance"]["annual_volatility"] * 100,
        "sharpe": robust["risk_adjusted"]["sharpe"],
        "sortino": robust["risk_adjusted"]["sortino"],
        "calmar": robust["risk_adjusted"]["calmar"],
        "average_exposure_pct": _mean([
            float(row["gross_exposure_pct"]) for row in curve]),
        "average_positions": _mean([float(row["positions"]) for row in curve]),
        "portfolio_utilization": _mean([
            float(row["positions"]) / cfg.max_positions for row in curve]),
        "turnover_multiple": traded_notional / average_equity,
        "estimated_transaction_costs": estimated_costs,
        "exposure_matched_excess_total_return_pct": (
            excess_robust["performance"]["total_return"] * 100),
        "exposure_matched_excess_cagr_pct": (
            excess_robust["performance"]["cagr"] * 100),
        "exposure_matched_excess_sharpe": excess_robust["risk_adjusted"]["sharpe"],
        "calendar_years": _annual_rows(curve),
        "trade_metrics": trade_metrics(enriched),
    }
    score_cell = {
        "summary": portfolio["summary"],
        "trade_stats": trade_stats(portfolio["trades"]),
        "drop_top_5": trim_stats(portfolio["trades"], 5),
        "drop_top_10": trim_stats(portfolio["trades"], 10),
        "robustness": robust,
    }
    return metrics, score_cell


def evaluate_signals(signals: list[dict], prices: dict[str, list[dict]], *,
                     cost_multiplier: int = 1, iterations: int = 1000) -> dict:
    cfg = Config(commission_bps=5.0 * cost_multiplier,
                 slippage_bps=5.0 * cost_multiplier)
    with patch("portfolio_backtest._candidate_signals", return_value=signals):
        portfolio = run_portfolio({}, prices, cfg, entry_rule="pullback",
                                  exit_rule="baseline")
    enriched = enrich_trades(portfolio["trades"], signals, prices, cfg)
    metrics, score_cell = portfolio_metrics(
        portfolio, enriched, cfg, iterations)
    return {"metrics": metrics, "score_cell": score_cell,
            "signals": signals, "trades": enriched,
            "equity_curve": portfolio["equity_curve"]}


def _comparison(baseline: dict, primary: dict, negative: dict) -> dict:
    bm = baseline["metrics"]
    pm = primary["metrics"]
    nm = negative["metrics"]
    return {
        "retained_signal_pct": (
            100 * len(primary["signals"]) / len(baseline["signals"])
            if baseline["signals"] else None),
        "retained_trade_pct": (
            100 * len(primary["trades"]) / len(baseline["trades"])
            if baseline["trades"] else None),
        "net_cagr_lift_pct_points": (
            pm["summary"]["cagr_pct"] - bm["summary"]["cagr_pct"]),
        "exposure_matched_excess_cagr_lift_pct_points": (
            pm["exposure_matched_excess_cagr_pct"]
            - bm["exposure_matched_excess_cagr_pct"]),
        "qualifying_minus_rejected_mean_excess_pct_points": (
            (pm["trade_metrics"]["mean_net_excess_pct"] or 0)
            - (nm["trade_metrics"]["mean_net_excess_pct"] or 0)),
        "mdd_change_pct_points": (
            pm["summary"]["max_drawdown_pct"]
            - bm["summary"]["max_drawdown_pct"]),
    }


def _train_gate(primary: dict, comparison: dict) -> dict:
    checks = {
        "primary_executed_trades>=30": len(primary["trades"]) >= 30,
        "net_cagr_lift>0": comparison["net_cagr_lift_pct_points"] > 0,
        "exposure_matched_excess_cagr_lift>0": (
            comparison["exposure_matched_excess_cagr_lift_pct_points"] > 0),
        "qualifying_minus_rejected_mean_excess>0": (
            comparison["qualifying_minus_rejected_mean_excess_pct_points"] > 0),
        "drop_best_five_expectancy>0": (
            primary["metrics"]["trade_metrics"][
                "drop_best_five_net_expectancy_pct"] or 0) > 0,
    }
    return {"passed": all(checks.values()), "checks": checks}


def _validation_gate(primary: dict, comparison: dict) -> dict:
    checks = {
        "primary_executed_trades>=30": len(primary["trades"]) >= 30,
        "net_cagr_lift>0": comparison["net_cagr_lift_pct_points"] > 0,
        "exposure_matched_excess_cagr_lift>0": (
            comparison["exposure_matched_excess_cagr_lift_pct_points"] > 0),
        "qualifying_minus_rejected_mean_excess>0": (
            comparison["qualifying_minus_rejected_mean_excess_pct_points"] > 0),
        "mdd_not_worse_by_more_than_2pp": comparison["mdd_change_pct_points"] >= -2,
    }
    return {"passed": all(checks.values()), "checks": checks}


def _quartiles(trades: list[dict]) -> list[dict]:
    available = sorted(
        [trade for trade in trades if trade.get("relative_divergence_pct") is not None],
        key=lambda row: float(row["relative_divergence_pct"]))
    output = []
    for quartile in range(4):
        batch = [row for index, row in enumerate(available)
                 if min(3, index * 4 // max(1, len(available))) == quartile]
        values = [float(row["relative_divergence_pct"]) for row in batch]
        output.append({"quartile": quartile + 1,
                       "min_divergence_pct": min(values) if values else None,
                       "max_divergence_pct": max(values) if values else None,
                       "metrics": trade_metrics(batch)})
    return output


def _regime_rows(trades: list[dict], prices: dict[str, list[dict]],
                 breadth_series: list[tuple[str, float]]) -> list[dict]:
    spy = sorted(prices.get("SPY") or [], key=lambda row: row["date"])
    spy_index = {row["date"]: index for index, row in enumerate(spy)}
    vol_by_trade = []
    states = []
    for trade in trades:
        date = trade.get("divergence_signal_date") or trade["signal_date"]
        index = spy_index.get(date)
        above_200 = None
        vol = None
        if index is not None and index >= 199:
            closes = [_adjusted_close(row) for row in spy[index - 199:index + 1]]
            above_200 = closes[-1] > statistics.fmean(closes)
        if index is not None and index >= 20:
            closes = [_adjusted_close(row) for row in spy[index - 20:index + 1]]
            returns = [closes[pos] / closes[pos - 1] - 1
                       for pos in range(1, len(closes))]
            vol = statistics.stdev(returns) * math.sqrt(252) if len(returns) >= 2 else None
        vol_by_trade.append(vol)
        states.append({"trade": trade, "above_200": above_200, "vol": vol,
                       "breadth": breadth_on_date(breadth_series, date)
                       if breadth_series else None})
    valid_vol = [value for value in vol_by_trade if value is not None]
    median_vol = statistics.median(valid_vol) if valid_vol else None
    definitions = {
        "spy_above_sma200": lambda row: row["above_200"] is True,
        "spy_below_sma200": lambda row: row["above_200"] is False,
        "high_volatility": lambda row: (row["vol"] is not None
                                         and median_vol is not None
                                         and row["vol"] >= median_vol),
        "low_volatility": lambda row: (row["vol"] is not None
                                        and median_vol is not None
                                        and row["vol"] < median_vol),
        "breadth_ge_50": lambda row: row["breadth"] is not None and row["breadth"] >= 50,
        "breadth_lt_50": lambda row: row["breadth"] is not None and row["breadth"] < 50,
        "edge_rank_ge_70": lambda row: float(row["trade"].get("edge_rank") or 0) >= 70,
        "edge_rank_lt_70": lambda row: float(row["trade"].get("edge_rank") or 0) < 70,
    }
    output = []
    for name, predicate in definitions.items():
        selected = [row["trade"] for row in states if predicate(row)]
        qualifying = [row for row in selected
                      if row.get("positive_rs_divergence") is True]
        rejected = [row for row in selected
                    if row.get("positive_rs_divergence") is False]
        qualifying_metrics = trade_metrics(qualifying)
        rejected_metrics = trade_metrics(rejected)
        qualifying_excess = qualifying_metrics["mean_net_excess_pct"]
        rejected_excess = rejected_metrics["mean_net_excess_pct"]
        output.append({
            "regime": name,
            "all": trade_metrics(selected),
            "qualifying": qualifying_metrics,
            "rejected": rejected_metrics,
            "qualifying_minus_rejected_mean_excess_pct_points": (
                qualifying_excess - rejected_excess
                if qualifying_excess is not None and rejected_excess is not None
                else None),
        })
    return output


def _compact_variant(result: dict) -> dict:
    return {"signals": len(result["signals"]), "trades": len(result["trades"]),
            "metrics": result["metrics"]}


def evaluate_partition(
    name: str, detections: dict, prices_all: dict[str, list[dict]], membership: dict,
    breadth_series: list[tuple[str, float]], iterations: int,
) -> tuple[dict, dict[str, dict]]:
    start, end, price_end = PERIODS[name]
    prices = slice_prices(prices_all, start, price_end)
    base_signals, membership_drops = build_baseline_signals(
        detections, prices, membership, start, end)
    primary_annotated, missing = annotate_signals(base_signals, prices)
    variant_signals = {
        "baseline": select_signals(primary_annotated, "all"),
        "primary_20d_0pp": select_signals(primary_annotated, "positive"),
        "negative_control": select_signals(primary_annotated, "negative_control"),
    }
    for lookback in LOOKBACK_SENSITIVITY:
        annotated, _ = annotate_signals(base_signals, prices, lookback=lookback)
        variant_signals[f"lookback_{lookback}d"] = select_signals(annotated, "positive")
    for threshold in THRESHOLD_SENSITIVITY:
        annotated, _ = annotate_signals(
            base_signals, prices, lookback=PRIMARY_LOOKBACK,
            threshold_pct=threshold)
        variant_signals[f"threshold_{threshold:g}pp"] = select_signals(
            annotated, "positive")

    raw = {variant: evaluate_signals(
        signals, prices, iterations=iterations)
        for variant, signals in variant_signals.items()}
    comparison = _comparison(
        raw["baseline"], raw["primary_20d_0pp"], raw["negative_control"])
    baseline_trades = raw["baseline"]["trades"]
    pass_trades = [trade for trade in baseline_trades
                   if trade.get("positive_rs_divergence") is True]
    fail_trades = [trade for trade in baseline_trades
                   if trade.get("positive_rs_divergence") is False]
    available = [trade for trade in baseline_trades
                 if trade.get("relative_divergence_pct") is not None]
    corr_rows = [trade for trade in available
                 if trade.get("net_excess_vs_spy_pct") is not None]
    spearman = _spearman_correlation(
        [float(row["relative_divergence_pct"]) for row in corr_rows],
        [float(row["net_excess_vs_spy_pct"]) for row in corr_rows],
    )
    costs = {}
    for multiplier in (2, 5, 10):
        costs[str(multiplier)] = {
            "baseline": _compact_variant(evaluate_signals(
                variant_signals["baseline"], prices,
                cost_multiplier=multiplier, iterations=max(200, iterations // 5))),
            "primary": _compact_variant(evaluate_signals(
                variant_signals["primary_20d_0pp"], prices,
                cost_multiplier=multiplier, iterations=max(200, iterations // 5))),
        }
    report = {
        "period": [start, end],
        "price_end_for_exit_bookkeeping": price_end,
        "membership_drops": membership_drops,
        "missing_history": missing,
        "variants": {name: _compact_variant(value) for name, value in raw.items()},
        "comparison": comparison,
        "baseline_trade_cohorts": {
            "qualifying": trade_metrics(pass_trades),
            "rejected": trade_metrics(fail_trades),
            "missing": len(baseline_trades) - len(pass_trades) - len(fail_trades),
        },
        "divergence_spearman_vs_future_excess": (
            float(spearman) if spearman is not None and math.isfinite(spearman) else None),
        "divergence_quartiles": _quartiles(baseline_trades),
        "regimes": _regime_rows(baseline_trades, prices, breadth_series),
        "cost_stress": costs,
    }
    return report, raw


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _score_lines(score: dict) -> list[str]:
    components = score["components"]
    return [
        f"## Backtest Score: {score['final_score']}/100 — {score['band']}", "",
        "| Component | Score | Available max |", "|---|---:|---:|",
        f"| A. Statistical validity | {components['A_statistical_validity']['score']} | 30 |",
        f"| B. Risk-adjusted performance | {components['B_risk_adjusted_performance']['score']} | 25 |",
        f"| C. Robustness computable | {components['C_robustness_computable']['score']} | 8 |",
        f"| D. Trade quality / consistency | {components['D_trade_quality_consistency']['score']} | 20 |",
        f"| Measured total | {score['measured_total']} | {score['measured_denominator']} |",
        f"| Normalized raw score | {score['reduced_denominator_normalized_raw_score']} | 100 |",
        "| Caps | unresolved survivorship → 20; no genuine untouched OOS/WFA → 55 | |",
        f"| **Final score** | **{score['final_score']}** | **100** |", "",
    ]


def render_markdown(report: dict) -> str:
    lines = [
        "# Trial 505–518 — Positive Relative-Strength Divergence Gate", "",
        f"Final verdict: **{report['verdict']}**", "",
        "> The confirmatory family failed its outcome-free 30-activation train "
        "gate (24/34). Return tables below are the separately frozen Trial 519 "
        "descriptive audit and cannot support an `IMPROVES` verdict.", "",
        f"Validation accessed: **{'YES' if report['validation_accessed'] else 'NO'}**  ",
        f"Best-available OOS accessed: **{'YES' if report['best_available_oos_accessed'] else 'NO'}**", "",
        *_score_lines(report["backtest_score"]),
        "The score is the repository analyst's capped diagnostic for the primary "
        "best-available OOS cell. It remains non-qualifying because the data has "
        "incomplete delisted coverage and no genuinely untouched OOS.", "",
        "## Every portfolio variant by chronological fold", "",
        "| Fold | Variant | Signals | Trades | Net CAGR | Sharpe | Sortino | Excess CAGR | MDD | Exposure | Mean trade excess | PF |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for partition, partition_report in report["partitions"].items():
        for name, cell in partition_report["variants"].items():
            metrics = cell["metrics"]
            trade = metrics["trade_metrics"]
            lines.append(
                f"| {partition} | {name} | {cell['signals']} | {cell['trades']} | "
                f"{metrics['summary']['cagr_pct']:.2f}% | {metrics['sharpe'] or 0:.3f} | "
                f"{metrics['sortino'] or 0:.3f} | "
                f"{metrics['exposure_matched_excess_cagr_pct']:.2f}% | "
                f"{metrics['summary']['max_drawdown_pct']:.2f}% | "
                f"{metrics['average_exposure_pct'] or 0:.1f}% | "
                f"{trade['mean_net_excess_pct'] or 0:.2f}% | "
                f"{trade['net_profit_factor'] or 0:.3f} |")

    lines += ["", "## Prespecified primary comparison by fold", "",
              "| Fold | Retained signals | CAGR lift | Exposure-matched excess CAGR lift | Pass-minus-fail mean excess | MDD change | Divergence/excess Spearman |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for partition, partition_report in report["partitions"].items():
        comparison = partition_report["comparison"]
        lines.append(
            f"| {partition} | {comparison['retained_signal_pct']:.1f}% | "
            f"{comparison['net_cagr_lift_pct_points']:.2f} pp | "
            f"{comparison['exposure_matched_excess_cagr_lift_pct_points']:.2f} pp | "
            f"{comparison['qualifying_minus_rejected_mean_excess_pct_points']:.2f} pp | "
            f"{comparison['mdd_change_pct_points']:.2f} pp | "
            f"{partition_report['divergence_spearman_vs_future_excess'] or 0:.3f} |")

    lines += ["", "## Primary trade-level evidence", "",
              "| Fold | Cohort | Trades | Mean gross | Mean net | Median net | Win rate | Mean matched excess | Excess 95% CI | Clustered t | Drop-best-5 mean |",
              "|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|"]
    for partition, partition_report in report["partitions"].items():
        cohort_cells = {
            "baseline": partition_report["variants"]["baseline"]["metrics"]["trade_metrics"],
            "qualifying": partition_report["baseline_trade_cohorts"]["qualifying"],
            "rejected": partition_report["baseline_trade_cohorts"]["rejected"],
        }
        for cohort, trade in cohort_cells.items():
            interval = trade["excess_bootstrap_95ci_pct"]
            interval_text = (f"[{interval[0]:.2f}, {interval[1]:.2f}]"
                             if interval and interval[0] is not None else "unavailable")
            lines.append(
                f"| {partition} | {cohort} | {trade['trades']} | "
                f"{trade['mean_gross_return_pct'] or 0:.2f}% | "
                f"{trade['mean_net_return_pct'] or 0:.2f}% | "
                f"{trade['median_net_return_pct'] or 0:.2f}% | "
                f"{100 * (trade['net_win_rate'] or 0):.1f}% | "
                f"{trade['mean_net_excess_pct'] or 0:.2f}% | {interval_text} | "
                f"{trade['entry_month_clustered_t'] or 0:.2f} | "
                f"{trade['drop_best_five_net_expectancy_pct'] or 0:.2f}% |")

    lines += ["", "## Primary year-by-year portfolio evidence", "",
              "| Fold | Year | Baseline return | Primary return | Baseline excess | Primary excess | Primary exposure |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for partition, partition_report in report["partitions"].items():
        baseline_years = partition_report["variants"]["baseline"]["metrics"]["calendar_years"]
        primary_years = partition_report["variants"]["primary_20d_0pp"]["metrics"]["calendar_years"]
        for year in sorted(set(baseline_years).intersection(primary_years)):
            baseline = baseline_years[year]
            primary = primary_years[year]
            lines.append(
                f"| {partition} | {year} | {baseline['portfolio_return_pct']:.2f}% | "
                f"{primary['portfolio_return_pct']:.2f}% | "
                f"{baseline['exposure_matched_excess_return_pct']:.2f}% | "
                f"{primary['exposure_matched_excess_return_pct']:.2f}% | "
                f"{primary['average_exposure_pct']:.1f}% |")

    lines += ["", "## Missing observations and PIT exclusions", "",
              "| Fold | Available divergence | Positive | Negative control | Missing | PIT detection drops | Signal-date drops | Fill-date drops |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for partition, partition_report in report["partitions"].items():
        missing = partition_report["missing_history"]
        drops = partition_report["membership_drops"]
        lines.append(
            f"| {partition} | {missing.get('available', 0)} | "
            f"{missing.get('positive', 0)} | {missing.get('negative_control', 0)} | "
            f"{sum(value for key, value in missing.items() if key not in ('available', 'positive', 'negative_control'))} | "
            f"{drops['detection_date']} | {drops['signal_date']} | {drops['fill_date']} |")

    train = report["partitions"]["train"]
    lines += ["", "## Sequential gate and robustness interpretation", "",
              f"Train gate: **{'PASS' if report['train_gate']['passed'] else 'FAIL'}**", ""]
    lines.extend(f"- {'PASS' if passed else 'FAIL'} — {name}"
                 for name, passed in report["train_gate"]["checks"].items())
    oos = report["partitions"].get("best_available_oos")
    if oos:
        primary_metrics = oos["variants"]["primary_20d_0pp"]["metrics"]
        primary = primary_metrics["trade_metrics"]
        lines += ["",
                  f"- Best-available OOS primary mean excess was {primary['mean_net_excess_pct']:.2f}% "
                  f"(bootstrap 95% CI {primary['excess_bootstrap_95ci_pct']}).",
                  f"- OOS drop-best-five net expectancy was {primary['drop_best_five_net_expectancy_pct']:.2f}%; "
                  f"winsorized expectancy was {primary['winsorized_net_expectancy_pct']:.2f}%.",
                  "- At 2×, 5× and 10× costs, both baseline and primary remained negative in OOS; the gate did not create positive economic performance.",
                  "- Divergence quartiles were not monotonic and the OOS Spearman association was weakly negative."]
        rejected = primary_metrics["summary"]["rejected"]
        lines += ["", "### Best-available OOS primary portfolio detail", "",
                  "| Total return | Annual volatility | Calmar | Average positions | Slot utilization | Turnover | Estimated costs | Capacity rejects | Cash/sector/liquidity rejects |",
                  "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
                  f"| {primary_metrics['summary']['total_return_pct']:.2f}% | "
                  f"{primary_metrics['annual_volatility_pct']:.2f}% | "
                  f"{primary_metrics['calmar'] or 0:.3f} | "
                  f"{primary_metrics['average_positions'] or 0:.2f} | "
                  f"{100 * (primary_metrics['portfolio_utilization'] or 0):.1f}% | "
                  f"{primary_metrics['turnover_multiple'] or 0:.2f}x | "
                  f"${primary_metrics['estimated_transaction_costs'] or 0:,.2f} | "
                  f"{rejected.get('duplicate_or_position_limit', 0)} | "
                  f"{rejected.get('cash_sector_or_liquidity', 0)} |"]
        lines += ["", "### Best-available OOS regime cohorts", "",
                  "| Regime | Qualifying trades | Rejected trades | Qualifying mean excess | Rejected mean excess | Difference |",
                  "|---|---:|---:|---:|---:|---:|"]
        for regime in oos["regimes"]:
            qualifying = regime["qualifying"]
            rejected = regime["rejected"]
            difference = regime[
                "qualifying_minus_rejected_mean_excess_pct_points"]
            lines.append(
                f"| {regime['regime']} | {qualifying['trades']} | "
                f"{rejected['trades']} | "
                f"{qualifying['mean_net_excess_pct'] or 0:.2f}% | "
                f"{rejected['mean_net_excess_pct'] or 0:.2f}% | "
                f"{difference or 0:.2f} pp |")
    lines += ["", "## Interpretation", "",
              report["interpretation"], "",
              "The 5/10/40/60-session and 2/5pp cells are sensitivity/multiple comparisons. They cannot replace the frozen 20-session, zero-threshold primary result. Ranking was not run because it cannot be separated from fixed Edge Rank sizing in the current engine.", "",
              "The apparent portfolio lift in validation and best-available OOS came with lower exposure. In best-available OOS, qualifying baseline trades had worse matched-window excess than rejected trades, while both baseline and challenger lost money. That mixed evidence is neither reliable stock-selection alpha nor economically successful.", "",
              "## Reproduction", "", "```bash", report["reproduction_command"], "```", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--breadth-csv", default=DEFAULT_BREADTH_CSV)
    parser.add_argument("--output-dir", default="backtests/relative_divergence_v2/results")
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument(
        "--descriptive-full-audit", action="store_true",
        help="open all partitions descriptively after a failed density gate",
    )
    args = parser.parse_args()
    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/real-SPY gate failed")
    client = CSVClient(args.price_csv)
    if client.synthetic_benchmark:
        raise SystemExit("real SPY is required; synthetic benchmark rejected")
    prices_all = {row["symbol"]: list(reversed(client.get_historical_prices(
        row["symbol"], days=100_000)["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]}
    detections = json.loads(Path(args.backtest_json).read_text())["detections_by_ticker"]
    membership = load_membership(args.membership_csv)
    breadth_series = load_breadth(args.breadth_csv) if Path(args.breadth_csv).exists() else []

    # Outcome-free activation count precedes every portfolio-return call.
    train_start, train_end, train_price_end = PERIODS["train"]
    train_prices = slice_prices(prices_all, train_start, train_price_end)
    train_base, train_membership_drops = build_baseline_signals(
        detections, train_prices, membership, train_start, train_end)
    train_annotated, density_missing = annotate_signals(train_base, train_prices)
    activations = sum(row.get("positive_rs_divergence") is True
                      for row in train_annotated)
    density = {"baseline_signals": len(train_base),
               "primary_activations": activations,
               "minimum": DENSITY_MIN,
               "passed": activations >= DENSITY_MIN,
               "missing_history": density_missing,
               "membership_drops": train_membership_drops}
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    reproduction = (
        f".venv/bin/python scripts/relative_divergence_experiment.py {args.backtest_json} "
        f"--price-csv {args.price_csv} --membership-csv {args.membership_csv} "
        f"--coverage-json {args.coverage_json} --breadth-csv {args.breadth_csv} "
        f"--output-dir {args.output_dir} --iterations {args.iterations}"
        + (" --descriptive-full-audit" if args.descriptive_full_audit else ""))
    if not density["passed"] and not args.descriptive_full_audit:
        report = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "family_spec": "backtests/relative_divergence_v2/frozen_spec.md",
            "classification": "outcome_free_density_only",
            "trials_before": TRIALS_BEFORE, "trials_after": TRIALS_AFTER,
            "return_evaluation_accessed": False,
            "validation_accessed": False, "best_available_oos_accessed": False,
            "density": density, "verdict": "INCONCLUSIVE",
            "reproduction_command": reproduction,
        }
        json_path = output / f"relative_divergence_{stamp}.json"
        md_path = output / f"relative_divergence_{stamp}.md"
        json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        md_path.write_text(
            "# Trial 505–518 — Relative-Divergence Density Audit\n\n"
            f"Primary activations: **{activations}/{len(train_base)}**; required "
            f"at least {DENSITY_MIN}. **FAIL**. No returns or later partition accessed.\n")
        print(json.dumps(density, indent=2)); print(json_path); print(md_path)
        return

    partitions = {}
    raw_partitions: dict[str, dict[str, dict]] = {}
    train_report, train_raw = evaluate_partition(
        "train", detections, prices_all, membership, breadth_series, args.iterations)
    partitions["train"] = train_report
    raw_partitions["train"] = train_raw
    train_gate = _train_gate(
        train_raw["primary_20d_0pp"], train_report["comparison"])
    validation_accessed = train_gate["passed"] or args.descriptive_full_audit
    validation_gate = None
    best_oos_accessed = False
    if validation_accessed:
        validation_report, validation_raw = evaluate_partition(
            "validation", detections, prices_all, membership,
            breadth_series, args.iterations)
        partitions["validation"] = validation_report
        raw_partitions["validation"] = validation_raw
        validation_gate = _validation_gate(
            validation_raw["primary_20d_0pp"], validation_report["comparison"])
        best_oos_accessed = (
            validation_gate["passed"] or args.descriptive_full_audit)
    if best_oos_accessed:
        oos_report, oos_raw = evaluate_partition(
            "best_available_oos", detections, prices_all, membership,
            breadth_series, args.iterations)
        partitions["best_available_oos"] = oos_report
        raw_partitions["best_available_oos"] = oos_raw

    score_source = raw_partitions[
        "best_available_oos" if best_oos_accessed else
        "validation" if validation_accessed else "train"]["primary_20d_0pp"]
    score = discovery_backtest_score(score_source["score_cell"])
    if args.descriptive_full_audit and not density["passed"]:
        verdict = "INCONCLUSIVE"
        interpretation = (
            "The prespecified family failed its outcome-free activation gate. "
            "All return results are a post-density descriptive audit and cannot "
            "support IMPROVES, regardless of their direction.")
    elif not best_oos_accessed:
        verdict = "INCONCLUSIVE"
        interpretation = (
            "The primary rule failed a prespecified sequential gate, so later "
            "evidence stayed sealed. Sensitivity cells are descriptive only and "
            "cannot establish out-of-sample improvement.")
    else:
        oos_comparison = partitions["best_available_oos"]["comparison"]
        oos_primary = raw_partitions["best_available_oos"]["primary_20d_0pp"]
        robust = (
            oos_comparison["exposure_matched_excess_cagr_lift_pct_points"] > 0
            and oos_comparison["qualifying_minus_rejected_mean_excess_pct_points"] > 0
            and len(oos_primary["trades"]) >= 30
            and (oos_primary["metrics"]["trade_metrics"][
                "drop_best_five_net_expectancy_pct"] or 0) > 0)
        verdict = "IMPROVES" if robust else (
            "WORSENS" if oos_comparison[
                "exposure_matched_excess_cagr_lift_pct_points"] < 0 else "INCONCLUSIVE")
        interpretation = (
            "The final classification uses only the frozen 20-session, zero-"
            "threshold best-available OOS comparison; that period is previously "
            "contaminated and retains the disclosed score caps.")

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/relative_divergence_v2/frozen_spec.md",
        "data_inventory": "backtests/current_2006_plus_data_audit/inventory.json",
        "classification": (
            "post_density_descriptive_full_partition_audit"
            if args.descriptive_full_audit and not density["passed"]
            else "sequential_relative_divergence_evaluation"),
        "coverage": coverage,
        "parameters": {"primary_lookback": PRIMARY_LOOKBACK,
                       "lookback_sensitivity": LOOKBACK_SENSITIVITY,
                       "threshold_sensitivity_pct": (0.0, *THRESHOLD_SENSITIVITY),
                       "entry_rule": "frozen pullback",
                       "exit_rule": "baseline stop plus 60-session timeout",
                       "price": "CSVClient adjusted close",
                       "calendar_alignment": "actual common dates <= signal_date"},
        "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": TRIALS_AFTER - TRIALS_BEFORE,
        "trials_after": TRIALS_AFTER,
        "density": density,
        "train_gate": train_gate,
        "validation_gate": validation_gate,
        "validation_accessed": validation_accessed,
        "best_available_oos_accessed": best_oos_accessed,
        "descriptive_full_audit": args.descriptive_full_audit,
        "descriptive_audit_spec": (
            "backtests/relative_divergence_v2/descriptive_audit_spec.md"
            if args.descriptive_full_audit else None),
        "ranking_experiment": {"run": False,
                               "reason": "Edge Rank jointly controls priority and sizing"},
        "partitions": partitions,
        "backtest_score": score,
        "verdict": verdict,
        "interpretation": interpretation,
        "reproduction_command": reproduction,
    }
    json_path = output / f"relative_divergence_{stamp}.json"
    md_path = output / f"relative_divergence_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    md_path.write_text(render_markdown(report))
    for partition, variants in raw_partitions.items():
        for variant, result in variants.items():
            prefix = output / f"relative_divergence_{stamp}_{partition}_{variant}"
            _write_csv(prefix.with_name(prefix.name + "_signals.csv"), result["signals"])
            _write_csv(prefix.with_name(prefix.name + "_trades.csv"), result["trades"])
            _write_csv(prefix.with_name(prefix.name + "_equity.csv"), result["equity_curve"])
    print(json.dumps({"density": density, "train_gate": train_gate,
                      "validation_gate": validation_gate,
                      "validation_accessed": validation_accessed,
                      "best_available_oos_accessed": best_oos_accessed,
                      "score": score, "verdict": verdict}, indent=2))
    print(json_path); print(md_path)


if __name__ == "__main__":
    main()
