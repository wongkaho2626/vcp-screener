#!/usr/bin/env python3
"""Prespecified Trial 363-367 Wilder DMI crossover lifecycle."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from anchored_vwap_reclaim_discovery import _period_rows, _score_table
from cross_sectional_leadership_discovery import discovery_backtest_score
from csv_client import CSVClient
from linear_timing_discovery import FIT, FIT_PRICE_END, compact, evaluate
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import slice_prices
from undercut_reclaim_discovery import gate

VALIDATION = ("2019-01-01", "2021-12-31")
VALIDATION_PRICE_START = "2017-01-01"
VALIDATION_PRICE_END = "2022-03-31"


def wilder_average(values: list[float], period: int) -> list[float | None]:
    """Causal Wilder moving average with an arithmetic seed."""
    if period <= 0:
        raise ValueError("Wilder period must be positive")
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    current = sum(values[:period]) / period
    result[period - 1] = current
    for index in range(period, len(values)):
        current = (current * (period - 1) + values[index]) / period
        result[index] = current
    return result


def dmi_series(bars: list[dict], period: int = 14
               ) -> tuple[list[float | None], list[float | None]]:
    """Return causal Wilder +DI and -DI aligned to daily bars."""
    if period <= 0:
        raise ValueError("DMI period must be positive")
    true_range = [0.0] * len(bars)
    positive_dm = [0.0] * len(bars)
    negative_dm = [0.0] * len(bars)
    for index in range(1, len(bars)):
        current = bars[index]
        prior = bars[index - 1]
        high = float(current.get("high") or 0)
        low = float(current.get("low") or 0)
        prior_high = float(prior.get("high") or 0)
        prior_low = float(prior.get("low") or 0)
        prior_close = float(prior.get("close") or 0)
        true_range[index] = max(high - low, abs(high - prior_close),
                                abs(low - prior_close))
        up_move = high - prior_high
        down_move = prior_low - low
        positive_dm[index] = up_move if up_move > down_move and up_move > 0 else 0.0
        negative_dm[index] = down_move if down_move > up_move and down_move > 0 else 0.0
    smoothed_tr = wilder_average(true_range[1:], period)
    smoothed_positive = wilder_average(positive_dm[1:], period)
    smoothed_negative = wilder_average(negative_dm[1:], period)
    plus_di: list[float | None] = [None] * len(bars)
    minus_di: list[float | None] = [None] * len(bars)
    for offset, atr in enumerate(smoothed_tr, start=1):
        if atr is not None and atr > 0:
            plus_di[offset] = 100 * float(smoothed_positive[offset - 1]) / atr
            minus_di[offset] = 100 * float(smoothed_negative[offset - 1]) / atr
    return plus_di, minus_di


def directional_state(bars: list[dict], plus_di: list[float | None],
                      minus_di: list[float | None], index: int,
                      pivot: float) -> dict[str, bool]:
    """Return causal positive-cross entry and negative-dominance exit state."""
    if index <= 0 or index >= len(bars):
        return {"positive_cross": False, "negative_dominance": False}
    current_plus = plus_di[index]
    current_minus = minus_di[index]
    prior_plus = plus_di[index - 1]
    prior_minus = minus_di[index - 1]
    if current_plus is None or current_minus is None:
        return {"positive_cross": False, "negative_dominance": False}
    negative = current_plus < current_minus
    close = float(bars[index].get("close") or 0)
    cross = bool(prior_plus is not None and prior_minus is not None
                 and prior_plus <= prior_minus
                 and current_plus > current_minus and close > pivot)
    return {"positive_cross": cross, "negative_dominance": negative}


def dmi_states(rows: list[dict], prices: dict[str, list[dict]],
               period: int = 14) -> list[dict]:
    cache = {symbol: dmi_series(bars, period) for symbol, bars in prices.items()
             if symbol != "SPY"}
    states = []
    for row in rows:
        bars = prices.get(row["symbol"]) or []
        plus_di, minus_di = cache.get(row["symbol"], ([], []))
        state = directional_state(bars, plus_di, minus_di,
                                  int(row["fill_idx"]) - 1,
                                  float(row.get("pivot") or 0))
        states.append({**row, **state})
    return states


def lifecycle_signals(states: list[dict], max_attempts: int = 3,
                      exit_confirm_closes: int = 2) -> list[dict]:
    """Emit next-open DMI entries and confirmed next-open reverse exits."""
    if max_attempts <= 0 or exit_confirm_closes <= 0:
        raise ValueError("lifecycle parameters must be positive")
    grouped: dict[str, list[dict]] = defaultdict(list)
    for state in states:
        grouped[state["setup_id"]].append(state)
    signals = []
    for setup_rows in grouped.values():
        ordered = sorted(setup_rows, key=lambda item: item["signal_date"])
        cursor = attempts = 0
        while cursor < len(ordered) and attempts < max_attempts:
            entry_pos = next((index for index in range(cursor, len(ordered))
                              if ordered[index]["positive_cross"]), None)
            if entry_pos is None:
                break
            exit_pos = None
            for index in range(entry_pos + exit_confirm_closes, len(ordered)):
                window = ordered[index - exit_confirm_closes + 1:index + 1]
                consecutive = all(int(window[offset]["fill_idx"])
                                  == int(window[0]["fill_idx"]) + offset
                                  for offset in range(len(window)))
                if consecutive and all(item["negative_dominance"] for item in window):
                    exit_pos = index
                    break
            attempts += 1
            entry = ordered[entry_pos]
            signal = {key: entry[key] for key in (
                "symbol", "sector", "signal_date", "fill_date", "fill_idx",
                "edge_rank", "pattern_stop", "pivot",
            )}
            signal["attempt"] = attempts
            if exit_pos is not None:
                signal["model_exit_idx"] = ordered[exit_pos]["fill_idx"]
                cursor = exit_pos + 1
            else:
                cursor = len(ordered)
            signals.append(signal)
    return sorted(signals, key=lambda row: (
        row["fill_date"], -row["edge_rank"], row["symbol"],
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--output-dir", default="backtests/dmi_crossover_lifecycle_v2/results")
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
    train_states = dmi_states(train_rows, train_prices)
    train_signals = lifecycle_signals(train_states)
    train_raw = evaluate(train_signals, train_prices, args.iterations,
                         exit_rule="model_decay", trials_declared=367)
    train_cell = compact(train_raw)
    train_gate = gate(train_cell, 60, 10)
    train_score = discovery_backtest_score(train_cell)

    validation = validation_raw = validation_drops = None
    if train_gate["passed"]:
        validation_prices = slice_prices(
            prices_all, VALIDATION_PRICE_START, VALIDATION_PRICE_END)
        validation_rows, validation_drops = _period_rows(
            detections, membership, validation_prices, *VALIDATION)
        validation_states = dmi_states(validation_rows, validation_prices)
        validation_signals = lifecycle_signals(validation_states)
        validation_raw = evaluate(validation_signals, validation_prices, args.iterations,
                                  exit_rule="model_decay", trials_declared=367)
        validation_cell = compact(validation_raw)
        validation = {"candidate_rows": len(validation_rows),
                      "states": len(validation_states),
                      "signals": validation_signals, "cell": validation_cell,
                      "score": discovery_backtest_score(validation_cell),
                      "gate": gate(validation_cell, 60, 15)}

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/dmi_crossover_lifecycle_v2/frozen_spec.md",
        "data_inventory": "backtests/current_2006_plus_data_audit/inventory.json",
        "backtest_score": train_score,
        "formal_validation_accessed": validation is not None,
        "best_available_oos_accessed": False,
        "coverage": coverage,
        "trials_before": 362, "new_multiplicity_units": 5, "trials_after": 367,
        "parameters": {"dmi_period": 14, "entry": "+DI cross above -DI and pivot",
                       "exit_confirm_negative_dominance_closes": 2,
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
    json_path = output / f"dmi_crossover_lifecycle_{stamp}.json"
    markdown_path = output / f"dmi_crossover_lifecycle_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (train_cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 363–367 — Wilder DMI Crossover Lifecycle", "",
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
            output / f"dmi_crossover_lifecycle_{stamp}_train_trades.csv", index=False)
        pd.DataFrame(train_raw["equity_curve"]).to_csv(
            output / f"dmi_crossover_lifecycle_{stamp}_train_daily.csv", index=False)
    if validation_raw and validation_raw["trades"]:
        pd.DataFrame(validation_raw["trades"]).to_csv(
            output / f"dmi_crossover_lifecycle_{stamp}_validation_trades.csv", index=False)
        pd.DataFrame(validation_raw["equity_curve"]).to_csv(
            output / f"dmi_crossover_lifecycle_{stamp}_validation_daily.csv", index=False)
    print(json.dumps({"train_signals": len(train_signals),
                      "train_summary": train_cell["summary"], "train_gate": train_gate,
                      "backtest_score": train_score,
                      "validation_accessed": validation is not None,
                      "open_best_available_oos": report["open_best_available_oos"]}, indent=2))
    print(json_path); print(markdown_path)


if __name__ == "__main__":
    main()
