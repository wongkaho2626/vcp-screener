#!/usr/bin/env python3
"""Prespecified Trial 358-362 Chaikin Money Flow reclaim lifecycle."""

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
from linear_timing_discovery import FIT, FIT_PRICE_END, HOLDOUT, compact, evaluate
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import slice_prices
from undercut_reclaim_discovery import gate


def cmf_series(bars: list[dict], period: int = 20) -> list[float | None]:
    """Return causal Chaikin Money Flow values for complete rolling windows."""
    if period <= 0:
        raise ValueError("CMF period must be positive")
    flows: list[tuple[float, float]] = []
    values: list[float | None] = []
    for index, bar in enumerate(bars):
        high = float(bar.get("high") or 0)
        low = float(bar.get("low") or 0)
        close = float(bar.get("close") or 0)
        volume = float(bar.get("volume") or 0)
        multiplier = ((2 * close - high - low) / (high - low)
                      if high > low else 0.0)
        flows.append((multiplier * max(0.0, volume), max(0.0, volume)))
        if index < period - 1:
            values.append(None)
            continue
        window = flows[index - period + 1:index + 1]
        total_volume = sum(item[1] for item in window)
        values.append(sum(item[0] for item in window) / total_volume
                      if total_volume > 0 else None)
    return values


def money_flow_state(bars: list[dict], cmf: list[float | None], index: int,
                     pivot: float) -> dict[str, bool]:
    """Return causal CMF zero-cross entry and negative-CMF exit states."""
    if index <= 0 or index >= len(bars) or index >= len(cmf):
        return {"accumulation_cross": False, "negative_cmf": False}
    current = cmf[index]
    prior = cmf[index - 1]
    if current is None:
        return {"accumulation_cross": False, "negative_cmf": False}
    negative = current < 0
    close = float(bars[index].get("close") or 0)
    cross = bool(prior is not None and prior <= 0 < current and close > pivot)
    return {"accumulation_cross": cross, "negative_cmf": negative}


def money_flow_states(rows: list[dict], prices: dict[str, list[dict]],
                      period: int = 20) -> list[dict]:
    cache = {symbol: cmf_series(bars, period) for symbol, bars in prices.items()
             if symbol != "SPY"}
    states = []
    for row in rows:
        bars = prices.get(row["symbol"]) or []
        state = money_flow_state(bars, cache.get(row["symbol"]) or [],
                                 int(row["fill_idx"]) - 1,
                                 float(row.get("pivot") or 0))
        states.append({**row, **state})
    return states


def lifecycle_signals(states: list[dict], max_attempts: int = 3,
                      exit_confirm_closes: int = 2) -> list[dict]:
    if max_attempts <= 0 or exit_confirm_closes <= 0:
        raise ValueError("lifecycle parameters must be positive")
    by_setup: dict[str, list[dict]] = defaultdict(list)
    for state in states:
        by_setup[state["setup_id"]].append(state)
    signals = []
    for setup_rows in by_setup.values():
        ordered = sorted(setup_rows, key=lambda item: item["signal_date"])
        cursor = attempts = 0
        while cursor < len(ordered) and attempts < max_attempts:
            entry_pos = next((i for i in range(cursor, len(ordered))
                              if ordered[i]["accumulation_cross"]), None)
            if entry_pos is None:
                break
            exit_pos = None
            for i in range(entry_pos + exit_confirm_closes, len(ordered)):
                window = ordered[i - exit_confirm_closes + 1:i + 1]
                consecutive = all(int(window[j]["fill_idx"])
                                  == int(window[0]["fill_idx"]) + j
                                  for j in range(len(window)))
                if consecutive and all(item["negative_cmf"] for item in window):
                    exit_pos = i
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--output-dir", default="backtests/chaikin_money_flow_v2/results")
    ap.add_argument("--iterations", type=int, default=1000)
    args = ap.parse_args()
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
    train_states = money_flow_states(train_rows, train_prices)
    train_signals = lifecycle_signals(train_states)
    train_raw = evaluate(train_signals, train_prices, args.iterations,
                         exit_rule="model_decay", trials_declared=362)
    train_cell = compact(train_raw)
    train_gate = gate(train_cell, 60, 10)
    score = discovery_backtest_score(train_cell)
    holdout = holdout_raw = holdout_drops = None
    if train_gate["passed"]:
        holdout_prices = slice_prices(prices_all, *HOLDOUT)
        holdout_rows, holdout_drops = _period_rows(
            detections, membership, holdout_prices, *HOLDOUT)
        holdout_states = money_flow_states(holdout_rows, holdout_prices)
        holdout_signals = lifecycle_signals(holdout_states)
        holdout_raw = evaluate(holdout_signals, holdout_prices, args.iterations,
                               exit_rule="model_decay", trials_declared=362)
        holdout_cell = compact(holdout_raw)
        holdout = {"candidate_rows": len(holdout_rows), "states": len(holdout_states),
                   "signals": holdout_signals, "cell": holdout_cell,
                   "gate": gate(holdout_cell, 60, 15)}
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "backtest_score": score,
        "family_spec": "backtests/chaikin_money_flow_v2/frozen_spec.md",
        "formal_validation_accessed": False, "untouched_oos_accessed": False,
        "internal_holdout_accessed": holdout is not None, "coverage": coverage,
        "trials_before": 357, "new_multiplicity_units": 5, "trials_after": 362,
        "parameters": {"cmf_period": 20, "entry_cross": "<=0 to >0",
                       "entry_above_frozen_pivot": True,
                       "exit_confirm_negative_closes": 2, "max_attempts": 3,
                       "max_hold_sessions": 60},
        "membership_drops": {"train": train_drops, "holdout": holdout_drops},
        "train": {"candidate_rows": len(train_rows), "states": len(train_states),
                  "signals": train_signals, "cell": train_cell, "gate": train_gate},
        "internal_holdout": holdout,
        "open_formal_validation": bool(holdout and holdout["gate"]["passed"]),
    }
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    jp = out / f"chaikin_money_flow_{stamp}.json"
    mp = out / f"chaikin_money_flow_{stamp}.md"
    jp.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (train_cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 358–362 — Chaikin Money Flow Reclaim Lifecycle", "",
             "Formal validation accessed: **NO**", "", *_score_table(score),
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
    lines += ["", f"Internal holdout accessed: **{'YES' if holdout else 'NO'}**", "",
              "Formal validation and untouched OOS remain sealed.", ""]
    mp.write_text("\n".join(lines))
    if train_raw["trades"]:
        pd.DataFrame(train_raw["trades"]).to_csv(
            out / f"chaikin_money_flow_{stamp}_train_trades.csv", index=False)
        pd.DataFrame(train_raw["equity_curve"]).to_csv(
            out / f"chaikin_money_flow_{stamp}_train_daily.csv", index=False)
    if holdout_raw and holdout_raw["trades"]:
        pd.DataFrame(holdout_raw["trades"]).to_csv(
            out / f"chaikin_money_flow_{stamp}_holdout_trades.csv", index=False)
        pd.DataFrame(holdout_raw["equity_curve"]).to_csv(
            out / f"chaikin_money_flow_{stamp}_holdout_daily.csv", index=False)
    print(json.dumps({"train_signals": len(train_signals),
                      "train_summary": train_cell["summary"], "train_gate": train_gate,
                      "backtest_score": score,
                      "internal_holdout_accessed": holdout is not None,
                      "open_formal_validation": report["open_formal_validation"]}, indent=2))
    print(jp); print(mp)


if __name__ == "__main__":
    main()
