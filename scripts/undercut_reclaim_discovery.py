#!/usr/bin/env python3
"""Prespecified Trial 305-307 last-contraction undercut-and-rally."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from csv_client import CSVClient
from edge_rank import DEFAULT_W_EXT, DEFAULT_W_RS, SIZING_MIN_EDGE, compute_edge_rank
from linear_timing_discovery import FIT, FIT_PRICE_END, HOLDOUT, compact, evaluate
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import filter_detections, slice_prices
from portfolio_backtest import _as_of_pattern_levels


def undercut_signals(detections: dict, prices: dict[str, list[dict]]) -> list[dict]:
    edges = compute_edge_rank(detections, DEFAULT_W_RS, DEFAULT_W_EXT)
    signals = []
    for symbol, symbol_detections in detections.items():
        bars = prices.get(symbol) or []
        index = {bar["date"]: i for i, bar in enumerate(bars)}
        for detection in symbol_detections:
            as_of = detection.get("as_of_date")
            as_of_idx = index.get(as_of)
            levels = _as_of_pattern_levels(detection)
            edge = (edges.get((symbol, as_of)) or {}).get("edge_rank")
            if as_of_idx is None or levels is None or edge is None or edge < SIZING_MIN_EDGE:
                continue
            pivot, original_stop = levels
            if float(bars[as_of_idx].get("close") or 0) < original_stop:
                continue
            terminal = min(as_of_idx + 60, len(bars) - 2)
            for i in range(as_of_idx, terminal + 1):
                bar = bars[i]
                close = float(bar.get("close") or 0)
                if close < original_stop:
                    break
                low = float(bar.get("low") or close)
                high = float(bar.get("high") or close)
                depth = low / original_stop - 1 if original_stop > 0 else 0
                clv = (close - low) / (high - low) if high > low else .5
                if not (-.02 <= depth < 0 and close >= original_stop and clv >= .50):
                    continue
                signals.append({
                    "symbol": symbol, "sector": detection.get("sector") or "Unknown",
                    "signal_date": bar["date"], "fill_date": bars[i + 1]["date"],
                    "fill_idx": i + 1, "edge_rank": edge,
                    "pattern_stop": low, "pivot": pivot,
                    "model_exit_idx": i + 1 + 20,
                    "original_pattern_stop": original_stop,
                    "undercut_depth": depth, "clv": clv,
                })
                break
    return sorted(signals, key=lambda row: (
        row["fill_date"], -row["edge_rank"], row["symbol"],
    ))


def gate(cell: dict, min_trades: int, min_cagr: float) -> dict:
    stats = cell["trade_stats"]
    adjusted = (cell.get("robustness") or {}).get("risk_adjusted") or {}
    checks = {
        f"trades>={min_trades}": stats["trades"] >= min_trades,
        f"cagr>={min_cagr:g}pct": cell["summary"]["cagr_pct"] >= min_cagr,
        "sharpe>=0.75": (adjusted.get("sharpe") or 0) >= .75,
        "pf>1.20": (stats.get("profit_factor") or 0) > 1.20,
        "mdd>-15pct": cell["summary"]["max_drawdown_pct"] > -15,
        "drop_top_5_expectancy>0": (cell["drop_top_5"].get("expectancy_pct") or 0) > 0,
    }
    return {"passed": all(checks.values()), "checks": checks}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--output-dir", default="backtests/undercut_reclaim_v2/results")
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
    train_dets, train_drops = filter_detections(detections, membership, *FIT)
    train_prices = slice_prices(prices_all, FIT[0], FIT_PRICE_END)
    train_signals = undercut_signals(train_dets, train_prices)
    train_raw = evaluate(train_signals, train_prices, args.iterations,
                         exit_rule="fixed_time", trials_declared=307)
    train_cell = compact(train_raw); train_gate = gate(train_cell, 20, 10)
    holdout = None; holdout_raw = None; holdout_drops = None
    if train_gate["passed"]:
        holdout_dets, holdout_drops = filter_detections(detections, membership, *HOLDOUT)
        holdout_prices = slice_prices(prices_all, *HOLDOUT)
        holdout_signals = undercut_signals(holdout_dets, holdout_prices)
        holdout_raw = evaluate(holdout_signals, holdout_prices, args.iterations,
                               exit_rule="fixed_time", trials_declared=307)
        holdout_cell = compact(holdout_raw)
        holdout = {"signals": holdout_signals, "cell": holdout_cell,
                   "gate": gate(holdout_cell, 30, 15)}
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/undercut_reclaim_v2/frozen_spec.md",
        "formal_validation_accessed": False, "untouched_oos_accessed": False,
        "internal_holdout_accessed": holdout is not None,
        "coverage": coverage, "trials_before": 304,
        "new_multiplicity_units": 3, "trials_after": 307,
        "parameters": {"max_undercut_pct": 2, "min_clv": .5,
                       "time_exit_sessions": 20, "next_open": True,
                       "stop": "shakeout low bounded by unchanged 8% risk cap"},
        "membership_drops": {"train": train_drops, "holdout": holdout_drops},
        "train": {"signal_period": FIT, "price_end": FIT_PRICE_END,
                  "signals": train_signals, "cell": train_cell, "gate": train_gate},
        "internal_holdout": holdout,
        "open_formal_validation": bool(holdout and holdout["gate"]["passed"]),
    }
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    jp = out / f"undercut_reclaim_{stamp}.json"
    mp = out / f"undercut_reclaim_{stamp}.md"
    jp.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (train_cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 305–307 — Undercut and Rally", "",
             "Formal validation accessed: **NO**", "",
             f"Train signals {len(train_signals)}; trades {train_cell['trade_stats']['trades']}; "
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
            out / f"undercut_reclaim_{stamp}_train_trades.csv", index=False)
    if train_raw["equity_curve"]:
        pd.DataFrame(train_raw["equity_curve"]).to_csv(
            out / f"undercut_reclaim_{stamp}_train_daily.csv", index=False)
    if holdout_raw and holdout_raw["trades"]:
        pd.DataFrame(holdout_raw["trades"]).to_csv(
            out / f"undercut_reclaim_{stamp}_holdout_trades.csv", index=False)
        pd.DataFrame(holdout_raw["equity_curve"]).to_csv(
            out / f"undercut_reclaim_{stamp}_holdout_daily.csv", index=False)
    print(json.dumps({"train_signals": len(train_signals),
                      "train_summary": train_cell["summary"], "train_gate": train_gate,
                      "internal_holdout_accessed": holdout is not None,
                      "open_formal_validation": report["open_formal_validation"]}, indent=2))
    print(jp); print(mp)


if __name__ == "__main__":
    main()
