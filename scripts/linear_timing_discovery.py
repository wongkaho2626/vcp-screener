#!/usr/bin/env python3
"""Purged train-only ridge timing model for causal VCP entry selection."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from csv_client import CSVClient
from edge_rank import DEFAULT_W_EXT, DEFAULT_W_RS, SIZING_MIN_EDGE, compute_edge_rank
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import (
    filter_detections, slice_prices, trade_stats, trim_stats,
)
from portfolio_backtest import Config, _as_of_pattern_levels, run_portfolio
from portfolio_robustness import analyze
from pullback_followthrough_discovery import holdout_gate

FIT = ("2016-07-01", "2018-06-30")
FIT_PRICE_END = "2018-12-31"
CALIBRATION = ("2019-01-01", "2019-06-30")
CALIBRATION_PRICE_END = "2019-12-31"
HOLDOUT = ("2020-01-01", "2021-12-31")
FEATURE_NAMES = (
    "delay_60", "close_pivot", "close_stop", "ret_1", "ret_3", "ret_5",
    "ret_10", "ret_20", "sma10_dist", "sma20_dist", "drawdown_high10",
    "clv", "volume_ratio20", "atr20", "edge_rank_100",
)


def _return(bars: list[dict], i: int, lag: int) -> float:
    if i - lag < 0:
        return 0.0
    prior = float(bars[i - lag].get("close") or 0)
    close = float(bars[i].get("close") or 0)
    return close / prior - 1 if prior > 0 else 0.0


def _sma_distance(bars: list[dict], i: int, period: int) -> float:
    if i - period + 1 < 0:
        return 0.0
    avg = statistics.fmean(float(row.get("close") or 0) for row in bars[i - period + 1:i + 1])
    close = float(bars[i].get("close") or 0)
    return close / avg - 1 if avg > 0 else 0.0


def _atr_ratio(bars: list[dict], i: int, period: int = 20) -> float:
    if i - period + 1 < 1:
        return 0.0
    values = []
    for j in range(i - period + 1, i + 1):
        high = float(bars[j].get("high") or bars[j].get("close") or 0)
        low = float(bars[j].get("low") or bars[j].get("close") or 0)
        prior = float(bars[j - 1].get("close") or 0)
        values.append(max(high - low, abs(high - prior), abs(low - prior)))
    close = float(bars[i].get("close") or 0)
    return statistics.fmean(values) / close if close > 0 else 0.0


def causal_features(
    bars: list[dict], i: int, as_of_idx: int, pivot: float, stop: float,
    edge_rank: float,
) -> list[float]:
    """Compute the frozen 15-feature vector using bars no later than index i."""
    close = float(bars[i].get("close") or 0)
    high = float(bars[i].get("high") or close)
    low = float(bars[i].get("low") or close)
    span = high - low
    high10 = max(
        float(row.get("high") or row.get("close") or 0)
        for row in bars[max(0, i - 9):i + 1]
    )
    prior_volume = [
        float(row.get("volume") or 0)
        for row in bars[max(0, i - 20):i]
    ]
    average_volume = statistics.fmean(prior_volume) if prior_volume else 0.0
    volume_ratio = (
        float(bars[i].get("volume") or 0) / average_volume - 1
        if average_volume > 0 else 0.0
    )
    return [
        (i - as_of_idx) / 60,
        close / pivot - 1,
        close / stop - 1,
        *[_return(bars, i, lag) for lag in (1, 3, 5, 10, 20)],
        _sma_distance(bars, i, 10),
        _sma_distance(bars, i, 20),
        close / high10 - 1 if high10 > 0 else 0.0,
        (close - low) / span if span > 0 else .5,
        max(-1.0, min(5.0, volume_ratio)),
        _atr_ratio(bars, i),
        edge_rank / 100,
    ]


def best_future_return(
    bars: list[dict], signal_idx: int, pattern_stop: float,
    cfg: Config = Config(),
) -> float | None:
    """Train-label best later open before the fixed stop/60-session limit."""
    entry_idx = signal_idx + 1
    if entry_idx + 1 >= len(bars):
        return None
    cost = (cfg.commission_bps + cfg.slippage_bps) / 10_000
    entry = float(bars[entry_idx].get("open") or 0) * (1 + cost)
    if entry <= 0:
        return None
    stop = max(pattern_stop, entry * (1 - cfg.max_risk_pct / 100))
    terminal = min(entry_idx + cfg.max_hold_bars, len(bars) - 1)
    for i in range(entry_idx + 1, terminal + 1):
        if float(bars[i].get("low") or bars[i].get("close") or 0) <= stop:
            terminal = i
            break
    if terminal <= entry_idx:
        return None
    best_open = max(float(bars[i].get("open") or 0) for i in range(entry_idx + 1, terminal + 1))
    return best_open * (1 - cost) / entry - 1


def fixed_horizon_return(
    bars: list[dict], signal_idx: int, pattern_stop: float,
    horizon: int = 20, cfg: Config = Config(),
) -> float | None:
    """Train label: causal-rule net return at fixed open horizon or first stop."""
    entry_idx = signal_idx + 1
    if horizon <= 0 or entry_idx + 1 >= len(bars):
        return None
    cost = (cfg.commission_bps + cfg.slippage_bps) / 10_000
    entry = float(bars[entry_idx].get("open") or 0) * (1 + cost)
    if entry <= 0:
        return None
    stop = max(pattern_stop, entry * (1 - cfg.max_risk_pct / 100))
    terminal = min(entry_idx + horizon, len(bars) - 1)
    raw_exit = float(bars[terminal].get("open") or 0)
    for i in range(entry_idx + 1, terminal + 1):
        if float(bars[i].get("low") or bars[i].get("close") or 0) <= stop:
            raw_exit = min(float(bars[i].get("open") or 0), stop)
            break
    return raw_exit * (1 - cost) / entry - 1


def fixed_horizon_survival(
    bars: list[dict], signal_idx: int, pattern_stop: float,
    horizon: int = 20, cfg: Config = Config(),
) -> float | None:
    """Binary label: the unchanged hard stop is not touched for `horizon` bars."""
    entry_idx = signal_idx + 1
    if horizon <= 0 or entry_idx + horizon >= len(bars):
        return None
    cost = (cfg.commission_bps + cfg.slippage_bps) / 10_000
    entry = float(bars[entry_idx].get("open") or 0) * (1 + cost)
    if entry <= 0 or float(bars[entry_idx].get("open") or 0) <= pattern_stop:
        return None
    stop = max(pattern_stop, entry * (1 - cfg.max_risk_pct / 100))
    return float(not any(
        float(bars[i].get("low") or bars[i].get("close") or 0) <= stop
        for i in range(entry_idx + 1, entry_idx + horizon + 1)
    ))


def build_rows(
    detections: dict, prices: dict[str, list[dict]], *, with_labels: bool,
    label_mode: str = "best_exit",
) -> list[dict]:
    if label_mode not in ("best_exit", "forward20", "survive20"):
        raise ValueError(f"unknown label mode: {label_mode}")
    edges = compute_edge_rank(detections, DEFAULT_W_RS, DEFAULT_W_EXT)
    rows = []
    for symbol, dets in detections.items():
        bars = prices.get(symbol) or []
        index = {bar["date"]: i for i, bar in enumerate(bars)}
        for ordinal, detection in enumerate(dets):
            as_of = detection.get("as_of_date")
            as_of_idx = index.get(as_of)
            levels = _as_of_pattern_levels(detection)
            edge = (edges.get((symbol, as_of)) or {}).get("edge_rank")
            if as_of_idx is None or levels is None or edge is None or edge < SIZING_MIN_EDGE:
                continue
            pivot, stop = levels
            setup_id = f"{symbol}|{as_of}|{ordinal}"
            end = min(as_of_idx + 60, len(bars) - 1)
            for signal_idx in range(as_of_idx, end):
                close = float(bars[signal_idx].get("close") or 0)
                if close < stop:
                    break
                row = {
                    "setup_id": setup_id, "symbol": symbol,
                    "sector": detection.get("sector") or "Unknown",
                    "as_of_date": as_of, "signal_date": bars[signal_idx]["date"],
                    "fill_date": bars[signal_idx + 1]["date"],
                    "fill_idx": signal_idx + 1, "edge_rank": edge,
                    "fill_open": float(bars[signal_idx + 1].get("open") or 0),
                    "close": close,
                    "pattern_stop": stop, "pivot": pivot,
                    "features": causal_features(
                        bars, signal_idx, as_of_idx, pivot, stop, edge,
                    ),
                }
                if with_labels:
                    future = (fixed_horizon_survival(bars, signal_idx, stop, horizon=20)
                              if label_mode == "survive20" else (
                              fixed_horizon_return(bars, signal_idx, stop, horizon=20)
                              if label_mode == "forward20"
                              else best_future_return(bars, signal_idx, stop)))
                    if future is None:
                        continue
                    row["label"] = (future if label_mode == "survive20" else (
                        max(-.2, min(.5, future))
                        if label_mode == "forward20"
                        else max(0.0, min(.5, future))
                    ))
                rows.append(row)
    return rows


def fit_ridge(rows: list[dict], ridge_lambda: float = 10.0) -> dict:
    if not rows:
        raise ValueError("cannot fit an empty timing model")
    x = np.asarray([row["features"] for row in rows], dtype=float)
    y = np.asarray([row["label"] for row in rows], dtype=float)
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std[std == 0] = 1.0
    z = (x - mean) / std
    design = np.column_stack([np.ones(len(z)), z])
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["setup_id"]] = counts.get(row["setup_id"], 0) + 1
    weights = np.asarray([1 / counts[row["setup_id"]] for row in rows])
    weighted = design * np.sqrt(weights[:, None])
    target = y * np.sqrt(weights)
    penalty = np.eye(design.shape[1]) * ridge_lambda
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(weighted.T @ weighted + penalty, weighted.T @ target)
    return {
        "model_type": "linear",
        "feature_names": list(FEATURE_NAMES), "ridge_lambda": ridge_lambda,
        "mean": mean.tolist(), "std": std.tolist(),
        "intercept": float(coefficients[0]),
        "coefficients": coefficients[1:].tolist(),
        "fit_rows": len(rows), "fit_setups": len(counts),
    }


def fit_quadratic_ridge(rows: list[dict], ridge_lambda: float = 10.0) -> dict:
    """Fit fixed base-plus-square ridge with equal total weight per setup."""
    if not rows:
        raise ValueError("cannot fit an empty timing model")
    x = np.asarray([row["features"] for row in rows], dtype=float)
    y = np.asarray([row["label"] for row in rows], dtype=float)
    base_mean = x.mean(axis=0)
    base_std = x.std(axis=0)
    base_std[base_std == 0] = 1.0
    z = (x - base_mean) / base_std
    expanded = np.column_stack([z, z ** 2])
    expanded_mean = expanded.mean(axis=0)
    expanded_std = expanded.std(axis=0)
    expanded_std[expanded_std == 0] = 1.0
    q = (expanded - expanded_mean) / expanded_std
    design = np.column_stack([np.ones(len(q)), q])
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["setup_id"]] = counts.get(row["setup_id"], 0) + 1
    weights = np.asarray([1 / counts[row["setup_id"]] for row in rows])
    weighted = design * np.sqrt(weights[:, None])
    target = y * np.sqrt(weights)
    penalty = np.eye(design.shape[1]) * ridge_lambda
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(
        weighted.T @ weighted + penalty, weighted.T @ target,
    )
    return {
        "model_type": "quadratic",
        "feature_names": [*FEATURE_NAMES, *[f"{name}_squared" for name in FEATURE_NAMES]],
        "ridge_lambda": ridge_lambda,
        "mean": base_mean.tolist(), "std": base_std.tolist(),
        "expanded_mean": expanded_mean.tolist(),
        "expanded_std": expanded_std.tolist(),
        "intercept": float(coefficients[0]),
        "coefficients": coefficients[1:].tolist(),
        "fit_rows": len(rows), "fit_setups": len(counts),
    }


def fit_logistic_ridge(
    rows: list[dict], ridge_lambda: float = 10.0,
    label_threshold: float = .10, iterations: int = 25,
) -> dict:
    """Fit fixed setup-weighted binary logistic ridge by Newton updates."""
    if not rows:
        raise ValueError("cannot fit an empty timing model")
    x=np.asarray([row["features"] for row in rows],dtype=float)
    y=np.asarray([float(row["label"] >= label_threshold) for row in rows])
    mean=x.mean(axis=0); std=x.std(axis=0); std[std==0]=1.0
    z=(x-mean)/std; design=np.column_stack([np.ones(len(z)),z])
    counts={}
    for row in rows: counts[row["setup_id"]]=counts.get(row["setup_id"],0)+1
    weights=np.asarray([1/counts[row["setup_id"]] for row in rows])
    beta=np.zeros(design.shape[1]); penalty=np.eye(design.shape[1])*ridge_lambda
    penalty[0,0]=0.0
    for _ in range(iterations):
        logits=np.clip(design@beta,-30,30); probability=1/(1+np.exp(-logits))
        gradient=design.T@(weights*(probability-y))+penalty@beta
        curvature=weights*probability*(1-probability)
        hessian=design.T@(design*curvature[:,None])+penalty
        step=np.linalg.solve(hessian,gradient)
        beta-=step
        if np.max(np.abs(step)) < 1e-8: break
    return {"model_type":"logistic","feature_names":list(FEATURE_NAMES),
            "ridge_lambda":ridge_lambda,"label_threshold":label_threshold,
            "mean":mean.tolist(),"std":std.tolist(),"intercept":float(beta[0]),
            "coefficients":beta[1:].tolist(),"fit_rows":len(rows),
            "fit_setups":len(counts),"positive_rows":int(y.sum())}


def score_features(features: list[float], model: dict) -> float:
    z = (
        (np.asarray(features) - np.asarray(model["mean"]))
        / np.asarray(model["std"])
    )
    if model.get("model_type", "linear") == "quadratic":
        expanded = np.concatenate([z, z ** 2])
        z = (
            (expanded - np.asarray(model["expanded_mean"]))
            / np.asarray(model["expanded_std"])
        )
    return float(model["intercept"] + z @ np.asarray(model["coefficients"]))


def threshold_from_rows(rows: list[dict], model: dict, percentile: float = 85) -> float:
    scores = [score_features(row["features"], model) for row in rows]
    if not scores:
        raise ValueError("cannot calibrate threshold on empty rows")
    return float(np.percentile(scores, percentile))


def signals_from_rows(rows: list[dict], model: dict, threshold: float) -> list[dict]:
    selected = []
    seen = set()
    for row in sorted(rows, key=lambda value: (value["signal_date"], value["setup_id"])):
        if row["setup_id"] in seen:
            continue
        if score_features(row["features"], model) < threshold:
            continue
        seen.add(row["setup_id"])
        selected.append({
            key: row[key] for key in (
                "symbol", "sector", "signal_date", "fill_date", "fill_idx",
                "edge_rank", "pattern_stop", "pivot",
            )
        })
    return sorted(selected, key=lambda value: (
        value["fill_date"], -value["edge_rank"], value["symbol"],
    ))


def signals_with_decay(
    rows: list[dict], model: dict, entry_threshold: float, exit_threshold: float,
) -> list[dict]:
    """Enter on a high score and schedule exit after a later low-score close."""
    by_setup: dict[str, list[dict]] = {}
    for row in rows:
        by_setup.setdefault(row["setup_id"], []).append(row)
    selected = []
    for setup_rows in by_setup.values():
        ordered = sorted(setup_rows, key=lambda value: value["signal_date"])
        entry = next(
            (row for row in ordered
             if score_features(row["features"], model) >= entry_threshold),
            None,
        )
        if entry is None:
            continue
        later = [row for row in ordered if row["fill_idx"] > entry["fill_idx"]]
        decay = next(
            (row for row in later
             if score_features(row["features"], model) <= exit_threshold),
            None,
        )
        signal = {
            key: entry[key] for key in (
                "symbol", "sector", "signal_date", "fill_date", "fill_idx",
                "edge_rank", "pattern_stop", "pivot",
            )
        }
        if decay is not None:
            signal["model_exit_idx"] = decay["fill_idx"]
        selected.append(signal)
    return sorted(selected, key=lambda value: (
        value["fill_date"], -value["edge_rank"], value["symbol"],
    ))


def lifecycle_signals_with_decay(
    rows: list[dict], model: dict, entry_threshold: float, exit_threshold: float,
    cooldown: int = 5, max_cycles: int = 3,
) -> list[dict]:
    """Emit repeated high/low score hysteresis cycles for each frozen setup."""
    if cooldown <= 0 or max_cycles <= 0:
        return []
    by_setup: dict[str, list[dict]] = {}
    for row in rows:
        by_setup.setdefault(row["setup_id"], []).append(row)
    signals = []
    for setup_rows in by_setup.values():
        ordered = sorted(setup_rows, key=lambda value: value["signal_date"])
        cursor = 0
        last_entry_idx = -10**9
        for attempt in range(1, max_cycles + 1):
            entry_pos = next((j for j in range(cursor, len(ordered))
                              if ordered[j]["fill_idx"] - last_entry_idx >= cooldown
                              and score_features(ordered[j]["features"], model) >= entry_threshold), None)
            if entry_pos is None:
                break
            entry = ordered[entry_pos]
            decay_pos = next((j for j in range(entry_pos + 1, len(ordered))
                              if score_features(ordered[j]["features"], model) <= exit_threshold), None)
            signal = {key: entry[key] for key in (
                "symbol", "sector", "signal_date", "fill_date", "fill_idx",
                "edge_rank", "pattern_stop", "pivot",
            )}
            signal["attempt"] = attempt
            if decay_pos is not None:
                signal["model_exit_idx"] = ordered[decay_pos]["fill_idx"]
                cursor = decay_pos + 1
            else:
                cursor = len(ordered)
            signals.append(signal)
            last_entry_idx = entry["fill_idx"]
            if decay_pos is None:
                break
    return sorted(signals, key=lambda value: (
        value["fill_date"], -value["edge_rank"], value["symbol"],
    ))


def signals_with_loss_decay(
    rows: list[dict], model: dict, entry_threshold: float, exit_threshold: float,
) -> list[dict]:
    """Exit on low-score close only while price is below raw entry open."""
    by_setup: dict[str, list[dict]] = {}
    for row in rows:
        by_setup.setdefault(row["setup_id"], []).append(row)
    signals = []
    for setup_rows in by_setup.values():
        ordered = sorted(setup_rows, key=lambda value: value["signal_date"])
        entry_pos = next((j for j,row in enumerate(ordered)
                          if score_features(row["features"],model) >= entry_threshold), None)
        if entry_pos is None:
            continue
        entry = ordered[entry_pos]
        decay = next((row for row in ordered[entry_pos+1:]
                      if score_features(row["features"],model) <= exit_threshold
                      and float(row["close"]) < float(entry["fill_open"])), None)
        signal={key:entry[key] for key in (
            "symbol","sector","signal_date","fill_date","fill_idx",
            "edge_rank","pattern_stop","pivot",
        )}
        if decay is not None:
            signal["model_exit_idx"]=decay["fill_idx"]
        signals.append(signal)
    return sorted(signals,key=lambda value:(value["fill_date"],-value["edge_rank"],value["symbol"]))


def evaluate(
    signals: list[dict], prices: dict[str, list[dict]], iterations: int,
    exit_rule: str = "followthrough_sma", trials_declared: int = 251,
) -> dict:
    exit_params = (
        {"early_days": 10, "min_gain_pct": 3.0,
         "arm_gain_pct": 10.0, "sma_period": 20}
        if exit_rule == "followthrough_sma" else None
    )
    with patch("portfolio_backtest._candidate_signals", return_value=signals):
        portfolio = run_portfolio(
            {}, prices, Config(), exit_rule=exit_rule, exit_params=exit_params,
        )
    curve = portfolio["equity_curve"]
    robustness = None
    if len(curve) >= 3:
        robustness = analyze(
            pd.Series([row["date"] for row in curve]),
            [float(row["portfolio_return"]) for row in curve],
            trials_declared, iterations, 10, 20260801, .70,
        )
    return {
        "summary": portfolio["summary"],
        "trade_stats": trade_stats(portfolio["trades"]),
        "drop_top_5": trim_stats(portfolio["trades"], 5),
        "drop_top_10": trim_stats(portfolio["trades"], 10),
        "robustness": robustness,
        "trades": portfolio["trades"],
        "equity_curve": portfolio["equity_curve"],
    }


def compact(cell: dict) -> dict:
    return {key: value for key, value in cell.items() if key not in ("trades", "equity_curve")}


def markdown(report: dict) -> str:
    cell = report["internal_holdout"]["cell"]
    robust = cell.get("robustness") or {}
    adjusted = robust.get("risk_adjusted") or {}
    lines = [
        "# Purged Linear Timing Model — Train-Only Forward Holdout", "",
        f"Generated: {report['generated_at']}", "",
        "Formal validation accessed: **NO**", "",
        f"Fit rows/setups: {report['model']['fit_rows']} / {report['model']['fit_setups']}",
        f"Calibration rows: {report['calibration']['rows']}",
        f"Frozen 85th-percentile threshold: {report['calibration']['threshold']:.6f}", "",
        "## 2020–2021 internal holdout", "",
        f"Signals {cell['summary']['signals']}; trades {cell['trade_stats']['trades']}; "
        f"net CAGR {cell['summary']['cagr_pct']:.2f}%; Sharpe {(adjusted.get('sharpe') or 0):.3f}; "
        f"Sortino {(adjusted.get('sortino') or 0):.3f}; Calmar {(adjusted.get('calmar') or 0):.3f}; "
        f"PF {(cell['trade_stats']['profit_factor'] or 0):.3f}; MDD {cell['summary']['max_drawdown_pct']:.2f}%; "
        f"drop-top-five expectancy {(cell['drop_top_5']['expectancy_pct'] or 0):.2f}%.", "",
        f"Internal gate: **{'PASS' if report['internal_holdout']['gate']['passed'] else 'FAIL'}**", "",
    ]
    for name, passed in report["internal_holdout"]["gate"]["checks"].items():
        lines.append(f"- {'PASS' if passed else 'FAIL'} — {name}")
    lines += [
        "", "The 2022–2023 formal validation and untouched OOS were not accessed. "
        "A failed gate closes this specification.", "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    ap.add_argument("--coverage-json", required=True)
    ap.add_argument("--output-dir", default="backtests/linear_timing_v2/results")
    ap.add_argument("--iterations", type=int, default=1000)
    args = ap.parse_args()

    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/benchmark gate failed")
    payload = json.loads(Path(args.backtest_json).read_text())
    all_detections = payload.get("detections_by_ticker") or {}
    membership = load_membership(args.membership_csv)
    client = CSVClient(args.price_csv)
    prices_all = {
        row["symbol"]: list(reversed(client.get_historical_prices(
            row["symbol"], days=100_000,
        )["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]
    }

    fit_detections, fit_drops = filter_detections(all_detections, membership, *FIT)
    fit_prices = slice_prices(prices_all, FIT[0], FIT_PRICE_END)
    fit_rows = build_rows(fit_detections, fit_prices, with_labels=True)
    model = fit_ridge(fit_rows)

    calibration_detections, calibration_drops = filter_detections(
        all_detections, membership, *CALIBRATION,
    )
    calibration_prices = slice_prices(prices_all, CALIBRATION[0], CALIBRATION_PRICE_END)
    calibration_rows = build_rows(
        calibration_detections, calibration_prices, with_labels=False,
    )
    threshold = threshold_from_rows(calibration_rows, model)

    holdout_detections, holdout_drops = filter_detections(
        all_detections, membership, *HOLDOUT,
    )
    holdout_prices = slice_prices(prices_all, *HOLDOUT)
    holdout_rows = build_rows(holdout_detections, holdout_prices, with_labels=False)
    signals = signals_from_rows(holdout_rows, model, threshold)
    raw_cell = evaluate(signals, holdout_prices, args.iterations)
    holdout = compact(raw_cell)
    gate = holdout_gate(holdout)

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/linear_timing_v2/family_spec.md",
        "formal_validation_accessed": False,
        "untouched_oos_accessed": False,
        "coverage": coverage,
        "trials_before": 234, "new_multiplicity_units": 17, "trials_after": 251,
        "periods": {
            "fit": FIT, "fit_price_end": FIT_PRICE_END,
            "calibration": CALIBRATION, "calibration_price_end": CALIBRATION_PRICE_END,
            "internal_holdout": HOLDOUT,
        },
        "membership_drops": {
            "fit": fit_drops, "calibration": calibration_drops,
            "internal_holdout": holdout_drops,
        },
        "model": model,
        "calibration": {
            "rows": len(calibration_rows), "setups": len({r['setup_id'] for r in calibration_rows}),
            "percentile": 85, "threshold": threshold, "outcomes_used": False,
        },
        "internal_holdout": {
            "candidate_rows": len(holdout_rows),
            "candidate_setups": len({r['setup_id'] for r in holdout_rows}),
            "selected_signals": len(signals), "cell": holdout, "gate": gate,
        },
        "open_formal_validation": gate["passed"],
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = out / f"linear_timing_discovery_{stamp}.json"
    md_path = out / f"linear_timing_discovery_{stamp}.md"
    trades_path = out / f"linear_timing_discovery_{stamp}_holdout_trades.csv"
    daily_path = out / f"linear_timing_discovery_{stamp}_holdout_daily.csv"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    md_path.write_text(markdown(report))
    if raw_cell["trades"]:
        pd.DataFrame(raw_cell["trades"]).to_csv(trades_path, index=False)
    if raw_cell["equity_curve"]:
        pd.DataFrame(raw_cell["equity_curve"]).to_csv(daily_path, index=False)
    print(json.dumps({
        "fit_rows": len(fit_rows), "calibration_rows": len(calibration_rows),
        "threshold": threshold, "holdout_signals": len(signals),
        "holdout_summary": holdout["summary"], "gate": gate,
        "open_formal_validation": gate["passed"],
    }, indent=2))
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
