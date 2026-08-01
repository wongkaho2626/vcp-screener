#!/usr/bin/env python3
"""Prespecified Trial 300-302 setup-balanced nearest-analogue model."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from csv_client import CSVClient
from linear_timing_discovery import (
    CALIBRATION, CALIBRATION_PRICE_END, FEATURE_NAMES, FIT, FIT_PRICE_END,
    HOLDOUT, build_rows, compact, evaluate,
)
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import filter_detections, slice_prices
from pullback_followthrough_discovery import holdout_gate


def fit_analogue_model(rows: list[dict], k: int = 15) -> dict:
    x = np.asarray([row["features"] for row in rows], dtype=float)
    mean = x.mean(axis=0); std = x.std(axis=0); std[std == 0] = 1
    z = (x - mean) / std
    setup_names = sorted({row["setup_id"] for row in rows})
    setup_index = {name: i for i, name in enumerate(setup_names)}
    groups = []
    for name in setup_names:
        indices = np.asarray([i for i, row in enumerate(rows)
                              if row["setup_id"] == name], dtype=int)
        groups.append((z[indices], np.asarray([rows[i]["label"] for i in indices])))
    digest = hashlib.sha256(
        np.ascontiguousarray(np.column_stack([x, [row["label"] for row in rows]])).tobytes()
    ).hexdigest()
    return {"model_type": "setup_balanced_knn", "k": k, "mean": mean,
            "std": std, "groups": groups, "fit_rows": len(rows),
            "fit_setups": len(setup_names), "feature_names": list(FEATURE_NAMES),
            "training_matrix_sha256": digest, "setup_index": setup_index}


def analogue_score(features: list[float], model: dict) -> float:
    z = (np.asarray(features, dtype=float) - model["mean"]) / model["std"]
    nearest = []
    for group_x, group_y in model["groups"]:
        distances = np.sum((group_x - z) ** 2, axis=1)
        index = int(np.argmin(distances))
        nearest.append((float(distances[index]), float(group_y[index])))
    nearest.sort(key=lambda item: item[0])
    return float(np.mean([label for _, label in nearest[:model["k"]]]))


def score_rows(rows: list[dict], model: dict) -> list[dict]:
    return [{**row, "analogue_score": analogue_score(row["features"], model)}
            for row in rows]


def analogue_signals(rows: list[dict], entry_threshold: float,
                     exit_threshold: float) -> list[dict]:
    by_setup: dict[str, list[dict]] = {}
    for row in rows:
        by_setup.setdefault(row["setup_id"], []).append(row)
    signals = []
    for setup_rows in by_setup.values():
        ordered = sorted(setup_rows, key=lambda row: row["signal_date"])
        entry = next((row for row in ordered
                      if row["analogue_score"] >= entry_threshold), None)
        if entry is None:
            continue
        decay = next((row for row in ordered
                      if row["fill_idx"] > entry["fill_idx"]
                      and row["analogue_score"] <= exit_threshold), None)
        signal = {key: entry[key] for key in (
            "symbol", "sector", "signal_date", "fill_date", "fill_idx",
            "edge_rank", "pattern_stop", "pivot",
        )}
        signal["entry_score"] = entry["analogue_score"]
        if decay is not None:
            signal["model_exit_idx"] = decay["fill_idx"]
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
    ap.add_argument("--output-dir", default="backtests/forward20_knn_v2/results")
    ap.add_argument("--iterations", type=int, default=1000)
    args = ap.parse_args()
    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/benchmark gate failed")
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
    model = fit_analogue_model(fit_rows, k=15)
    cal_dets, cal_drops = filter_detections(detections, membership, *CALIBRATION)
    cal_rows = score_rows(build_rows(
        cal_dets, slice_prices(prices_all, CALIBRATION[0], CALIBRATION_PRICE_END),
        with_labels=False,
    ), model)
    entry_threshold = float(np.percentile([row["analogue_score"] for row in cal_rows], 80))
    exit_threshold = float(np.percentile([row["analogue_score"] for row in cal_rows], 50))
    holdout_dets, holdout_drops = filter_detections(detections, membership, *HOLDOUT)
    holdout_prices = slice_prices(prices_all, *HOLDOUT)
    holdout_rows = score_rows(build_rows(holdout_dets, holdout_prices,
                                         with_labels=False), model)
    signals = analogue_signals(holdout_rows, entry_threshold, exit_threshold)
    raw_cell = evaluate(signals, holdout_prices, args.iterations,
                        exit_rule="model_decay", trials_declared=302)
    cell = compact(raw_cell)
    gate = holdout_gate(cell)
    gate["checks"].pop("trades>=25")
    gate["checks"]["trades>=40"] = cell["trade_stats"]["trades"] >= 40
    gate["passed"] = all(gate["checks"].values())
    public_model = {key: model[key] for key in (
        "model_type", "k", "fit_rows", "fit_setups", "feature_names",
        "training_matrix_sha256",
    )}
    public_model["mean"] = model["mean"].tolist()
    public_model["std"] = model["std"].tolist()
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/forward20_knn_v2/frozen_spec.md",
        "formal_validation_accessed": False, "untouched_oos_accessed": False,
        "coverage": coverage, "trials_before": 299,
        "new_multiplicity_units": 3, "trials_after": 302,
        "periods": {"fit": FIT, "calibration": CALIBRATION, "holdout": HOLDOUT},
        "membership_drops": {"fit": fit_drops, "calibration": cal_drops,
                             "holdout": holdout_drops},
        "model": public_model,
        "calibration": {"rows": len(cal_rows), "outcomes_used": False,
                        "entry_percentile": 80, "entry_threshold": entry_threshold,
                        "exit_percentile": 50, "exit_threshold": exit_threshold},
        "internal_holdout": {"candidate_rows": len(holdout_rows),
                             "selected_signals": len(signals), "signals": signals,
                             "cell": cell, "gate": gate},
        "open_formal_validation": gate["passed"],
    }
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = out / f"forward20_knn_{stamp}.json"
    md_path = out / f"forward20_knn_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 300–302 — Setup-Balanced Analogues", "",
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
        pd.DataFrame(raw_cell["trades"]).to_csv(
            out / f"forward20_knn_{stamp}_holdout_trades.csv", index=False,
        )
    if raw_cell["equity_curve"]:
        pd.DataFrame(raw_cell["equity_curve"]).to_csv(
            out / f"forward20_knn_{stamp}_holdout_daily.csv", index=False,
        )
    print(json.dumps({"signals": len(signals), "summary": cell["summary"],
                      "trade_stats": cell["trade_stats"], "gate": gate,
                      "open_formal_validation": gate["passed"]}, indent=2))
    print(json_path); print(md_path)


if __name__ == "__main__":
    main()
