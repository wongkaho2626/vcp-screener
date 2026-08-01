#!/usr/bin/env python3
"""Prespecified Trial 296 SEC dual-growth entry on the internal holdout."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from csv_client import CSVClient
from linear_timing_discovery import (
    CALIBRATION, CALIBRATION_PRICE_END, FIT, FIT_PRICE_END, HOLDOUT,
    build_rows, compact, evaluate, fit_ridge, score_features,
    threshold_from_rows,
)
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import filter_detections, slice_prices
from pullback_followthrough_discovery import holdout_gate
from sec_companyfacts import latest_event_before


def fundamental_signals_with_decay(
    rows: list[dict], model: dict, events_by_symbol: dict[str, list[dict]],
    entry_threshold: float, exit_threshold: float,
) -> list[dict]:
    """Enter on p70 plus fresh dual growth; retain all rows for score exit."""
    by_setup: dict[str, list[dict]] = {}
    for row in rows:
        by_setup.setdefault(row["setup_id"], []).append(row)
    selected = []
    for setup_rows in by_setup.values():
        ordered = sorted(setup_rows, key=lambda value: value["signal_date"])
        entry = event = None
        for row in ordered:
            if score_features(row["features"], model) < entry_threshold:
                continue
            candidate = latest_event_before(
                events_by_symbol.get(row["symbol"], []), row["signal_date"],
            )
            if candidate is None:
                continue
            age = (date.fromisoformat(row["signal_date"])
                   - date.fromisoformat(candidate["filed"])).days
            if (age <= 120 and candidate["eps_growth"] >= .20
                    and candidate["revenue_growth"] >= .10):
                entry, event = row, {**candidate, "age_days": age}
                break
        if entry is None:
            continue
        decay = next(
            (row for row in ordered if row["fill_idx"] > entry["fill_idx"]
             and score_features(row["features"], model) <= exit_threshold),
            None,
        )
        signal = {key: entry[key] for key in (
            "symbol", "sector", "signal_date", "fill_date", "fill_idx",
            "edge_rank", "pattern_stop", "pivot",
        )}
        signal["fundamental_event"] = event
        if decay is not None:
            signal["model_exit_idx"] = decay["fill_idx"]
        selected.append(signal)
    return sorted(selected, key=lambda value: (
        value["fill_date"], -value["edge_rank"], value["symbol"],
    ))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--growth-events-json", required=True)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--output-dir", default="backtests/sec_dual_growth_v2/results")
    ap.add_argument("--iterations", type=int, default=1000)
    args = ap.parse_args()

    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT price coverage/benchmark gate failed")
    events = json.loads(Path(args.growth_events_json).read_text())
    payload = json.loads(Path(args.backtest_json).read_text())
    detections = payload["detections_by_ticker"]
    membership = load_membership(args.membership_csv)
    client = CSVClient(args.price_csv)
    prices_all = {
        row["symbol"]: list(reversed(client.get_historical_prices(
            row["symbol"], days=100_000,
        )["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]
    }

    fit_dets, fit_drops = filter_detections(detections, membership, *FIT)
    fit_rows = build_rows(
        fit_dets, slice_prices(prices_all, FIT[0], FIT_PRICE_END),
        with_labels=True, label_mode="forward20",
    )
    model = fit_ridge(fit_rows)
    calibration_dets, calibration_drops = filter_detections(
        detections, membership, *CALIBRATION,
    )
    calibration_rows = build_rows(
        calibration_dets, slice_prices(prices_all, CALIBRATION[0], CALIBRATION_PRICE_END),
        with_labels=False,
    )
    entry_threshold = threshold_from_rows(calibration_rows, model, 70)
    exit_threshold = threshold_from_rows(calibration_rows, model, 50)
    holdout_dets, holdout_drops = filter_detections(detections, membership, *HOLDOUT)
    holdout_prices = slice_prices(prices_all, *HOLDOUT)
    holdout_rows = build_rows(holdout_dets, holdout_prices, with_labels=False)
    signals = fundamental_signals_with_decay(
        holdout_rows, model, events, entry_threshold, exit_threshold,
    )
    raw_cell = evaluate(
        signals, holdout_prices, args.iterations, exit_rule="model_decay",
        trials_declared=296,
    )
    cell = compact(raw_cell)
    gate = holdout_gate(cell)
    gate["passed"] = all(gate["checks"].values())
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/sec_dual_growth_v2/frozen_spec.md",
        "formal_validation_accessed": False, "untouched_oos_accessed": False,
        "outcome_uses": "fit labels and one prespecified internal holdout only",
        "coverage": coverage, "sec_coverage": {
            "source": "backtests/sec_pit_audit/sec_fundamental_coverage.json",
            "growth_events_symbols": len(events),
        },
        "trials_before": 295, "new_multiplicity_units": 1,
        "trials_after": 296,
        "periods": {"fit": FIT, "calibration": CALIBRATION, "holdout": HOLDOUT},
        "membership_drops": {"fit": fit_drops, "calibration": calibration_drops,
                             "holdout": holdout_drops},
        "model": model, "label_mode": "forward20",
        "entry": {"score_percentile": 70, "score_threshold": entry_threshold,
                  "max_filing_age_days": 120, "min_eps_growth": .20,
                  "min_revenue_growth": .10, "strict_filed_before_signal": True,
                  "same_accession_comparison": True},
        "exit": {"score_percentile": 50, "score_threshold": exit_threshold,
                 "portfolio_rule": "model_decay_with_hard_stop_and_timeout"},
        "calibration": {"rows": len(calibration_rows), "outcomes_used": False},
        "internal_holdout": {"candidate_rows": len(holdout_rows),
                             "selected_signals": len(signals), "signals": signals,
                             "cell": cell, "gate": gate},
        "open_formal_validation": gate["passed"],
    }
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = out / f"sec_dual_growth_{stamp}.json"
    md_path = out / f"sec_dual_growth_{stamp}.md"
    trades_path = out / f"sec_dual_growth_{stamp}_holdout_trades.csv"
    daily_path = out / f"sec_dual_growth_{stamp}_holdout_daily.csv"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 296 — SEC Dual-Growth Discovery", "",
             "Formal validation accessed: **NO**", "",
             f"Signals {len(signals)}; trades {cell['trade_stats']['trades']}; "
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
        pd.DataFrame(raw_cell["trades"]).to_csv(trades_path, index=False)
    if raw_cell["equity_curve"]:
        pd.DataFrame(raw_cell["equity_curve"]).to_csv(daily_path, index=False)
    print(json.dumps({"signals": len(signals), "summary": cell["summary"],
                      "trade_stats": cell["trade_stats"], "gate": gate,
                      "open_formal_validation": gate["passed"]}, indent=2))
    print(json_path); print(md_path)


if __name__ == "__main__":
    main()
