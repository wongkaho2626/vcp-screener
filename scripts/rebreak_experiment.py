#!/usr/bin/env python3
"""Predeclared comparison of MA20-pullback entry versus pullback then rebreak.

Rebreak rule: after the frozen MA20 touch-and-hold within 15 sessions of the
initial breakout, wait for a close above the highest high from the breakout
bar through the pullback bar. Enter next session open. Maximum wait is 60
trading sessions; a close below the pattern stop invalidates the setup.
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

SEGMENTS = (
    ("development", "2016-01-01", "2021-12-31"),
    ("validation", "2022-01-01", "2024-12-31"),
    ("evaluation", "2025-01-01", "2026-12-31"),
)


def _metrics(result: dict) -> dict:
    returns = [row["portfolio_return"] for row in result["equity_curve"]]
    std = statistics.stdev(returns) if len(returns) > 1 else 0.0
    sharpe = statistics.fmean(returns) / std * math.sqrt(252) if std else 0.0
    trade_returns = [t["net_return_pct"] / 100 for t in result["trades"]]
    gains = sum(r for r in trade_returns if r > 0)
    losses = -sum(r for r in trade_returns if r < 0)
    return {**result["summary"], "sharpe": round(sharpe, 3),
            "profit_factor": round(gains / losses, 3) if losses else None}


def _subset(detections: dict, start: str, end: str) -> dict:
    return {symbol: selected for symbol, rows in detections.items()
            if (selected := [d for d in rows if start <=
                ((d.get("forward_outcome") or {}).get("exit_date") or "") <= end])}


def _clip_prices(prices: dict, end: str) -> dict:
    return {symbol: [bar for bar in bars if bar["date"] <= end]
            for symbol, bars in prices.items()}


def run_experiment(detections: dict, prices: dict, cfg: Config = Config()) -> dict:
    full = {rule: run_portfolio(detections, prices, cfg, entry_rule=rule)
            for rule in ("pullback", "rebreak")}
    segments = {}
    for name, start, end in SEGMENTS:
        px = _clip_prices(prices, end)
        dets = _subset(detections, start, end)
        segments[name] = {"start": start, "end": end, **{
            rule: _metrics(run_portfolio(dets, px, cfg, entry_rule=rule))
            for rule in ("pullback", "rebreak")}}
    return {"frozen_hypothesis": {
                "pullback_window_sessions": 15,
                "rebreak_level": "highest high from breakout through pullback bar",
                "rebreak_confirmation": "close strictly above frozen rebreak level",
                "rebreak_wait_sessions": 60,
                "entry": "next session open",
                "invalidation": "close below pattern stop before rebreak",
                "threshold_sweep": False,
            }, "config": cfg.__dict__, "segments": segments, **full}


def _write_daily(path: str, curve: list[dict]) -> None:
    fields = ["date", "equity", "cash", "positions", "gross_exposure_pct",
              "portfolio_return", "spy_return", "excess_return",
              "exposure_matched_spy_return", "exposure_matched_excess_return"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(curve)


def _write_markdown(path: str, result: dict) -> None:
    lines = ["# Pullback-Then-Rebreak Experiment", "", "## Frozen hypothesis", "",
             "After an MA20 touch-and-hold within 15 sessions, wait at most 60 sessions for "
             "a close above the highest high from the initial breakout through the pullback "
             "bar, then enter next session open. No threshold sweep was performed.", "",
             "## Results", "", "| Period | Entry | Trades | Return | CAGR | Sharpe | MDD | PF |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    periods = [("full", {r: _metrics(result[r]) for r in ("pullback", "rebreak")})]
    periods += [(f'{name} ({rows["start"][:4]}–{rows["end"][:4]})', rows)
                for name, rows in result["segments"].items()]
    for period, rows in periods:
        for rule in ("pullback", "rebreak"):
            m = rows[rule]
            pf = "n/a" if m["profit_factor"] is None else f'{m["profit_factor"]:.2f}'
            lines.append(f'| {period} | {rule} | {m["trades"]} | '
                         f'{m["total_return_pct"]:.2f}% | {m["cagr_pct"]:.2f}% | '
                         f'{m["sharpe"]:.2f} | {m["max_drawdown_pct"]:.2f}% | {pf} |')
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--output-dir", default="backtests/improved/rebreak")
    args = parser.parse_args()
    with open(args.backtest_json) as f:
        detections = json.load(f).get("detections_by_ticker") or {}
    client = CSVClient(args.price_csv)
    symbols = [r["symbol"] for r in client.get_constituents()] + ["SPY"]
    prices = {s: list(reversed(hist["historical"])) for s in symbols
              if (hist := client.get_historical_prices(s, days=100_000))}
    result = run_experiment(detections, prices)
    os.makedirs(args.output_dir, exist_ok=True)
    root = os.path.join(args.output_dir,
                        f'rebreak_vcp_{datetime.now().strftime("%Y-%m-%d_%H%M%S")}')
    with open(root + ".json", "w") as f:
        json.dump(result, f, indent=2)
    for rule in ("pullback", "rebreak"):
        _write_daily(root + f"_{rule}_daily.csv", result[rule]["equity_curve"])
    _write_markdown(root + ".md", result)
    print(root + ".json")
    print(root + ".md")


if __name__ == "__main__":
    main()
