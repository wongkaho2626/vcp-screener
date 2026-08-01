#!/usr/bin/env python3
"""Prespecified Trial 352-357 detection-anchored VWAP reclaim lifecycle."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from cross_sectional_leadership_discovery import discovery_backtest_score
from csv_client import CSVClient
from linear_timing_discovery import FIT, FIT_PRICE_END, HOLDOUT, build_rows, compact, evaluate
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import filter_detections, slice_prices
from undercut_reclaim_discovery import gate


def anchored_vwap_series(bars: list[dict], anchor_idx: int) -> list[float | None]:
    """Return a causal expanding typical-price VWAP from ``anchor_idx``."""
    if anchor_idx < 0 or anchor_idx >= len(bars):
        raise ValueError("anchor index is outside the price series")
    values: list[float | None] = [None] * len(bars)
    cumulative_price_volume = 0.0
    cumulative_volume = 0.0
    for index in range(anchor_idx, len(bars)):
        bar = bars[index]
        volume = float(bar.get("volume") or 0)
        typical_price = (
            float(bar.get("high") or 0)
            + float(bar.get("low") or 0)
            + float(bar.get("close") or 0)
        ) / 3
        if volume > 0 and typical_price > 0:
            cumulative_price_volume += typical_price * volume
            cumulative_volume += volume
        if cumulative_volume > 0:
            values[index] = cumulative_price_volume / cumulative_volume
    return values


def reclaim_state(bars: list[dict], avwap: list[float | None], index: int,
                  pivot: float) -> dict[str, bool]:
    """Return the causal AVWAP reclaim-entry and below-AVWAP exit state."""
    if index <= 0 or index >= len(bars) or index >= len(avwap):
        return {"reclaim": False, "below_avwap": False}
    current_avwap = avwap[index]
    prior_avwap = avwap[index - 1]
    close = float(bars[index].get("close") or 0)
    if current_avwap is None:
        return {"reclaim": False, "below_avwap": False}
    below = close < current_avwap
    if prior_avwap is None:
        return {"reclaim": False, "below_avwap": below}
    prior_close = float(bars[index - 1].get("close") or 0)
    reclaim = (prior_close <= prior_avwap
               and close > current_avwap
               and close > pivot)
    return {"reclaim": reclaim, "below_avwap": below}


def anchored_states(rows: list[dict], prices: dict[str, list[dict]]) -> list[dict]:
    """Attach each setup's detection-anchored causal VWAP state to daily rows."""
    cache: dict[tuple[str, str], list[float | None]] = {}
    index_cache: dict[str, dict[str, int]] = {}
    states = []
    for row in rows:
        symbol = row["symbol"]
        as_of = row["as_of_date"]
        bars = prices.get(symbol) or []
        if symbol not in index_cache:
            index_cache[symbol] = {bar["date"]: index for index, bar in enumerate(bars)}
        key = (symbol, as_of)
        if key not in cache:
            anchor_idx = index_cache[symbol].get(as_of)
            cache[key] = (anchored_vwap_series(bars, anchor_idx)
                          if anchor_idx is not None else [None] * len(bars))
        signal_idx = int(row["fill_idx"]) - 1
        state = reclaim_state(bars, cache[key], signal_idx,
                              float(row.get("pivot") or 0))
        states.append({**row, **state})
    return states


def lifecycle_signals(states: list[dict], max_attempts: int = 3,
                      exit_confirm_closes: int = 2) -> list[dict]:
    """Emit fresh AVWAP reclaims and confirmed next-open AVWAP exits."""
    if max_attempts <= 0 or exit_confirm_closes <= 0:
        raise ValueError("lifecycle parameters must be positive")
    by_setup: dict[str, list[dict]] = defaultdict(list)
    for state in states:
        by_setup[state["setup_id"]].append(state)
    signals = []
    for setup_rows in by_setup.values():
        ordered = sorted(setup_rows, key=lambda item: item["signal_date"])
        cursor = 0
        attempts = 0
        while cursor < len(ordered) and attempts < max_attempts:
            entry_pos = next((index for index in range(cursor, len(ordered))
                              if ordered[index]["reclaim"]), None)
            if entry_pos is None:
                break
            exit_pos = None
            for index in range(entry_pos + exit_confirm_closes, len(ordered)):
                window = ordered[index - exit_confirm_closes + 1:index + 1]
                consecutive_rows = all(
                    int(window[offset]["fill_idx"])
                    == int(window[0]["fill_idx"]) + offset
                    for offset in range(len(window))
                )
                if consecutive_rows and all(item["below_avwap"] for item in window):
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


def _period_rows(detections: dict, membership: dict, prices: dict[str, list[dict]],
                 start: str, end: str) -> tuple[list[dict], int]:
    selected, dropped = filter_detections(detections, membership, start, end)
    rows = build_rows(selected, prices, with_labels=False)
    return [row for row in rows if start <= row["signal_date"] <= end], dropped


