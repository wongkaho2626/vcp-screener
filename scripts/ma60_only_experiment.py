#!/usr/bin/env python3
"""Trial 542: standalone stock-versus-SPY relative-MA60 entry strategy."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from cross_sectional_leadership_discovery import discovery_backtest_score
from csv_client import CSVClient
from membership import DEFAULT_MEMBERSHIP_CSV, is_member, load_membership
from pivot_retest_experiment import slice_prices, trade_stats, trim_stats
from portfolio_backtest import Config, run_portfolio
from portfolio_robustness import analyze
from relative_divergence_experiment import (
    _annual_rows,
    _mean,
    enrich_trades,
    trade_metrics,
)

MA_PERIOD = 60
SLOPE_SESSIONS = 20
TRIALS_BEFORE = 540
TRIALS_AFTER = 541
PERIODS = {
    "train": ("2016-07-01", "2018-06-30", "2018-12-31"),
    "validation": ("2019-01-01", "2021-12-31", "2022-03-31"),
    "best_available_oos": ("2022-01-01", "2026-03-31", "2026-06-30"),
    "full": ("2016-07-01", "2026-03-31", "2026-06-30"),
}


def _prefix(values: list[float]) -> list[float]:
    output = [0.0]
    for value in values:
        output.append(output[-1] + value)
    return output


def _window_mean(prefix: list[float], start: int, end: int) -> float:
    """Mean over the half-open interval [start, end)."""
    return (prefix[end] - prefix[start]) / (end - start)


def calculate_ma60_only_signal(
    stock_bars: list[dict], spy_bars: list[dict], as_of_date: str,
    ma_period: int = MA_PERIOD, slope_sessions: int = SLOPE_SESSIONS,
) -> dict | None:
    """Calculate the standalone gate on common completed sessions only."""
    if ma_period <= 0 or slope_sessions <= 0:
        raise ValueError("MA period and slope sessions must be positive")
    stock = {
        str(row.get("date") or ""): float(row.get("adjClose") or row.get("close") or 0)
        for row in stock_bars
        if str(row.get("date") or "") <= as_of_date
        and float(row.get("adjClose") or row.get("close") or 0) > 0
    }
    spy = {
        str(row.get("date") or ""): float(row.get("adjClose") or row.get("close") or 0)
        for row in spy_bars
        if str(row.get("date") or "") <= as_of_date
        and float(row.get("adjClose") or row.get("close") or 0) > 0
    }
    dates = sorted(set(stock).intersection(spy))
    required = ma_period + slope_sessions
    if len(dates) < required:
        return None
    stock_values = [stock[date] for date in dates]
    spy_values = [spy[date] for date in dates]
    stock_prefix = _prefix(stock_values)
    spy_prefix = _prefix(spy_values)
    end = len(dates)
    prior_end = end - slope_sessions
    stock_now = _window_mean(stock_prefix, end - ma_period, end)
    stock_then = _window_mean(stock_prefix, prior_end - ma_period, prior_end)
    spy_now = _window_mean(spy_prefix, end - ma_period, end)
    spy_then = _window_mean(spy_prefix, prior_end - ma_period, prior_end)
    stock_slope = 100 * (stock_now / stock_then - 1)
    spy_slope = 100 * (spy_now / spy_then - 1)
    divergence = stock_slope - spy_slope
    stock_close = stock_values[-1]
    return {
        "ma_period": ma_period,
        "slope_sessions": slope_sessions,
        "signal_date": dates[-1],
        "stock_signal_close": stock_close,
        "stock_ma_value": stock_now,
        "stock_ma_20_sessions_ago": stock_then,
        "spy_ma_value": spy_now,
        "spy_ma_20_sessions_ago": spy_then,
        "stock_ma_slope_pct": stock_slope,
        "spy_ma_slope_pct": spy_slope,
        "relative_ma_slope_pct": divergence,
        "positive_relative_ma_slope": bool(
            stock_close > stock_now and stock_slope > 0 and divergence > 0
        ),
    }


def build_standalone_signals(
    prices: dict[str, list[dict]], membership: dict[str, list[tuple[str, str]]],
    sectors: dict[str, str], start: str, end: str, *,
    ma_period: int = MA_PERIOD, slope_sessions: int = SLOPE_SESSIONS,
) -> tuple[list[dict], dict[str, int]]:
    """Emit one causal order on each false-to-true relative-MA transition."""
    if ma_period <= 0 or slope_sessions <= 0:
        raise ValueError("MA period and slope sessions must be positive")
    spy = {
        row["date"]: float(row.get("adjClose") or row.get("close") or 0)
        for row in prices.get("SPY", [])
        if float(row.get("adjClose") or row.get("close") or 0) > 0
    }
    counts: Counter[str] = Counter()
    signals: list[dict] = []
    required = ma_period + slope_sessions
    for symbol in sorted(key for key in prices if key != "SPY"):
        bars = prices[symbol]
        stock_rows = {
            row["date"]: (index, float(row.get("adjClose") or row.get("close") or 0))
            for index, row in enumerate(bars)
            if float(row.get("adjClose") or row.get("close") or 0) > 0
        }
        common_dates = sorted(set(stock_rows).intersection(spy))
        if len(common_dates) < required:
            counts["insufficient_common_history_tickers"] += 1
            continue
        stock_values = [stock_rows[date][1] for date in common_dates]
        spy_values = [spy[date] for date in common_dates]
        stock_prefix = _prefix(stock_values)
        spy_prefix = _prefix(spy_values)
        previous = False
        for position in range(required - 1, len(common_dates)):
            date = common_dates[position]
            if date > end:
                break
            now_end = position + 1
            prior_end = now_end - slope_sessions
            stock_now = _window_mean(
                stock_prefix, now_end - ma_period, now_end)
            stock_then = _window_mean(
                stock_prefix, prior_end - ma_period, prior_end)
            spy_now = _window_mean(spy_prefix, now_end - ma_period, now_end)
            spy_then = _window_mean(spy_prefix, prior_end - ma_period, prior_end)
            stock_slope = 100 * (stock_now / stock_then - 1)
            spy_slope = 100 * (spy_now / spy_then - 1)
            divergence = stock_slope - spy_slope
            condition = bool(
                stock_values[position] > stock_now
                and stock_slope > 0
                and divergence > 0
            )
            if start <= date <= end:
                counts["evaluated_stock_sessions"] += 1
                counts["true_stock_sessions"] += int(condition)
            rising = condition and not previous
            previous = condition
            if not rising or not start <= date <= end:
                continue
            counts["rising_edge_events"] += 1
            if not is_member(membership, symbol, date):
                counts["not_member_on_signal"] += 1
                continue
            stock_index = stock_rows[date][0]
            if stock_index + 1 >= len(bars):
                counts["missing_next_ticker_session"] += 1
                continue
            fill_date = bars[stock_index + 1]["date"]
            if not is_member(membership, symbol, fill_date):
                counts["not_member_on_fill"] += 1
                continue
            counts["emitted_signals"] += 1
            sector = sectors.get(symbol) or "Unknown"
            counts["unknown_sector_signals"] += int(sector == "Unknown")
            signals.append({
                "symbol": symbol,
                "sector": sector,
                "signal_date": date,
                "fill_date": fill_date,
                "fill_idx": stock_index + 1,
                # All names are capped at the same 10% target. Values above the
                # cap preserve relative-slope priority inside run_portfolio.
                "edge_rank": Config().edge_cap + divergence,
                "candidate_priority": divergence,
                "pattern_stop": 0.0,
                "pivot": None,
                "attempt": 1,
                "relative_ma_period": ma_period,
                "relative_ma_slope_sessions": slope_sessions,
                "stock_signal_close": stock_values[position],
                "stock_ma_value": stock_now,
                "stock_ma_20_sessions_ago": stock_then,
                "spy_ma_value": spy_now,
                "spy_ma_20_sessions_ago": spy_then,
                "stock_ma_slope_pct": stock_slope,
                "spy_ma_slope_pct": spy_slope,
                "relative_ma_slope_pct": divergence,
                "positive_relative_ma_slope": True,
                "relative_ma_signal_date": date,
                "relative_ma_missing_reason": None,
            })
    return sorted(signals, key=lambda row: (
        row["fill_date"], -row["candidate_priority"], row["symbol"]
    )), dict(sorted(counts.items()))


def _portfolio_metrics(
    portfolio: dict, enriched: list[dict], cfg: Config, iterations: int,
    seed_offset: int, trials: int,
) -> tuple[dict, dict]:
    curve = portfolio["equity_curve"]
    returns = [float(row["portfolio_return"]) for row in curve]
    excess = [float(row["exposure_matched_excess_return"]) for row in curve]
    dates = pd.Series([row["date"] for row in curve])
    robust = analyze(
        dates, returns, trials, iterations, 10,
        20260820 + seed_offset, .70,
    )
    excess_robust = analyze(
        dates, excess, trials, iterations, 10,
        20260840 + seed_offset, .70,
    )
    average_equity = _mean([float(row["equity"]) for row in curve]) or cfg.initial_cash
    traded_notional = sum(
        float(row["shares"]) * (float(row["entry_price"]) + float(row["exit_price"]))
        for row in enriched
    )
    cost_rate = (cfg.commission_bps + cfg.slippage_bps) / 10_000
    estimated_costs = sum(
        float(row["shares"]) * (
            float(row["entry_price"]) / (1 + cost_rate) * cost_rate
            + float(row["exit_price"]) / (1 - cost_rate) * cost_rate
        )
        for row in enriched
    ) if cost_rate < 1 else None
    spy_total = (math.prod(1 + float(row["spy_return"]) for row in curve) - 1) if curve else 0
    years = max(len(curve) / 252, 1 / 252)
    spy_cagr = (1 + spy_total) ** (1 / years) - 1 if spy_total > -1 else -1
    metrics = {
        "summary": portfolio["summary"],
        "spy_total_return_pct": 100 * spy_total,
        "spy_cagr_pct": 100 * spy_cagr,
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


def evaluate_signals(
    signals: list[dict], prices: dict[str, list[dict]], *,
    cost_multiplier: int = 1, iterations: int = 1000, seed_offset: int = 0,
    exit_rule: str = "baseline", exit_params: dict | None = None,
    trials: int = TRIALS_AFTER,
    simulation_start_date: str | None = None,
) -> dict:
    one_way_cost = 10.0 * cost_multiplier / 10_000
    # run_portfolio normally measures max risk from its cost-loaded fill. Undo
    # that mechanical coupling so every cost stress keeps the same raw-open 8%
    # stop and changes costs only.
    cost_neutral_max_risk_pct = 100 * (
        1 - (1 - Config().max_risk_pct / 100) / (1 + one_way_cost)
    )
    cfg = Config(
        commission_bps=5.0 * cost_multiplier,
        slippage_bps=5.0 * cost_multiplier,
        max_risk_pct=cost_neutral_max_risk_pct,
    )
    with patch("portfolio_backtest._candidate_signals", return_value=signals):
        portfolio = run_portfolio(
            {}, prices, cfg, exit_rule=exit_rule, exit_params=exit_params,
            simulation_start_date=simulation_start_date)
    enriched = enrich_trades(portfolio["trades"], signals, prices, cfg)
    metrics, score_cell = _portfolio_metrics(
        portfolio, enriched, cfg, iterations, seed_offset, trials)
    return {
        "metrics": metrics,
        "score_cell": score_cell,
        "signals": signals,
        "trades": enriched,
        "equity_curve": portfolio["equity_curve"],
    }


def _compact_cost(result: dict) -> dict:
    metrics = result["metrics"]
    return {
        "cagr_pct": metrics["summary"]["cagr_pct"],
        "total_return_pct": metrics["summary"]["total_return_pct"],
        "max_drawdown_pct": metrics["summary"]["max_drawdown_pct"],
        "sharpe": metrics["sharpe"],
        "profit_factor": metrics["trade_metrics"]["net_profit_factor"],
        "mean_net_return_pct": metrics["trade_metrics"]["mean_net_return_pct"],
        "estimated_transaction_costs": metrics["estimated_transaction_costs"],
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


def _format(value: object, digits: int = 2) -> str:
    if value is None:
        return "unavailable"
    return f"{float(value):.{digits}f}"


def render_markdown(report: dict) -> str:
    score = report["backtest_score"]
    lines = [
        "# Trial 542 — Standalone Relative-MA60 Entry",
        "",
        f"Verdict: **{report['verdict']}**",
        "",
        f"## Backtest Score: {score['final_score']}/100 — {score['band']}",
        "",
        "| Component | Score | Available max |",
        "|---|---:|---:|",
    ]
    labels = {
        "A_statistical_validity": "A. Statistical validity",
        "B_risk_adjusted_performance": "B. Risk-adjusted performance",
        "C_robustness_computable": "C. Robustness computable",
        "D_trade_quality_consistency": "D. Trade quality / consistency",
    }
    for key, cell in score["components"].items():
        lines.append(f"| {labels[key]} | {cell['score']} | {cell['max']} |")
    lines += [
        f"| Measured total | {score['measured_total']} | {score['measured_denominator']} |",
        f"| Normalized raw score | {score['reduced_denominator_normalized_raw_score']} | 100 |",
        "| Caps | unresolved survivorship → 20 | |",
        f"| **Final score** | **{score['final_score']}** | **100** |",
        "",
        "The score is capped because price coverage is incomplete for historical/delisted members. The latest partition is best-available, not untouched OOS.",
        "",
        "## Definition",
        "",
        "No VCP, breakout, MA20 pullback, pivot, contraction, pattern stop, or Edge Rank is used. A false-to-true standalone MA60 gate signals at the close and fills next open. The portfolio uses equal 10% targets, relative-slope priority, an 8% hard stop, a 60-session timeout, and frozen costs/capacity.",
        "",
        "## Chronological results at 1× costs",
        "",
        "| Partition | Signals | Trades | CAGR | SPY CAGR | Total return | MDD | Sharpe | PF | Exposure | Mean trade | Drop-best-5 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("train", "validation", "best_available_oos", "full"):
        part = report["partitions"][name]
        metrics = part["metrics"]
        summary = metrics["summary"]
        trades = metrics["trade_metrics"]
        lines.append(
            f"| {name} | {summary['signals']} | {summary['trades']} | "
            f"{_format(summary['cagr_pct'])}% | {_format(metrics['spy_cagr_pct'])}% | "
            f"{_format(summary['total_return_pct'])}% | {_format(summary['max_drawdown_pct'])}% | "
            f"{_format(metrics['sharpe'], 3)} | {_format(trades['net_profit_factor'], 3)} | "
            f"{_format(metrics['average_exposure_pct'])}% | {_format(trades['mean_net_return_pct'])}% | "
            f"{_format(trades['drop_best_five_net_expectancy_pct'])}% |"
        )
    lines += [
        "",
        "## Cost stress",
        "",
        "| Partition | Cost | CAGR | Total return | MDD | Sharpe | PF | Mean trade |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("train", "validation", "best_available_oos", "full"):
        for multiplier, cell in report["cost_stress"][name].items():
            lines.append(
                f"| {name} | {multiplier}× | {_format(cell['cagr_pct'])}% | "
                f"{_format(cell['total_return_pct'])}% | {_format(cell['max_drawdown_pct'])}% | "
                f"{_format(cell['sharpe'], 3)} | {_format(cell['profit_factor'], 3)} | "
                f"{_format(cell['mean_net_return_pct'])}% |"
            )
    full = report["partitions"]["full"]["metrics"]
    oos = report["partitions"]["best_available_oos"]["metrics"]
    lines += [
        "",
        "## Interpretation",
        "",
        report["interpretation"],
        "",
        f"Full-period exposure-matched excess CAGR: {_format(full['exposure_matched_excess_cagr_pct'])}%; best-available OOS: {_format(oos['exposure_matched_excess_cagr_pct'])}%.",
        "",
        f"Capacity was saturated: {full['summary']['rejected'].get('duplicate_or_position_limit', 0):,} of {full['summary']['signals']:,} full-period signals were rejected because the name was already held or all ten slots were occupied. Average exposure was {_format(full['average_exposure_pct'])}%, so the SPY shortfall is not explained by staying mostly in cash.",
        "",
        "This is not an apples-to-apples entry-filter test: removing VCP also removes its pattern stop and Edge Rank input. The frozen replacements are documented in `frozen_spec.md`. Current sector labels are not point-in-time, and historical/delisted price coverage remains incomplete.",
        "",
        "## Reproduction",
        "",
        "```bash",
        report["reproduction_command"],
        "```",
    ]
    return "\n".join(lines) + "\n"


def _sector_map(path: str) -> dict[str, str]:
    rows = json.loads(Path(path).read_text())
    return {
        str(row.get("symbol") or "").upper().replace(".", "-"): str(row.get("sector") or "Unknown")
        for row in rows
        if row.get("symbol")
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--sector-json", default="scripts/data/sp500_constituents.json")
    parser.add_argument("--output-dir", default="backtests/ma60_only_v2/results")
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
    partitions = {}
    raw = {}
    cost_stress = {}
    for offset, (name, (start, end, price_end)) in enumerate(PERIODS.items()):
        prices = slice_prices(prices_all, start, price_end)
        signals, counts = build_standalone_signals(
            prices, membership, sectors, start, end)
        result = evaluate_signals(
            signals, prices, iterations=args.iterations, seed_offset=offset)
        raw[name] = result
        partitions[name] = {
            "period": [start, end],
            "price_end": price_end,
            "signal_counts": counts,
            "metrics": result["metrics"],
        }
        cost_stress[name] = {"1": _compact_cost(result)}
        for multiplier in (2, 5, 10):
            stressed = evaluate_signals(
                signals, prices, cost_multiplier=multiplier,
                iterations=args.iterations, seed_offset=offset + multiplier * 10)
            cost_stress[name][str(multiplier)] = _compact_cost(stressed)
    score = discovery_backtest_score(raw["full"]["score_cell"])
    full_metrics = partitions["full"]["metrics"]
    oos_metrics = partitions["best_available_oos"]["metrics"]
    positive_full = (
        full_metrics["summary"]["cagr_pct"] > 0
        and full_metrics["exposure_matched_excess_cagr_pct"] > 0
    )
    positive_oos = (
        oos_metrics["summary"]["cagr_pct"] > 0
        and oos_metrics["exposure_matched_excess_cagr_pct"] > 0
    )
    verdict = "INCONCLUSIVE" if positive_full and positive_oos else "WORSENS"
    interpretation = (
        "The standalone rule is economically positive in both the full and latest "
        "partitions, but MA60 was chosen after the train grid and the architecture "
        "required new sizing/stop assumptions; treat the result as exploratory."
        if verdict == "INCONCLUSIVE" else
        "The standalone rule makes a positive absolute return, but materially "
        "underperforms SPY and has negative exposure-matched excess performance "
        "in both the full and latest partitions."
    )
    reproduction = (
        ".venv/bin/python scripts/ma60_only_experiment.py "
        "--price-csv SP500_PIT_2016_2026.csv "
        "--coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json "
        "--membership-csv scripts/data/sp500_membership.csv "
        "--sector-json scripts/data/sp500_constituents.json "
        "--output-dir backtests/ma60_only_v2/results --iterations 1000"
    )
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "classification": "standalone_relative_ma60_rising_edge",
        "family_spec": "backtests/ma60_only_v2/frozen_spec.md",
        "parameters": {
            "ma_period": MA_PERIOD,
            "slope_sessions": SLOPE_SESSIONS,
            "entry_event": "false_to_true",
            "position_target_pct": Config().max_position_pct,
            "initial_stop_pct": Config().max_risk_pct,
            "max_hold_sessions": Config().max_hold_bars,
        },
        "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": 1,
        "trials_after": TRIALS_AFTER,
        "coverage": coverage,
        "partitions": partitions,
        "cost_stress": cost_stress,
        "backtest_score": score,
        "verdict": verdict,
        "interpretation": interpretation,
        "reproduction_command": reproduction,
    }
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stem = output / f"ma60_only_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}"
    stem.with_suffix(".json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    stem.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    for name, result in raw.items():
        _csv(Path(f"{stem}_{name}_signals.csv"), result["signals"])
        _csv(Path(f"{stem}_{name}_trades.csv"), result["trades"])
        _csv(Path(f"{stem}_{name}_equity.csv"), result["equity_curve"])
    print(json.dumps({
        "verdict": verdict,
        "score": score["final_score"],
        "full": partitions["full"]["metrics"],
        "best_available_oos": partitions["best_available_oos"]["metrics"],
        "json": str(stem.with_suffix(".json")),
        "markdown": str(stem.with_suffix(".md")),
    }, indent=2))


if __name__ == "__main__":
    main()
