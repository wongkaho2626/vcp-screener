#!/usr/bin/env python3
"""Outcome-free Trial 471-477 gap-rejection reclaim density audit."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from anchored_vwap_reclaim_discovery import _period_rows
from csv_client import CSVClient
from linear_timing_discovery import FIT, FIT_PRICE_END
from macd_crossover_lifecycle_discovery import DENSITY_MAX, DENSITY_MIN
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import slice_prices

GAP_THRESHOLD = .01
RECLAIM_WINDOW = 5
MAX_ATTEMPTS = 3
TRIALS_BEFORE = 470
TRIALS_AFTER = 477


def is_gap_rejection(bars: list[dict], index: int,
                     gap_threshold: float = GAP_THRESHOLD) -> bool:
    """Return a completed-bar gap-up rejection using no later observation."""
    if gap_threshold < 0:
        raise ValueError("gap threshold cannot be negative")
    if index <= 0 or index >= len(bars):
        return False
    prior_close = float(bars[index - 1].get("close") or 0)
    open_price = float(bars[index].get("open") or 0)
    close = float(bars[index].get("close") or 0)
    return bool(prior_close > 0 and open_price > 0 and close > 0
                and open_price / prior_close - 1 >= gap_threshold
                and close < open_price)


def _signal_from_row(row: dict, attempt: int, rejection: dict) -> dict:
    signal = {key: row[key] for key in (
        "symbol", "sector", "signal_date", "fill_date", "fill_idx",
        "edge_rank", "pattern_stop", "pivot",
    )}
    signal.update({
        "attempt": attempt,
        "rejection_date": rejection["signal_date"],
        "rejection_high": rejection["rejection_high"],
        "rejection_low": rejection["rejection_low"],
    })
    return signal


def rejection_reclaim_signals(
    rows: list[dict], prices: dict[str, list[dict]],
    gap_threshold: float = GAP_THRESHOLD,
    reclaim_window: int = RECLAIM_WINDOW,
    max_attempts: int = MAX_ATTEMPTS,
) -> list[dict]:
    """Emit causal rejection-high reclaims and frozen-low next-open exits."""
    if reclaim_window <= 0 or max_attempts <= 0:
        raise ValueError("lifecycle parameters must be positive")
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["setup_id"]].append(row)
    signals: list[dict] = []
    for setup_rows in grouped.values():
        ordered = sorted(setup_rows, key=lambda item: int(item["fill_idx"]))
        bars = prices.get(ordered[0]["symbol"]) if ordered else None
        if not bars:
            continue
        cursor = 0
        attempts = 0
        while cursor < len(ordered) and attempts < max_attempts:
            rejection_pos = next((
                pos for pos in range(cursor, len(ordered))
                if is_gap_rejection(bars, int(ordered[pos]["fill_idx"]) - 1,
                                    gap_threshold)
            ), None)
            if rejection_pos is None:
                break
            rejection_row = ordered[rejection_pos]
            rejection_idx = int(rejection_row["fill_idx"]) - 1
            rejection_high = float(bars[rejection_idx].get("high") or 0)
            rejection_low = float(bars[rejection_idx].get("low") or 0)
            rejection = {**rejection_row, "rejection_high": rejection_high,
                         "rejection_low": rejection_low}
            reclaim_pos = None
            for pos in range(rejection_pos + 1, len(ordered)):
                row = ordered[pos]
                signal_idx = int(row["fill_idx"]) - 1
                elapsed = signal_idx - rejection_idx
                if elapsed > reclaim_window:
                    break
                if elapsed <= 0:
                    continue
                close = float(bars[signal_idx].get("close") or 0)
                if close < float(row["pattern_stop"]):
                    break
                if close > rejection_high and close > float(row["pivot"]):
                    reclaim_pos = pos
                    break
            if reclaim_pos is None:
                cursor = rejection_pos + 1
                continue
            attempts += 1
            entry = ordered[reclaim_pos]
            signal = _signal_from_row(entry, attempts, rejection)
            exit_pos = next((
                pos for pos in range(reclaim_pos + 1, len(ordered))
                if float(bars[int(ordered[pos]["fill_idx"]) - 1].get("close") or 0)
                < rejection_low
            ), None)
            if exit_pos is None:
                cursor = len(ordered)
            else:
                signal["model_exit_idx"] = int(ordered[exit_pos]["fill_idx"])
                cursor = exit_pos + 1
            signals.append(signal)
    return sorted(signals, key=lambda row: (
        row["fill_date"], -row["edge_rank"], row["symbol"], row["attempt"],
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--output-dir",
                        default="backtests/gap_rejection_reclaim_v2/results")
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
    train_rows, membership_drops = _period_rows(
        detections, membership, train_prices, *FIT)
    signals = rejection_reclaim_signals(train_rows, train_prices)
    passed = DENSITY_MIN <= len(signals) <= DENSITY_MAX
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/gap_rejection_reclaim_v2/density_spec.md",
        "classification": "outcome_free_density_only",
        "return_evaluation_accessed": False,
        "validation_accessed": False,
        "best_available_oos_accessed": False,
        "period": list(FIT),
        "price_end_for_causal_signal_bookkeeping": FIT_PRICE_END,
        "coverage": coverage,
        "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": TRIALS_AFTER - TRIALS_BEFORE,
        "trials_after": TRIALS_AFTER,
        "parameters": {
            "gap_threshold_pct": GAP_THRESHOLD * 100,
            "rejection": "close strictly below open",
            "reclaim_window_sessions": RECLAIM_WINDOW,
            "reclaim": "close strictly above frozen rejection high and pivot",
            "model_exit": "next open after close below frozen rejection low",
            "max_attempts": MAX_ATTEMPTS,
            "max_hold_sessions": 60,
        },
        "density": {
            "active_setup_rows": len(train_rows),
            "signals": len(signals),
            "symbols": len({row["symbol"] for row in signals}),
            "setups": len({(row["symbol"], row["rejection_date"])
                           for row in signals}),
            "minimum": DENSITY_MIN,
            "maximum": DENSITY_MAX,
            "passed": passed,
        },
        "membership_drops": membership_drops,
        "permission_to_freeze_return_specification": passed,
    }
    output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = output / f"gap_rejection_reclaim_density_{stamp}.json"
    md_path = output / f"gap_rejection_reclaim_density_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    md_path.write_text(
        "# Trial 471–477 — Gap-Rejection Reclaim Density Audit\n\n"
        "Return evaluation accessed: **NO**\n\n"
        f"Active setup rows: {len(train_rows)}; signals: **{len(signals)}**; "
        f"symbols: {report['density']['symbols']}.\n\n"
        f"Density gate ({DENSITY_MIN}–{DENSITY_MAX}): "
        f"**{'PASS' if passed else 'FAIL'}**.\n\n"
        + ("A separate return specification may now be frozen; returns remain unopened.\n"
           if passed else
           "Family closed outcome-free; validation and best-available OOS remain sealed.\n")
    )
    print(json.dumps(report["density"], indent=2))
    print(json_path); print(md_path)


if __name__ == "__main__":
    main()
