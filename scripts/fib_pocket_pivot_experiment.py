#!/usr/bin/env python3
"""Prespecified Fibonacci-retracement entry test on Pocket Pivot signals.

The candidate keeps the frozen Pocket Pivot v2 signal and replaces its
next-open fill with a wait for the canonical 38.2% retracement of the signal
leg (lowest low of the ten sessions ending at the signal bar up to the signal
bar's high).  The first bar whose low touches the level and whose close holds
at or above it fills at the next session open.  A close below the frozen
pattern stop invalidates while waiting; no touch within ten sessions means no
trade.  Baselines: frozen MA20 pullback and Pocket Pivot v2, identical Edge
Rank sizing, constraints, costs, stops and 60-bar timeout.  Retracement
50%/61.8% and wait windows 5/15 are reported as robustness only, not adopted.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime

from csv_client import CSVClient
from pocket_pivot_experiment import _clip_prices, _metrics, _subset, _write_daily
from portfolio_backtest import Config, run_portfolio

RULES = ("pullback", "pocket_pivot", "pocket_pivot_fib")
SEGMENTS = (
    ("development", "2016-01-01", "2021-12-31"),
    ("validation", "2022-01-01", "2024-12-31"),
    ("evaluation", "2025-01-01", "2026-12-31"),
)
ROBUSTNESS_VARIANTS = (
    ("retracement_0.500", {"retracement": 0.5}),
    ("retracement_0.618", {"retracement": 0.618}),
    ("wait_window_5", {"wait_window": 5}),
    ("wait_window_15", {"wait_window": 15}),
)


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
    robustness = {
        label: _metrics(run_portfolio(
            detections, prices, cfg,
            entry_rule="pocket_pivot_fib", entry_params=params,
        ))
        for label, params in ROBUSTNESS_VARIANTS
    }
    return {
        "frozen_hypothesis": {
            "baselines": ["frozen MA20 pullback", "Pocket Pivot v2 next-open fill"],
            "candidate": "Pocket Pivot v2 signal + 38.2% Fibonacci retracement fill",
            "retracement": 0.382,
            "leg": (
                "lowest low of the 10 sessions ending at the signal bar "
                "up to the signal bar's high"
            ),
            "fill_trigger": "first bar with low <= level <= close (touch-and-hold)",
            "wait_window_sessions": 10,
            "entry": "next session open after the touch-and-hold bar",
            "invalidation": "close below as-of last-contraction low while waiting",
            "no_touch_means_no_trade": True,
            "forward_outcome_used": False,
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
        "robustness_not_adopted": robustness,
        **full,
    }


def _write_markdown(path: str, result: dict) -> None:
    lines = [
        "# VCP Pocket Pivot Fibonacci-Retracement Experiment", "",
        "## Frozen hypothesis", "",
        "Keep the frozen Pocket Pivot v2 signal; replace its next-open fill with a ",
        "wait for the canonical 38.2% Fibonacci retracement of the signal leg ",
        "(lowest low of the 10 sessions ending at the signal bar, up to the signal ",
        "bar's high). Fill next open after the first bar that touches the level and ",
        "closes at or above it. Invalidate on a close below the frozen ",
        "last-contraction low; no touch within 10 sessions means no trade. ",
        "50%/61.8% and wait 5/15 are robustness only. No threshold sweep.", "",
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
    lines += [
        "", "## Robustness (not adopted)", "",
        "| Variant | Trades | Return | CAGR | Sharpe | MDD | PF |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, metrics in result["robustness_not_adopted"].items():
        profit_factor = (
            "n/a" if metrics["profit_factor"] is None
            else f'{metrics["profit_factor"]:.2f}'
        )
        lines.append(
            f'| {label} | {metrics["trades"]} | {metrics["total_return_pct"]:.2f}% | '
            f'{metrics["cagr_pct"]:.2f}% | {metrics["sharpe"]:.2f} | '
            f'{metrics["max_drawdown_pct"]:.2f}% | {profit_factor} |'
        )
    with open(path, "w") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--output-dir", default="backtests/pocket_pivot_fib")
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
        f'fib_pocket_pivot_{datetime.now().strftime("%Y-%m-%d_%H%M%S")}',
    )
    with open(root + ".json", "w") as handle:
        json.dump(result, handle, indent=2)
    for rule in RULES:
        _write_daily(root + f"_{rule}_daily.csv", result[rule]["equity_curve"])
    _write_markdown(root + ".md", result)
    print(root + ".json")
    print(root + ".md")


if __name__ == "__main__":
    main()
