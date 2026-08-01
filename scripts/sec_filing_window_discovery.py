#!/usr/bin/env python3
"""Prespecified Trial 303-304 fresh dual-growth SEC filing window."""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from csv_client import CSVClient
from linear_timing_discovery import (
    FIT, FIT_PRICE_END, HOLDOUT, build_rows, compact, evaluate,
)
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import filter_detections, slice_prices
from pullback_followthrough_discovery import holdout_gate
from sec_companyfacts import latest_event_before


def qualifying_event(row: dict, events: dict[str, list[dict]]) -> dict | None:
    event = latest_event_before(events.get(row["symbol"], []), row["signal_date"])
    if event is None:
        return None
    age = (date.fromisoformat(row["signal_date"])
           - date.fromisoformat(event["filed"])).days
    if age > 30 or event["eps_growth"] < .20 or event["revenue_growth"] < .10:
        return None
    return {**event, "age_days": age}


def filing_window_signals(rows: list[dict], events: dict[str, list[dict]]) -> list[dict]:
    by_setup: dict[str, list[dict]] = {}
    for row in rows:
        by_setup.setdefault(row["setup_id"], []).append(row)
    signals = []
    for setup_rows in by_setup.values():
        entry = event = None
        for row in sorted(setup_rows, key=lambda item: item["signal_date"]):
            event = qualifying_event(row, events)
            if event is not None:
                entry = row
                break
        if entry is None:
            continue
        signal = {key: entry[key] for key in (
            "symbol", "sector", "signal_date", "fill_date", "fill_idx",
            "edge_rank", "pattern_stop", "pivot",
        )}
        signal["setup_id"] = entry["setup_id"]
        signal["fundamental_event"] = event
        signal["model_exit_idx"] = entry["fill_idx"] + 20
        signals.append(signal)
    return sorted(signals, key=lambda row: (
        row["fill_date"], -row["edge_rank"], row["symbol"],
    ))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--growth-events-json", required=True)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--output-dir", default="backtests/sec_filing_window_v2/results")
    ap.add_argument("--iterations", type=int, default=1000)
    args = ap.parse_args()
    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/benchmark gate failed")
    events = json.loads(Path(args.growth_events_json).read_text())
    detections = json.loads(Path(args.backtest_json).read_text())["detections_by_ticker"]
    membership = load_membership(args.membership_csv)
    client = CSVClient(args.price_csv)
    prices_all = {
        row["symbol"]: list(reversed(client.get_historical_prices(
            row["symbol"], days=100_000,
        )["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]
    }
    fit_dets, fit_drops = filter_detections(detections, membership, *FIT)
    fit_rows = build_rows(fit_dets, slice_prices(prices_all, FIT[0], FIT_PRICE_END),
                          with_labels=True, label_mode="forward20")
    fit_signals = filing_window_signals(fit_rows, events)
    labels_by_id = {(row["setup_id"], row["signal_date"]): row for row in fit_rows}
    fit_labels = []
    for signal in fit_signals:
        match = labels_by_id[(signal["setup_id"], signal["signal_date"])]
        fit_labels.append(float(match["label"]))
    holdout_dets, holdout_drops = filter_detections(detections, membership, *HOLDOUT)
    holdout_prices = slice_prices(prices_all, *HOLDOUT)
    holdout_rows = build_rows(holdout_dets, holdout_prices, with_labels=False)
    signals = filing_window_signals(holdout_rows, events)
    raw_cell = evaluate(signals, holdout_prices, args.iterations,
                        exit_rule="fixed_time", trials_declared=304)
    cell = compact(raw_cell)
    gate = holdout_gate(cell)
    gate["checks"].pop("trades>=25")
    gate["checks"]["trades>=30"] = cell["trade_stats"]["trades"] >= 30
    gate["passed"] = all(gate["checks"].values())
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/sec_filing_window_v2/frozen_spec.md",
        "formal_validation_accessed": False, "untouched_oos_accessed": False,
        "coverage": coverage, "trials_before": 302,
        "new_multiplicity_units": 2, "trials_after": 304,
        "entry": {"max_filing_age_days": 30, "min_eps_growth": .20,
                  "min_revenue_growth": .10, "strict_filed_before_signal": True,
                  "same_accession_comparison": True},
        "exit": {"fixed_holding_sessions": 20, "next_open": True,
                 "hard_stop_earlier": True},
        "train_evidence": {"period": FIT, "setups": len(fit_labels),
                           "mean_label": statistics.fmean(fit_labels),
                           "median_label": statistics.median(fit_labels),
                           "positive": sum(value > 0 for value in fit_labels)},
        "membership_drops": {"fit": fit_drops, "holdout": holdout_drops},
        "internal_holdout": {"period": HOLDOUT, "candidate_rows": len(holdout_rows),
                             "selected_signals": len(signals), "signals": signals,
                             "cell": cell, "gate": gate},
        "open_formal_validation": gate["passed"],
    }
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = out / f"sec_filing_window_{stamp}.json"
    md_path = out / f"sec_filing_window_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 303–304 — Fresh SEC Filing Window", "",
             "Formal validation accessed: **NO**", "",
             f"Train setups {len(fit_labels)}; mean fixed-20 label "
             f"{statistics.fmean(fit_labels)*100:.2f}%; positive "
             f"{sum(value > 0 for value in fit_labels)}/{len(fit_labels)}.", "",
             f"Holdout signals {len(signals)}; trades {cell['trade_stats']['trades']}; "
             f"CAGR {cell['summary']['cagr_pct']:.2f}%; "
             f"Sharpe {(adjusted.get('sharpe') or 0):.3f}; "
             f"PF {(cell['trade_stats'].get('profit_factor') or 0):.3f}; "
             f"MDD {cell['summary']['max_drawdown_pct']:.2f}%; "
             f"trim-5 expectancy {(cell['drop_top_5'].get('expectancy_pct') or 0):.2f}%.", "",
             f"Gate: **{'PASS' if gate['passed'] else 'FAIL'}**", ""]
    lines.extend(f"- {'PASS' if passed else 'FAIL'} — {name}"
                 for name, passed in gate["checks"].items())
    lines += ["", "Formal validation and untouched OOS remain sealed.", ""]
    md_path.write_text("\n".join(lines))
    if raw_cell["trades"]:
        pd.DataFrame(raw_cell["trades"]).to_csv(
            out / f"sec_filing_window_{stamp}_holdout_trades.csv", index=False,
        )
    if raw_cell["equity_curve"]:
        pd.DataFrame(raw_cell["equity_curve"]).to_csv(
            out / f"sec_filing_window_{stamp}_holdout_daily.csv", index=False,
        )
    print(json.dumps({"train_evidence": report["train_evidence"],
                      "signals": len(signals), "summary": cell["summary"],
                      "trade_stats": cell["trade_stats"], "gate": gate,
                      "open_formal_validation": gate["passed"]}, indent=2))
    print(json_path); print(md_path)


if __name__ == "__main__":
    main()
