#!/usr/bin/env python3
"""Prespecified Trial 368-373 Parabolic SAR flip lifecycle."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from anchored_vwap_reclaim_discovery import _period_rows, _score_table
from cross_sectional_leadership_discovery import discovery_backtest_score
from csv_client import CSVClient
from dmi_crossover_lifecycle_discovery import (
    VALIDATION,
    VALIDATION_PRICE_END,
    VALIDATION_PRICE_START,
    lifecycle_signals,
)
from linear_timing_discovery import FIT, FIT_PRICE_END, compact, evaluate
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import slice_prices
from undercut_reclaim_discovery import gate


def parabolic_sar_series(bars: list[dict], acceleration_step: float = .02,
                         acceleration_max: float = .20) -> list[float | None]:
    """Return a causal standard Parabolic SAR series."""
    if acceleration_step <= 0 or acceleration_max < acceleration_step:
        raise ValueError("invalid Parabolic SAR acceleration parameters")
    result: list[float | None] = [None] * len(bars)
    if len(bars) < 2:
        return result
    uptrend = float(bars[1].get("close") or 0) >= float(bars[0].get("close") or 0)
    sar = float(bars[0]["low"] if uptrend else bars[0]["high"])
    extreme = float(bars[0]["high"] if uptrend else bars[0]["low"])
    acceleration = acceleration_step
    result[0] = sar
    for index in range(1, len(bars)):
        candidate = sar + acceleration * (extreme - sar)
        if uptrend:
            candidate = min(candidate, float(bars[index - 1]["low"]),
                            float(bars[index - 2]["low"])
                            if index >= 2 else float(bars[index - 1]["low"]))
            if float(bars[index]["low"]) < candidate:
                uptrend = False
                sar = extreme
                extreme = float(bars[index]["low"])
                acceleration = acceleration_step
            else:
                sar = candidate
                if float(bars[index]["high"]) > extreme:
                    extreme = float(bars[index]["high"])
                    acceleration = min(acceleration_max,
                                       acceleration + acceleration_step)
        else:
            candidate = max(candidate, float(bars[index - 1]["high"]),
                            float(bars[index - 2]["high"])
                            if index >= 2 else float(bars[index - 1]["high"]))
            if float(bars[index]["high"]) > candidate:
                uptrend = True
                sar = extreme
                extreme = float(bars[index]["high"])
                acceleration = acceleration_step
            else:
                sar = candidate
                if float(bars[index]["low"]) < extreme:
                    extreme = float(bars[index]["low"])
                    acceleration = min(acceleration_max,
                                       acceleration + acceleration_step)
        result[index] = sar
    return result


def psar_state(bars: list[dict], sar: list[float | None], index: int,
               pivot: float) -> dict[str, bool]:
    """Return causal close/PSAR crossover entry and below-PSAR exit state."""
    if index <= 0 or index >= len(bars) or index >= len(sar):
        return {"positive_cross": False, "negative_dominance": False}
    current_sar = sar[index]
    prior_sar = sar[index - 1]
    if current_sar is None or prior_sar is None:
        return {"positive_cross": False, "negative_dominance": False}
    close = float(bars[index].get("close") or 0)
    prior_close = float(bars[index - 1].get("close") or 0)
    below = close < current_sar
    cross = prior_close <= prior_sar and close > current_sar and close > pivot
    return {"positive_cross": cross, "negative_dominance": below}


def psar_states(rows: list[dict], prices: dict[str, list[dict]],
                acceleration_step: float = .02,
                acceleration_max: float = .20) -> list[dict]:
    cache = {symbol: parabolic_sar_series(bars, acceleration_step, acceleration_max)
             for symbol, bars in prices.items() if symbol != "SPY"}
    states = []
    for row in rows:
        bars = prices.get(row["symbol"]) or []
        state = psar_state(bars, cache.get(row["symbol"]) or [],
                           int(row["fill_idx"]) - 1,
                           float(row.get("pivot") or 0))
        states.append({**row, **state})
    return states


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--output-dir", default="backtests/parabolic_sar_lifecycle_v2/results")
    parser.add_argument("--iterations", type=int, default=1000)
    args = parser.parse_args()
    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/benchmark gate failed")
    detections = json.loads(Path(args.backtest_json).read_text())["detections_by_ticker"]
    membership = load_membership(args.membership_csv)
    client = CSVClient(args.price_csv)
    prices_all = {row["symbol"]: list(reversed(client.get_historical_prices(
        row["symbol"], days=100_000)["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]}

    train_prices = slice_prices(prices_all, FIT[0], FIT_PRICE_END)
    train_rows, train_drops = _period_rows(detections, membership, train_prices, *FIT)
    train_states = psar_states(train_rows, train_prices)
    train_signals = lifecycle_signals(train_states)
    train_raw = evaluate(train_signals, train_prices, args.iterations,
                         exit_rule="model_decay", trials_declared=373)
    train_cell = compact(train_raw)
    train_gate = gate(train_cell, 60, 10)
    train_score = discovery_backtest_score(train_cell)

    validation = validation_raw = validation_drops = None
    if train_gate["passed"]:
        validation_prices = slice_prices(
            prices_all, VALIDATION_PRICE_START, VALIDATION_PRICE_END)
        validation_rows, validation_drops = _period_rows(
            detections, membership, validation_prices, *VALIDATION)
        validation_states = psar_states(validation_rows, validation_prices)
        validation_signals = lifecycle_signals(validation_states)
        validation_raw = evaluate(validation_signals, validation_prices, args.iterations,
                                  exit_rule="model_decay", trials_declared=373)
        validation_cell = compact(validation_raw)
        validation = {"candidate_rows": len(validation_rows),
                      "states": len(validation_states),
                      "signals": validation_signals, "cell": validation_cell,
                      "score": discovery_backtest_score(validation_cell),
                      "gate": gate(validation_cell, 60, 15)}

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/parabolic_sar_lifecycle_v2/frozen_spec.md",
        "data_inventory": "backtests/current_2006_plus_data_audit/inventory.json",
        "backtest_score": train_score,
        "formal_validation_accessed": validation is not None,
        "best_available_oos_accessed": False,
        "coverage": coverage,
        "trials_before": 367, "new_multiplicity_units": 6, "trials_after": 373,
        "parameters": {"acceleration_step": .02, "acceleration_max": .20,
                       "entry": "close cross above PSAR and frozen pivot",
                       "exit_confirm_below_psar_closes": 2,
                       "max_attempts": 3, "max_hold_sessions": 60},
        "chronology": {"train": FIT, "embargo": ["2018-07-01", "2018-12-31"],
                       "validation": VALIDATION,
                       "best_available_frozen_oos": ["2022-01-01", "2026-03-31"]},
        "membership_drops": {"train": train_drops, "validation": validation_drops},
        "train": {"candidate_rows": len(train_rows), "states": len(train_states),
                  "signals": train_signals, "cell": train_cell, "gate": train_gate},
        "validation": validation,
        "open_best_available_oos": bool(validation and validation["gate"]["passed"]),
    }
    output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = output / f"parabolic_sar_lifecycle_{stamp}.json"
    markdown_path = output / f"parabolic_sar_lifecycle_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (train_cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 368–373 — Parabolic SAR Flip Lifecycle", "",
             "Best-available frozen OOS accessed: **NO**", "", *_score_table(train_score),
             f"Train states {len(train_states)}; signals {len(train_signals)}; "
             f"trades {train_cell['trade_stats']['trades']}; "
             f"CAGR {train_cell['summary']['cagr_pct']:.2f}%; "
             f"Sharpe {(adjusted.get('sharpe') or 0):.3f}; "
             f"PF {(train_cell['trade_stats'].get('profit_factor') or 0):.3f}; "
             f"MDD {train_cell['summary']['max_drawdown_pct']:.2f}%; "
             f"trim-5 expectancy {(train_cell['drop_top_5'].get('expectancy_pct') or 0):.2f}%.", "",
             f"Train gate: **{'PASS' if train_gate['passed'] else 'FAIL'}**", ""]
    lines.extend(f"- {'PASS' if passed else 'FAIL'} — {name}"
                 for name, passed in train_gate["checks"].items())
    lines += ["", f"2019–2021 validation accessed: "
              f"**{'YES' if validation else 'NO'}**", "",
              "2022–2026Q1 best-available OOS remains sealed.", ""]
    markdown_path.write_text("\n".join(lines))
    if train_raw["trades"]:
        pd.DataFrame(train_raw["trades"]).to_csv(
            output / f"parabolic_sar_lifecycle_{stamp}_train_trades.csv", index=False)
        pd.DataFrame(train_raw["equity_curve"]).to_csv(
            output / f"parabolic_sar_lifecycle_{stamp}_train_daily.csv", index=False)
    if validation_raw and validation_raw["trades"]:
        pd.DataFrame(validation_raw["trades"]).to_csv(
            output / f"parabolic_sar_lifecycle_{stamp}_validation_trades.csv", index=False)
        pd.DataFrame(validation_raw["equity_curve"]).to_csv(
            output / f"parabolic_sar_lifecycle_{stamp}_validation_daily.csv", index=False)
    print(json.dumps({"train_signals": len(train_signals),
                      "train_summary": train_cell["summary"], "train_gate": train_gate,
                      "backtest_score": train_score,
                      "validation_accessed": validation is not None,
                      "open_best_available_oos": report["open_best_available_oos"]}, indent=2))
    print(json_path); print(markdown_path)


if __name__ == "__main__":
    main()
