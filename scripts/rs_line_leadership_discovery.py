#!/usr/bin/env python3
"""Prespecified Trial 340-344 relative-strength-line leadership lifecycle."""

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


def relative_strength_series(stock_bars: list[dict], benchmark_bars: list[dict]) -> list[float | None]:
    """Stock/benchmark close using only the latest benchmark date at or before stock date."""
    benchmark = sorted(benchmark_bars, key=lambda row: row["date"])
    pointer = -1
    values: list[float | None] = []
    for stock in sorted(stock_bars, key=lambda row: row["date"]):
        while (pointer + 1 < len(benchmark)
               and benchmark[pointer + 1]["date"] <= stock["date"]):
            pointer += 1
        stock_close = float(stock.get("close") or 0)
        benchmark_close = (float(benchmark[pointer].get("close") or 0)
                           if pointer >= 0 else 0)
        values.append(stock_close / benchmark_close
                      if stock_close > 0 and benchmark_close > 0 else None)
    return values


def rs_states(rows: list[dict], prices: dict[str, list[dict]],
              high_lookback: int = 63, sma_period: int = 20) -> list[dict]:
    """Attach causal RS-line high and joint RS/stock trend state."""
    benchmark = prices.get("SPY") or []
    if not benchmark:
        raise ValueError("SPY benchmark series is required")
    rs_cache = {symbol: relative_strength_series(bars, benchmark)
                for symbol, bars in prices.items() if symbol != "SPY"}
    states = []
    for row in rows:
        bars = prices.get(row["symbol"]) or []
        ratios = rs_cache.get(row["symbol"]) or []
        index = int(row["fill_idx"]) - 1
        if index < max(high_lookback, sma_period - 1) or index >= len(ratios):
            continue
        high_window = ratios[index - high_lookback:index + 1]
        sma_window = ratios[index - sma_period + 1:index + 1]
        if any(value is None for value in high_window) or any(value is None for value in sma_window):
            continue
        current_rs = float(ratios[index])
        rs_sma = sum(float(value) for value in sma_window) / sma_period
        stock_closes = [float(bar.get("close") or 0)
                        for bar in bars[index - sma_period + 1:index + 1]]
        if any(value <= 0 for value in stock_closes):
            continue
        close = stock_closes[-1]
        stock_sma = sum(stock_closes) / sma_period
        states.append({
            **row,
            "relative_strength": current_rs,
            "rs_new_high": current_rs > max(float(value) for value in high_window[:-1]),
            "entry_confirmed": (close > float(row.get("pivot") or 0)
                                and close > stock_sma),
            "below_rs_sma20": current_rs < rs_sma,
            "below_stock_sma20": close < stock_sma,
        })
    return states


def lifecycle_signals(states: list[dict], max_attempts: int = 3) -> list[dict]:
    """Enter RS-line highs and exit only on joint RS/stock SMA20 failure."""
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")
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
                              if ordered[index]["rs_new_high"]
                              and ordered[index]["entry_confirmed"]), None)
            if entry_pos is None:
                break
            entry = ordered[entry_pos]
            exit_pos = next((index for index in range(entry_pos + 1, len(ordered))
                             if ordered[index]["below_rs_sma20"]
                             and ordered[index]["below_stock_sma20"]), None)
            attempts += 1
            signal = {key: entry[key] for key in (
                "symbol", "sector", "signal_date", "fill_date", "fill_idx",
                "edge_rank", "pattern_stop", "pivot",
            )}
            signal.update({"attempt": attempts,
                           "relative_strength": entry.get("relative_strength")})
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
    ap.add_argument("--output-dir", default="backtests/rs_line_leadership_v2/results")
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
    train_states = rs_states(train_rows, train_prices)
    train_signals = lifecycle_signals(train_states)
    train_raw = evaluate(train_signals, train_prices, args.iterations,
                         exit_rule="model_decay", trials_declared=344)
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
        holdout_states = rs_states(holdout_rows, holdout_prices)
        holdout_signals = lifecycle_signals(holdout_states)
        holdout_raw = evaluate(holdout_signals, holdout_prices, args.iterations,
                               exit_rule="model_decay", trials_declared=344)
        holdout_cell = compact(holdout_raw)
        holdout = {"candidate_rows": len(holdout_rows),
                   "rs_states": len(holdout_states),
                   "signals": holdout_signals, "cell": holdout_cell,
                   "gate": gate(holdout_cell, 60, 15)}

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "backtest_score": backtest_score,
        "family_spec": "backtests/rs_line_leadership_v2/frozen_spec.md",
        "formal_validation_accessed": False,
        "untouched_oos_accessed": False,
        "internal_holdout_accessed": holdout is not None,
        "coverage": coverage,
        "trials_before": 339,
        "new_multiplicity_units": 5,
        "trials_after": 344,
        "parameters": {"rs_high_lookback_sessions": 63,
                       "stock_sma_sessions": 20,
                       "rs_sma_sessions": 20,
                       "entry_requires_above_pivot": True,
                       "exit_requires_joint_rs_stock_failure": True,
                       "max_attempts": 3,
                       "max_hold_sessions": 60},
        "membership_drops": {"train": train_drops, "holdout": holdout_drops},
        "train": {"candidate_rows": len(train_rows), "rs_states": len(train_states),
                  "signals": train_signals, "cell": train_cell, "gate": train_gate},
        "internal_holdout": holdout,
        "open_formal_validation": bool(holdout and holdout["gate"]["passed"]),
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    jp = out / f"rs_line_leadership_{stamp}.json"
    mp = out / f"rs_line_leadership_{stamp}.md"
    jp.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (train_cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 340–344 — Relative-Strength-Line Leadership Lifecycle", "",
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
            out / f"rs_line_leadership_{stamp}_train_trades.csv", index=False)
        pd.DataFrame(train_raw["equity_curve"]).to_csv(
            out / f"rs_line_leadership_{stamp}_train_daily.csv", index=False)
    if holdout_raw and holdout_raw["trades"]:
        pd.DataFrame(holdout_raw["trades"]).to_csv(
            out / f"rs_line_leadership_{stamp}_holdout_trades.csv", index=False)
        pd.DataFrame(holdout_raw["equity_curve"]).to_csv(
            out / f"rs_line_leadership_{stamp}_holdout_daily.csv", index=False)
    print(json.dumps({"train_signals": len(train_signals),
                      "train_summary": train_cell["summary"],
                      "train_gate": train_gate, "backtest_score": backtest_score,
                      "internal_holdout_accessed": holdout is not None,
                      "open_formal_validation": report["open_formal_validation"]}, indent=2))
    print(jp)
    print(mp)


if __name__ == "__main__":
    main()
