#!/usr/bin/env python3
"""Prespecified Trial 441-447 realized-semivariance lifecycle."""

from __future__ import annotations

import argparse
import json
import math
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

TRIALS_BEFORE = 440
TRIALS_AFTER = 447
RETURN_PERIOD = 20
ENTRY_RATIO = 1.50
EXIT_RATIO = .75


def semivariance_ratio(bars: list[dict], index: int,
                       period: int = RETURN_PERIOD,
                       ) -> tuple[float, float, float] | None:
    """Return causal upside energy, downside energy and their ratio."""
    if period <= 0:
        raise ValueError("return period must be positive")
    start = index - period
    if start < 0 or index >= len(bars):
        return None
    closes = [float(bar.get("close") or 0)
              for bar in bars[start:index + 1]]
    if any(close <= 0 for close in closes):
        return None
    returns = [closes[offset] / closes[offset - 1] - 1
               for offset in range(1, len(closes))]
    upside = sum(value * value for value in returns if value > 0)
    downside = sum(value * value for value in returns if value < 0)
    if upside == 0 and downside == 0:
        return None
    ratio = math.inf if downside == 0 else upside / downside
    return upside, downside, ratio


def semivariance_state(bars: list[dict], index: int, pivot: float,
                       period: int = RETURN_PERIOD,
                       entry_ratio: float = ENTRY_RATIO,
                       exit_ratio: float = EXIT_RATIO,
                       ) -> dict[str, bool | float | None]:
    """Return causal upside-asymmetry entry and downside failure state."""
    if not 0 <= exit_ratio < 1 < entry_ratio:
        raise ValueError("invalid semivariance ratio thresholds")
    values = semivariance_ratio(bars, index, period)
    if values is None:
        return {"positive_cross": False, "negative_dominance": False,
                "upside_energy": None, "downside_energy": None,
                "semivariance_ratio": None}
    upside, downside, ratio = values
    close = float(bars[index].get("close") or 0)
    return {"positive_cross": ratio >= entry_ratio and close > pivot,
            "negative_dominance": ratio < exit_ratio,
            "upside_energy": upside, "downside_energy": downside,
            "semivariance_ratio": ratio}


def semivariance_states(rows: list[dict],
                        prices: dict[str, list[dict]]) -> list[dict]:
    states = []
    for row in rows:
        bars = prices.get(row["symbol"]) or []
        state = semivariance_state(bars, int(row["fill_idx"]) - 1,
                                   float(row.get("pivot") or 0))
        states.append({**row, **state})
    return states


def _write_density_failure(output: Path, stamp: str, coverage: dict,
                           train_rows: list[dict], train_states: list[dict],
                           train_signals: list[dict], train_drops: dict) -> None:
    density = {"candidate_rows": len(train_rows), "states": len(train_states),
               "signals": len(train_signals), "minimum": DENSITY_MIN,
               "maximum": DENSITY_MAX, "passed": False}
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/semivariance_asymmetry_lifecycle_v2/frozen_spec.md",
        "data_inventory": "backtests/current_2006_plus_data_audit/inventory.json",
        "return_evaluation_accessed": False,
        "formal_validation_accessed": False,
        "best_available_oos_accessed": False,
        "coverage": coverage, "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": 7, "trials_after": TRIALS_AFTER,
        "density": density, "membership_drops": {"train": train_drops},
        "validation": None, "open_best_available_oos": False,
    }
    json_path = output / f"semivariance_asymmetry_lifecycle_{stamp}.json"
    md_path = output / f"semivariance_asymmetry_lifecycle_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    md_path.write_text(
        "# Trial 441–447 — Realized Semivariance Asymmetry Lifecycle\n\n"
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
    parser.add_argument("--output-dir",
                        default="backtests/semivariance_asymmetry_lifecycle_v2/results")
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
    train_states = semivariance_states(train_rows, train_prices)
    train_signals = lifecycle_signals(train_states)
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
        validation_states = semivariance_states(validation_rows, validation_prices)
        validation_signals = lifecycle_signals(validation_states)
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
        "family_spec": "backtests/semivariance_asymmetry_lifecycle_v2/frozen_spec.md",
        "data_inventory": "backtests/current_2006_plus_data_audit/inventory.json",
        "backtest_score": train_score,
        "formal_validation_accessed": validation is not None,
        "best_available_oos_accessed": False,
        "coverage": coverage, "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": 7, "trials_after": TRIALS_AFTER,
        "parameters": {"return_sessions": RETURN_PERIOD,
                       "entry_upside_downside_ratio": ENTRY_RATIO,
                       "exit_upside_downside_ratio": EXIT_RATIO,
                       "entry": "upside semivariance dominance above pivot",
                       "exit_confirm_downside_dominance_closes": 2,
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
    json_path = output / f"semivariance_asymmetry_lifecycle_{stamp}.json"
    markdown_path = output / f"semivariance_asymmetry_lifecycle_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (train_cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 441–447 — Realized Semivariance Asymmetry Lifecycle", "",
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
            output / f"semivariance_asymmetry_lifecycle_{stamp}_train_trades.csv", index=False)
        pd.DataFrame(train_raw["equity_curve"]).to_csv(
            output / f"semivariance_asymmetry_lifecycle_{stamp}_train_daily.csv", index=False)
    if validation_raw and validation_raw["trades"]:
        pd.DataFrame(validation_raw["trades"]).to_csv(
            output / f"semivariance_asymmetry_lifecycle_{stamp}_validation_trades.csv", index=False)
        pd.DataFrame(validation_raw["equity_curve"]).to_csv(
            output / f"semivariance_asymmetry_lifecycle_{stamp}_validation_daily.csv", index=False)
    print(json.dumps({"train_signals": len(train_signals),
                      "train_summary": train_cell["summary"],
                      "train_gate": train_gate, "backtest_score": train_score,
                      "validation_accessed": validation is not None,
                      "open_best_available_oos": report["open_best_available_oos"]}, indent=2))
    print(json_path); print(markdown_path)


if __name__ == "__main__":
    main()
