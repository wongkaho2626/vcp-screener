#!/usr/bin/env python3
"""Prespecified comparison of frozen VCP pullback and Pocket Pivot entries.

The Pocket Pivot scan starts on the VCP as-of bar and lasts ten sessions.  It
uses only as-of detection fields plus contemporaneous/prior OHLCV data; an
accepted signal fills at the next session open.  Both legs reuse the same Edge
Rank sizing, portfolio constraints, costs, stops, and time exits.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
from datetime import datetime

from csv_client import CSVClient
from portfolio_backtest import Config, run_portfolio

RULES = ("pullback", "pocket_pivot")
SEGMENTS = (
    ("development", "2016-01-01", "2021-12-31"),
    ("validation", "2022-01-01", "2024-12-31"),
    ("evaluation", "2025-01-01", "2026-12-31"),
)


def _metrics(result: dict) -> dict:
    returns = [row["portfolio_return"] for row in result["equity_curve"]]
    std = statistics.stdev(returns) if len(returns) > 1 else 0.0
    sharpe = statistics.fmean(returns) / std * math.sqrt(252) if std else 0.0
    trade_returns = [trade["net_return_pct"] / 100 for trade in result["trades"]]
    gains = sum(value for value in trade_returns if value > 0)
    losses = -sum(value for value in trade_returns if value < 0)
    return {
        **result["summary"],
        "sharpe": round(sharpe, 3),
        "profit_factor": round(gains / losses, 3) if losses else None,
    }


def _subset(detections: dict, start: str, end: str) -> dict:
    """Select detections by their causal as-of date, with inclusive bounds."""
    return {
        symbol: selected
        for symbol, rows in detections.items()
        if (selected := [
            row for row in rows if start <= (row.get("as_of_date") or "") <= end
        ])
    }


def _clip_prices(prices: dict, end: str) -> dict:
    return {
        symbol: [bar for bar in bars if bar["date"] <= end]
        for symbol, bars in prices.items()
    }


def run_experiment(
    detections: dict, prices: dict, cfg: Config = Config(),
) -> dict:
    full = {
        rule: run_portfolio(detections, prices, cfg, entry_rule=rule)
        for rule in RULES
    }
    segments = {}
    for name, start, end in SEGMENTS:
        segment_detections = _subset(detections, start, end)
        segment_prices = _clip_prices(prices, end)
        segments[name] = {
            "start": start,
            "end": end,
            **{
                rule: _metrics(run_portfolio(
                    segment_detections, segment_prices, cfg, entry_rule=rule,
                ))
                for rule in RULES
            },
        }
    return {
        "frozen_hypothesis": {
            "baseline": "MA20 touch-and-hold within 15 sessions after a realised breakout",
            "candidate": "Pocket Pivot within a detected VCP",
            "scan_window_sessions": 10,
            "scan_starts": "as_of bar (inclusive)",
            "volume_rule": (
                "up-day volume strictly exceeds the largest down-day volume "
                "among the preceding 10 sessions; fail when none exist"
            ),
            "moving_average_rule": "SMA10 > SMA50 > SMA200 on signal close",
            "location_rule": (
                "close >= SMA10, <= 3% above SMA10, and <= 3% above as-of VCP pivot"
            ),
            "entry": "next session open",
            "invalidation": "close below as-of last-contraction low before signal",
            "pivot_source": "vcp_pattern.pivot_price at as_of_date",
            "stop_source": "vcp_pattern.contractions[-1].low_price at as_of_date",
            "forward_outcome_used_for_pocket_pivot": False,
            "threshold_sweep": False,
        },
        "comparison_controls": {
            "identical_edge_rank_sizing": True,
            "identical_portfolio_constraints": True,
            "identical_costs": True,
            "identical_exits": True,
            "segment_assignment_field": "as_of_date",
        },
        "config": cfg.__dict__,
        "segments": segments,
        **full,
    }


def _write_daily(path: str, curve: list[dict]) -> None:
    fields = [
        "date", "equity", "cash", "positions", "gross_exposure_pct",
        "portfolio_return", "spy_return", "excess_return",
        "exposure_matched_spy_return", "exposure_matched_excess_return",
    ]
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(curve)


def _write_comparison(path: str, pullback: list[dict], pocket_pivot: list[dict]) -> None:
    """Write aligned daily return lifts, treating pre-signal portfolios as cash."""
    pullback_by_date = {row["date"]: row for row in pullback}
    pocket_by_date = {row["date"]: row for row in pocket_pivot}
    fields = [
        "date", "pullback_return", "pocket_pivot_return", "return_lift",
        "pullback_exposure_matched_excess_return",
        "pocket_pivot_exposure_matched_excess_return", "excess_lift",
    ]
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for date in sorted(set(pullback_by_date) | set(pocket_by_date)):
            baseline = pullback_by_date.get(date) or {}
            candidate = pocket_by_date.get(date) or {}
            baseline_return = float(baseline.get("portfolio_return") or 0.0)
            candidate_return = float(candidate.get("portfolio_return") or 0.0)
            baseline_excess = float(
                baseline.get("exposure_matched_excess_return") or 0.0
            )
            candidate_excess = float(
                candidate.get("exposure_matched_excess_return") or 0.0
            )
            writer.writerow({
                "date": date,
                "pullback_return": baseline_return,
                "pocket_pivot_return": candidate_return,
                "return_lift": candidate_return - baseline_return,
                "pullback_exposure_matched_excess_return": baseline_excess,
                "pocket_pivot_exposure_matched_excess_return": candidate_excess,
                "excess_lift": candidate_excess - baseline_excess,
            })


def _write_markdown(path: str, result: dict) -> None:
    lines = [
        "# VCP Pocket Pivot Experiment", "", "## Frozen hypothesis", "",
        "Compare the existing frozen MA20 pullback entry with a Pocket Pivot scanned ",
        "from the VCP as-of bar through ten sessions. The Pocket Pivot must be an up ",
        "day whose volume strictly exceeds every down-day volume in the preceding ten ",
        "sessions, with SMA10 > SMA50 > SMA200 and price no more than 3% above either ",
        "SMA10 or the frozen VCP pivot. Fill next session open; invalidate on a close ",
        "below the frozen last-contraction low. No threshold sweep was performed.", "",
        "Pocket Pivot qualification and location do not use `forward_outcome`.", "",
        "## Results", "",
        "| Period | Entry | Trades | Return | CAGR | Sharpe | MDD | PF |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    periods = [("full", {rule: _metrics(result[rule]) for rule in RULES})]
    periods += [
        (f'{name} ({rows["start"][:4]}–{rows["end"][:4]})', rows)
        for name, rows in result["segments"].items()
    ]
    for period, rows in periods:
        for rule in RULES:
            metrics = rows[rule]
            profit_factor = (
                "n/a" if metrics["profit_factor"] is None
                else f'{metrics["profit_factor"]:.2f}'
            )
            lines.append(
                f'| {period} | {rule} | {metrics["trades"]} | '
                f'{metrics["total_return_pct"]:.2f}% | {metrics["cagr_pct"]:.2f}% | '
                f'{metrics["sharpe"]:.2f} | {metrics["max_drawdown_pct"]:.2f}% | '
                f'{profit_factor} |'
            )
    with open(path, "w") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--output-dir", default="backtests/improved/pocket_pivot")
    parser.add_argument("--commission-bps", type=float, default=5.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    args = parser.parse_args()
    if args.commission_bps < 0 or args.slippage_bps < 0:
        parser.error("cost inputs must be non-negative")

    with open(args.backtest_json) as handle:
        payload = json.load(handle)
    detections = payload.get("detections_by_ticker") or {}
    client = CSVClient(args.price_csv)
    symbols = [row["symbol"] for row in client.get_constituents()] + ["SPY"]
    prices = {
        symbol: list(reversed(history["historical"]))
        for symbol in symbols
        if (history := client.get_historical_prices(symbol, days=100_000))
    }
    result = run_experiment(
        detections,
        prices,
        Config(
            commission_bps=args.commission_bps,
            slippage_bps=args.slippage_bps,
        ),
    )
    result["data_lineage"] = {
        "backtest_json": os.path.abspath(args.backtest_json),
        "price_csv": os.path.abspath(args.price_csv),
        "detector_metadata": payload.get("metadata") or {},
        "price_client": client.get_api_stats(),
    }

    os.makedirs(args.output_dir, exist_ok=True)
    root = os.path.join(
        args.output_dir,
        f'pocket_pivot_vcp_{datetime.now().strftime("%Y-%m-%d_%H%M%S")}',
    )
    with open(root + ".json", "w") as handle:
        json.dump(result, handle, indent=2)
    for rule in RULES:
        _write_daily(root + f"_{rule}_daily.csv", result[rule]["equity_curve"])
    _write_comparison(
        root + "_comparison_daily.csv",
        result["pullback"]["equity_curve"],
        result["pocket_pivot"]["equity_curve"],
    )
    _write_markdown(root + ".md", result)
    print(root + ".json")
    print(root + ".md")


if __name__ == "__main__":
    main()