def _score_table(score: dict) -> list[str]:
    components = score["components"]
    return [
        f"## Backtest Score: {score['final_score']}/100 — {score['band']}", "",
        "Discovery-only reduced-denominator score; it cannot qualify the strategy.", "",
        "| Component | Score | Available max |", "|---|---:|---:|",
        f"| A. Statistical validity | {components['A_statistical_validity']['score']} | 30 |",
        f"| B. Risk-adjusted performance | {components['B_risk_adjusted_performance']['score']} | 25 |",
        f"| C. Robustness (bootstrap only) | {components['C_robustness_computable']['score']} | 8 |",
        f"| D. Trade quality / consistency | {components['D_trade_quality_consistency']['score']} | 20 |",
        f"| **Measured total** | **{score['measured_total']}** | **{score['measured_denominator']}** |",
        f"| **Normalized raw score** | **{score['reduced_denominator_normalized_raw_score']}** | **100** |",
        "| Caps applied | Unresolved survivorship → 20; no formal OOS / WFA → 55 | |",
        f"| **Final score** | **{score['final_score']}** | **100** |", "",
        "WFA efficiency (10 points) and parameter sensitivity (7 points) were unavailable because the train gate failed. Their weight was redistributed under the reduced-denominator rule rather than silently scored as zero. The lower unresolved-survivorship cap then applies to the normalized score.", "",
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--output-dir", default="backtests/anchored_vwap_reclaim_v2/results")
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
    train_states = anchored_states(train_rows, train_prices)
    train_signals = lifecycle_signals(train_states)
    train_raw = evaluate(train_signals, train_prices, args.iterations,
                         exit_rule="model_decay", trials_declared=357)
    train_cell = compact(train_raw)
    train_gate = gate(train_cell, 60, 10)
    backtest_score = discovery_backtest_score(train_cell)

    holdout = None
    holdout_raw = None
    holdout_drops = None
    if train_gate["passed"]:
        holdout_prices = slice_prices(prices_all, *HOLDOUT)
        holdout_rows, holdout_drops = _period_rows(
            detections, membership, holdout_prices, *HOLDOUT,
        )
        holdout_states = anchored_states(holdout_rows, holdout_prices)
        holdout_signals = lifecycle_signals(holdout_states)
        holdout_raw = evaluate(holdout_signals, holdout_prices, args.iterations,
                               exit_rule="model_decay", trials_declared=357)
        holdout_cell = compact(holdout_raw)
        holdout = {"candidate_rows": len(holdout_rows),
                   "anchored_states": len(holdout_states),
                   "signals": holdout_signals, "cell": holdout_cell,
                   "gate": gate(holdout_cell, 60, 15)}

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "backtest_score": backtest_score,
        "family_spec": "backtests/anchored_vwap_reclaim_v2/frozen_spec.md",
        "formal_validation_accessed": False,
        "untouched_oos_accessed": False,
        "internal_holdout_accessed": holdout is not None,
        "coverage": coverage,
        "trials_before": 351,
        "new_multiplicity_units": 6,
        "trials_after": 357,
        "parameters": {"anchor": "setup as_of_date",
                       "price": "(high+low+close)/3",
                       "weight": "daily volume",
                       "entry": "below-to-above AVWAP and above frozen pivot",
                       "exit_confirm_closes": 2,
                       "max_attempts": 3,
                       "max_hold_sessions": 60},
        "membership_drops": {"train": train_drops, "holdout": holdout_drops},
        "train": {"candidate_rows": len(train_rows),
                  "anchored_states": len(train_states),
                  "signals": train_signals, "cell": train_cell,
                  "gate": train_gate},
        "internal_holdout": holdout,
        "open_formal_validation": bool(holdout and holdout["gate"]["passed"]),
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    jp = out / f"anchored_vwap_reclaim_{stamp}.json"
    mp = out / f"anchored_vwap_reclaim_{stamp}.md"
    jp.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (train_cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 352–357 — Detection-Anchored VWAP Reclaim Lifecycle", "",
             "Formal validation accessed: **NO**", "", *_score_table(backtest_score),
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
            out / f"anchored_vwap_reclaim_{stamp}_train_trades.csv", index=False)
        pd.DataFrame(train_raw["equity_curve"]).to_csv(
            out / f"anchored_vwap_reclaim_{stamp}_train_daily.csv", index=False)
    if holdout_raw and holdout_raw["trades"]:
        pd.DataFrame(holdout_raw["trades"]).to_csv(
            out / f"anchored_vwap_reclaim_{stamp}_holdout_trades.csv", index=False)
        pd.DataFrame(holdout_raw["equity_curve"]).to_csv(
            out / f"anchored_vwap_reclaim_{stamp}_holdout_daily.csv", index=False)
    print(json.dumps({"train_signals": len(train_signals),
                      "train_summary": train_cell["summary"],
                      "train_gate": train_gate, "backtest_score": backtest_score,
                      "internal_holdout_accessed": holdout is not None,
                      "open_formal_validation": report["open_formal_validation"]}, indent=2))
    print(jp)
    print(mp)


if __name__ == "__main__":
    main()
