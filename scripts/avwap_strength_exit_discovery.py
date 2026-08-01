#!/usr/bin/env python3
"""Prespecified Trial 455-466 AVWAP reclaim with strength exit."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from anchored_vwap_reclaim_discovery import (
    _period_rows,
    _score_table,
    anchored_states,
)
from cross_sectional_leadership_discovery import discovery_backtest_score
from csv_client import CSVClient
from dmi_crossover_lifecycle_discovery import (
    VALIDATION,
    VALIDATION_PRICE_END,
    VALIDATION_PRICE_START,
)
from linear_timing_discovery import FIT, FIT_PRICE_END, compact, evaluate
from macd_crossover_lifecycle_discovery import DENSITY_MAX, DENSITY_MIN
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import slice_prices
from undercut_reclaim_discovery import gate

TRIALS_BEFORE = 454
TRIALS_AFTER = 466
HIGH_WINDOW = 5
MIN_HOLD = 10


def is_fresh_close_high(bars: list[dict], index: int,
                        window: int = HIGH_WINDOW) -> bool:
    """True when the completed close strictly exceeds prior window-1 closes."""
    if window <= 1:
        raise ValueError("closing-high window must exceed one")
    if index - window + 1 < 0 or index >= len(bars):
        return False
    close = float(bars[index].get("close") or 0)
    priors = [float(bar.get("close") or 0)
              for bar in bars[index - window + 1:index]]
    return close > 0 and all(prior > 0 and close > prior for prior in priors)


def strength_states(rows: list[dict],
                    prices: dict[str, list[dict]]) -> list[dict]:
    """Attach causal fresh-five-day-high state to AVWAP reclaim rows."""
    states = anchored_states(rows, prices)
    return [
        {**row, "fresh_close_high": is_fresh_close_high(
            prices.get(row["symbol"]) or [], int(row["fill_idx"]) - 1)}
        for row in states
    ]


def strength_lifecycle_signals(states: list[dict], max_attempts: int = 3,
                               min_hold: int = MIN_HOLD) -> list[dict]:
    """Emit AVWAP entries and next-open delayed five-day-high exits."""
    if max_attempts <= 0 or min_hold <= 0:
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
                              if ordered[index]["reclaim"]), None)
            if entry_pos is None:
                break
            entry = ordered[entry_pos]
            entry_fill_idx = int(entry["fill_idx"])
            exit_pos = next((
                index for index in range(entry_pos + 1, len(ordered))
                if int(ordered[index]["fill_idx"]) - entry_fill_idx >= min_hold
                and ordered[index]["fresh_close_high"]
            ), None)
            attempts += 1
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


def _write_density_failure(output: Path, stamp: str, coverage: dict,
                           train_rows: list[dict], train_states: list[dict],
                           train_signals: list[dict], train_drops: dict) -> None:
    density = {"candidate_rows": len(train_rows), "states": len(train_states),
               "signals": len(train_signals), "minimum": DENSITY_MIN,
               "maximum": DENSITY_MAX, "passed": False}
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/avwap_strength_exit_v2/frozen_spec.md",
        "oracle_provenance": "backtests/oracle_exit_residual_audit/",
        "data_inventory": "backtests/current_2006_plus_data_audit/inventory.json",
        "return_evaluation_accessed": False,
        "formal_validation_accessed": False,
        "best_available_oos_accessed": False,
        "coverage": coverage, "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": 12, "trials_after": TRIALS_AFTER,
        "density": density, "membership_drops": {"train": train_drops},
        "validation": None, "open_best_available_oos": False,
    }
    json_path = output / f"avwap_strength_exit_{stamp}.json"
    md_path = output / f"avwap_strength_exit_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    md_path.write_text(
        "# Trial 455–466 — AVWAP Reclaim with Delayed Five-Day-High Exit\n\n"
        "Hypothesis provenance: **train-oracle-generated / post-hoc entry-family selection**.\n\n"
        f"Outcome-free density: **{len(train_signals)} signals**; required "
        f"{DENSITY_MIN}–{DENSITY_MAX}.\n\n"
        "Density gate: **FAIL**. No return, validation or best-available OOS "
        "partition was accessed.\n"
    )
    print(json.dumps(density, indent=2)); print(json_path); print(md_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--output-dir", default="backtests/avwap_strength_exit_v2/results")
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
    train_states = strength_states(train_rows, train_prices)
    train_signals = strength_lifecycle_signals(train_states)
    output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    if not DENSITY_MIN <= len(train_signals) <= DENSITY_MAX:
        _write_density_failure(output, stamp, coverage, train_rows, train_states,
                               train_signals, train_drops)
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
        validation_states = strength_states(validation_rows, validation_prices)
        validation_signals = strength_lifecycle_signals(validation_states)
        validation_raw = evaluate(validation_signals, validation_prices,
                                  args.iterations, exit_rule="model_decay",
                                  trials_declared=TRIALS_AFTER)
        validation_cell = compact(validation_raw)
        validation = {"candidate_rows": len(validation_rows),
                      "states": len(validation_states),
                      "signals": validation_signals, "cell": validation_cell,
                      "score": discovery_backtest_score(validation_cell),
                      "gate": gate(validation_cell, 60, 15)}

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/avwap_strength_exit_v2/frozen_spec.md",
        "oracle_provenance": "backtests/oracle_exit_residual_audit/",
        "hypothesis_classification": "train_oracle_generated_post_hoc_entry_selection",
        "data_inventory": "backtests/current_2006_plus_data_audit/inventory.json",
        "backtest_score": train_score,
        "formal_validation_accessed": validation is not None,
        "best_available_oos_accessed": False,
        "coverage": coverage, "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": 12, "trials_after": TRIALS_AFTER,
        "parameters": {"entry": "detection-anchored AVWAP reclaim above pivot",
                       "exit_closing_high_sessions": HIGH_WINDOW,
                       "exit_arm_holding_sessions": MIN_HOLD,
                       "exit": "next open after strict fresh five-day close high",
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
        "train": {"candidate_rows": len(train_rows), "states": len(train_states),
                  "signals": train_signals, "cell": train_cell, "gate": train_gate},
        "validation": validation,
        "open_best_available_oos": bool(validation and validation["gate"]["passed"]),
    }
    json_path = output / f"avwap_strength_exit_{stamp}.json"
    markdown_path = output / f"avwap_strength_exit_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (train_cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 455–466 — AVWAP Reclaim with Delayed Five-Day-High Exit", "",
             "Hypothesis provenance: **train-oracle-generated / post-hoc entry-family selection**.", "",
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
            output / f"avwap_strength_exit_{stamp}_train_trades.csv", index=False)
        pd.DataFrame(train_raw["equity_curve"]).to_csv(
            output / f"avwap_strength_exit_{stamp}_train_daily.csv", index=False)
    if validation_raw and validation_raw["trades"]:
        pd.DataFrame(validation_raw["trades"]).to_csv(
            output / f"avwap_strength_exit_{stamp}_validation_trades.csv", index=False)
        pd.DataFrame(validation_raw["equity_curve"]).to_csv(
            output / f"avwap_strength_exit_{stamp}_validation_daily.csv", index=False)
    print(json.dumps({"train_signals": len(train_signals),
                      "train_summary": train_cell["summary"],
                      "train_gate": train_gate, "backtest_score": train_score,
                      "validation_accessed": validation is not None,
                      "open_best_available_oos": report["open_best_available_oos"]}, indent=2))
    print(json_path); print(markdown_path)


if __name__ == "__main__":
    main()
