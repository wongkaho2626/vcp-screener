#!/usr/bin/env python3
"""Prespecified Trial 483-488 lag-1 serial-dependence lifecycle."""

from __future__ import annotations

import argparse
import json
import math
import statistics
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
from macd_crossover_lifecycle_discovery import DENSITY_MAX, DENSITY_MIN
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import slice_prices
from undercut_reclaim_discovery import gate

RETURN_WINDOW = 20
TRIALS_BEFORE = 482
TRIALS_AFTER = 488


def lag1_autocorrelation(bars: list[dict], index: int,
                         period: int = RETURN_WINDOW) -> float | None:
    """Pearson lag-1 autocorrelation of causal close returns through ``index``."""
    if period < 3:
        raise ValueError("autocorrelation period must be at least 3")
    if index < period or index >= len(bars):
        return None
    returns = []
    for offset in range(index - period + 1, index + 1):
        prior = float(bars[offset - 1].get("close") or 0)
        close = float(bars[offset].get("close") or 0)
        if prior <= 0 or close <= 0:
            return None
        returns.append(close / prior - 1)
    x_values, y_values = returns[:-1], returns[1:]
    x_mean = statistics.fmean(x_values)
    y_mean = statistics.fmean(y_values)
    x_ss = sum((value - x_mean) ** 2 for value in x_values)
    y_ss = sum((value - y_mean) ** 2 for value in y_values)
    denominator = math.sqrt(x_ss * y_ss)
    if denominator == 0:
        return None
    return sum((x - x_mean) * (y - y_mean)
               for x, y in zip(x_values, y_values)) / denominator


def serial_dependence_state(bars: list[dict], index: int, pivot: float,
                            period: int = RETURN_WINDOW) -> dict:
    """Return causal zero-cross entry and nonpositive serial-state exit flags."""
    current = lag1_autocorrelation(bars, index, period)
    prior = lag1_autocorrelation(bars, index - 1, period)
    if current is None:
        return {"positive_cross": False, "negative_dominance": False,
                "lag1_autocorrelation": None,
                "prior_lag1_autocorrelation": prior}
    close = float(bars[index].get("close") or 0)
    cross = bool(prior is not None and prior <= 0 < current and close > pivot)
    return {"positive_cross": cross, "negative_dominance": current <= 0,
            "lag1_autocorrelation": current,
            "prior_lag1_autocorrelation": prior}


def serial_dependence_states(rows: list[dict],
                             prices: dict[str, list[dict]]) -> list[dict]:
    states = []
    for row in rows:
        bars = prices.get(row["symbol"]) or []
        state = serial_dependence_state(
            bars, int(row["fill_idx"]) - 1, float(row.get("pivot") or 0))
        states.append({**row, **state})
    return states


def _write_density_failure(output: Path, stamp: str, coverage: dict,
                           rows: list[dict], states: list[dict],
                           signals: list[dict], drops: int) -> None:
    density = {"candidate_rows": len(rows), "states": len(states),
               "signals": len(signals),
               "symbols": len({row["symbol"] for row in signals}),
               "minimum": DENSITY_MIN, "maximum": DENSITY_MAX,
               "passed": False}
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/serial_dependence_lifecycle_v2/frozen_spec.md",
        "classification": "outcome_free_density_only",
        "return_evaluation_accessed": False,
        "validation_accessed": False,
        "best_available_oos_accessed": False,
        "coverage": coverage, "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": TRIALS_AFTER - TRIALS_BEFORE,
        "trials_after": TRIALS_AFTER,
        "parameters": {"return_window": RETURN_WINDOW, "lag": 1,
                       "estimator": "Pearson",
                       "entry": "nonpositive-to-positive cross above pivot",
                       "exit_confirm_nonpositive_closes": 2,
                       "max_attempts": 3, "max_hold_sessions": 60},
        "density": density, "membership_drops": drops,
        "permission_to_evaluate_returns": False,
    }
    json_path = output / f"serial_dependence_lifecycle_{stamp}.json"
    md_path = output / f"serial_dependence_lifecycle_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    md_path.write_text(
        "# Trial 483–488 — Lag-1 Serial-Dependence Density Audit\n\n"
        "Return evaluation accessed: **NO**\n\n"
        f"Signals: **{len(signals)}** across {density['symbols']} symbols; "
        f"required {DENSITY_MIN}–{DENSITY_MAX}.\n\n"
        "Density gate: **FAIL**. The family is closed outcome-free; validation "
        "and best-available OOS remain sealed.\n"
    )
    print(json.dumps(density, indent=2)); print(json_path); print(md_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--output-dir",
                        default="backtests/serial_dependence_lifecycle_v2/results")
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
    train_rows, train_drops = _period_rows(
        detections, membership, train_prices, *FIT)
    train_states = serial_dependence_states(train_rows, train_prices)
    train_signals = lifecycle_signals(train_states)
    output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    if not DENSITY_MIN <= len(train_signals) <= DENSITY_MAX:
        _write_density_failure(output, stamp, coverage, train_rows,
                               train_states, train_signals, train_drops)
        return

    train_raw = evaluate(train_signals, train_prices, args.iterations,
                         exit_rule="model_decay", trials_declared=TRIALS_AFTER)
    train_cell = compact(train_raw)
    train_gate = gate(train_cell, 60, 10)
    train_score = discovery_backtest_score(train_cell)

    validation = validation_raw = validation_drops = None
    if train_gate["passed"]:
        validation_prices = slice_prices(
            prices_all, VALIDATION_PRICE_START, VALIDATION_PRICE_END)
        validation_rows, validation_drops = _period_rows(
            detections, membership, validation_prices, *VALIDATION)
        validation_states = serial_dependence_states(
            validation_rows, validation_prices)
        validation_signals = lifecycle_signals(validation_states)
        validation_raw = evaluate(
            validation_signals, validation_prices, args.iterations,
            exit_rule="model_decay", trials_declared=TRIALS_AFTER)
        validation_cell = compact(validation_raw)
        validation = {"candidate_rows": len(validation_rows),
                      "signals": validation_signals, "cell": validation_cell,
                      "score": discovery_backtest_score(validation_cell),
                      "gate": gate(validation_cell, 60, 15)}

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/serial_dependence_lifecycle_v2/frozen_spec.md",
        "backtest_score": train_score,
        "formal_validation_accessed": validation is not None,
        "best_available_oos_accessed": False,
        "coverage": coverage, "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": TRIALS_AFTER - TRIALS_BEFORE,
        "trials_after": TRIALS_AFTER,
        "parameters": {"return_window": RETURN_WINDOW, "lag": 1,
                       "estimator": "Pearson",
                       "entry": "nonpositive-to-positive cross above pivot",
                       "exit_confirm_nonpositive_closes": 2,
                       "max_attempts": 3, "max_hold_sessions": 60},
        "density": {"candidate_rows": len(train_rows),
                    "states": len(train_states), "signals": len(train_signals),
                    "minimum": DENSITY_MIN, "maximum": DENSITY_MAX,
                    "passed": True},
        "chronology": {"train": FIT, "embargo": ["2018-07-01", "2018-12-31"],
                       "validation": VALIDATION,
                       "best_available_frozen_oos": ["2022-01-01", "2026-03-31"]},
        "membership_drops": {"train": train_drops,
                             "validation": validation_drops},
        "train": {"signals": train_signals, "cell": train_cell,
                  "gate": train_gate},
        "validation": validation,
        "open_best_available_oos": bool(validation and validation["gate"]["passed"]),
    }
    json_path = output / f"serial_dependence_lifecycle_{stamp}.json"
    md_path = output / f"serial_dependence_lifecycle_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (train_cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 483–488 — Lag-1 Serial-Dependence Lifecycle", "",
             "Best-available frozen OOS accessed: **NO**", "",
             *_score_table(train_score),
             f"Train signals {len(train_signals)}; trades "
             f"{train_cell['trade_stats']['trades']}; CAGR "
             f"{train_cell['summary']['cagr_pct']:.2f}%; Sharpe "
             f"{(adjusted.get('sharpe') or 0):.3f}; PF "
             f"{(train_cell['trade_stats'].get('profit_factor') or 0):.3f}; "
             f"MDD {train_cell['summary']['max_drawdown_pct']:.2f}%; trim-5 "
             f"expectancy {(train_cell['drop_top_5'].get('expectancy_pct') or 0):.2f}%.", "",
             f"Train gate: **{'PASS' if train_gate['passed'] else 'FAIL'}**", ""]
    lines.extend(f"- {'PASS' if passed else 'FAIL'} — {name}"
                 for name, passed in train_gate["checks"].items())
    lines += ["", f"2019–2021 validation accessed: "
              f"**{'YES' if validation else 'NO'}**", "",
              "2022–2026Q1 best-available OOS remains sealed.", ""]
    md_path.write_text("\n".join(lines))
    if train_raw["trades"]:
        pd.DataFrame(train_raw["trades"]).to_csv(
            output / f"serial_dependence_lifecycle_{stamp}_train_trades.csv", index=False)
        pd.DataFrame(train_raw["equity_curve"]).to_csv(
            output / f"serial_dependence_lifecycle_{stamp}_train_daily.csv", index=False)
    if validation_raw and validation_raw["trades"]:
        pd.DataFrame(validation_raw["trades"]).to_csv(
            output / f"serial_dependence_lifecycle_{stamp}_validation_trades.csv", index=False)
        pd.DataFrame(validation_raw["equity_curve"]).to_csv(
            output / f"serial_dependence_lifecycle_{stamp}_validation_daily.csv", index=False)
    print(json.dumps({"train_signals": len(train_signals),
                      "train_summary": train_cell["summary"],
                      "train_gate": train_gate, "backtest_score": train_score,
                      "validation_accessed": validation is not None,
                      "open_best_available_oos": report["open_best_available_oos"]},
                     indent=2))
    print(json_path); print(md_path)


if __name__ == "__main__":
    main()
