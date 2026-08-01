#!/usr/bin/env python3
"""Prespecified Trial 489-495 SEC share-supply contraction lifecycle."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from anchored_vwap_reclaim_discovery import _period_rows, _score_table
from cross_sectional_leadership_discovery import discovery_backtest_score
from csv_client import CSVClient
from dmi_crossover_lifecycle_discovery import (
    VALIDATION,
    VALIDATION_PRICE_END,
    VALIDATION_PRICE_START,
)
from linear_timing_discovery import FIT, FIT_PRICE_END, compact, evaluate
from macd_crossover_lifecycle_discovery import DENSITY_MAX, DENSITY_MIN
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from pivot_retest_experiment import slice_prices
from sec_companyfacts import _units_for_tag, comparable_values, latest_event_before
from undercut_reclaim_discovery import gate

SHARE_TAGS = (
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "WeightedAverageNumberOfSharesOutstandingBasic",
)
FRESHNESS_DAYS = 120
HOLD_SESSIONS = 20
MAX_ATTEMPTS = 3
TRIALS_BEFORE = 488
TRIALS_AFTER = 495


def as_filed_share_events(companyfacts: dict) -> list[dict]:
    """Return same-accession YoY weighted-average-share comparisons."""
    tag_accessions: dict[str, dict[str, list[dict]]] = {}
    filings: set[tuple[str, str, str]] = set()
    for tag in SHARE_TAGS:
        by_accession: dict[str, list[dict]] = defaultdict(list)
        for row in _units_for_tag(companyfacts, tag):
            accession = row.get("accn")
            form = row.get("form")
            filed = row.get("filed")
            if accession:
                by_accession[accession].append(row)
            if accession and filed and form in ("10-Q", "10-K"):
                filings.add((filed, accession, form))
        tag_accessions[tag] = dict(by_accession)
    events = []
    for filed, accession, form in sorted(filings):
        for tag in SHARE_TAGS:
            values = comparable_values(
                tag_accessions[tag].get(accession, []), accession, form)
            if values is None or values[0] <= 0 or values[1] <= 0:
                continue
            events.append({
                "filed": filed, "accession": accession, "form": form,
                "share_growth": values[0] / values[1] - 1,
                "current_shares": values[0], "prior_shares": values[1],
                "share_tag": tag,
            })
            break
    return events


def load_share_events(companyfacts_dir: Path,
                      symbols: set[str]) -> tuple[dict[str, list[dict]], dict]:
    events: dict[str, list[dict]] = {}
    stats = {"symbols_requested": len(symbols), "cached": 0,
             "with_comparable_events": 0, "invalid": 0,
             "comparable_events": 0}
    for symbol in sorted(symbols):
        path = companyfacts_dir / f"{symbol}.json"
        if not path.exists():
            continue
        stats["cached"] += 1
        try:
            rows = as_filed_share_events(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            stats["invalid"] += 1
            continue
        if rows:
            events[symbol] = rows
            stats["with_comparable_events"] += 1
            stats["comparable_events"] += len(rows)
    return events, stats


def share_contraction_signals(
    rows: list[dict], events_by_symbol: dict[str, list[dict]],
    freshness_days: int = FRESHNESS_DAYS,
    hold_sessions: int = HOLD_SESSIONS,
    max_attempts: int = MAX_ATTEMPTS,
) -> list[dict]:
    """Emit causal fresh-contraction entries with fixed next-open exits."""
    if min(freshness_days, hold_sessions, max_attempts) <= 0:
        raise ValueError("lifecycle parameters must be positive")
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["setup_id"]].append(row)
    signals = []
    for setup_rows in grouped.values():
        ordered = sorted(setup_rows, key=lambda item: int(item["fill_idx"]))
        eligible_fill_idx = -1
        attempts = 0
        for row in ordered:
            if attempts >= max_attempts:
                break
            if int(row["fill_idx"]) < eligible_fill_idx:
                continue
            event = latest_event_before(
                events_by_symbol.get(row["symbol"], []), row["signal_date"])
            if event is None:
                continue
            age = (date.fromisoformat(row["signal_date"])
                   - date.fromisoformat(event["filed"])).days
            if age > freshness_days or float(event["share_growth"]) >= 0:
                continue
            if float(row.get("close") or 0) <= float(row["pivot"]):
                continue
            attempts += 1
            signal = {key: row[key] for key in (
                "symbol", "sector", "signal_date", "fill_date", "fill_idx",
                "edge_rank", "pattern_stop", "pivot",
            )}
            signal.update({
                "attempt": attempts, "filed": event["filed"],
                "accession": event["accession"],
                "share_growth": event["share_growth"],
                "share_tag": event["share_tag"], "event_age_days": age,
                "model_exit_idx": int(row["fill_idx"]) + hold_sessions,
            })
            eligible_fill_idx = signal["model_exit_idx"]
            signals.append(signal)
    return sorted(signals, key=lambda row: (
        row["fill_date"], -row["edge_rank"], row["symbol"], row["attempt"],
    ))


def _write_density_failure(output: Path, stamp: str, coverage: dict,
                           rows: list[dict], signals: list[dict], drops: int,
                           cache_stats: dict) -> None:
    density = {"active_setup_rows": len(rows), "signals": len(signals),
               "symbols": len({row["symbol"] for row in signals}),
               "minimum": DENSITY_MIN, "maximum": DENSITY_MAX,
               "passed": False}
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/share_supply_contraction_v2/frozen_spec.md",
        "classification": "outcome_free_density_only",
        "source": "repository-existing SEC Company Facts cache",
        "external_data_accessed": False,
        "return_evaluation_accessed": False,
        "validation_accessed": False,
        "best_available_oos_accessed": False,
        "coverage": coverage, "cache_stats": cache_stats,
        "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": TRIALS_AFTER - TRIALS_BEFORE,
        "trials_after": TRIALS_AFTER,
        "parameters": {"share_tags_priority": list(SHARE_TAGS),
                       "same_accession": True,
                       "share_growth_threshold": "<0",
                       "freshness_days": FRESHNESS_DAYS,
                       "entry": "close above frozen pivot, next open",
                       "hold_sessions": HOLD_SESSIONS,
                       "max_attempts": MAX_ATTEMPTS},
        "density": density, "membership_drops": drops,
        "permission_to_evaluate_returns": False,
    }
    json_path = output / f"share_supply_contraction_{stamp}.json"
    md_path = output / f"share_supply_contraction_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    md_path.write_text(
        "# Trial 489–495 — SEC Share-Supply Contraction Density Audit\n\n"
        "External data accessed: **NO**\n\nReturn evaluation accessed: **NO**\n\n"
        f"Signals: **{len(signals)}** across {density['symbols']} symbols; "
        f"required {DENSITY_MIN}–{DENSITY_MAX}.\n\n"
        "Density gate: **FAIL**. The family is closed outcome-free; validation "
        "and best-available OOS remain sealed.\n"
    )
    print(json.dumps({"cache_stats": cache_stats, "density": density}, indent=2))
    print(json_path); print(md_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--companyfacts-dir", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--output-dir",
                        default="backtests/share_supply_contraction_v2/results")
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
    train_rows, train_drops = _period_rows(
        detections, membership, train_prices, *FIT)
    events, cache_stats = load_share_events(
        Path(args.companyfacts_dir), {row["symbol"] for row in train_rows})
    train_signals = share_contraction_signals(train_rows, events)
    output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    if not DENSITY_MIN <= len(train_signals) <= DENSITY_MAX:
        _write_density_failure(output, stamp, coverage, train_rows,
                               train_signals, train_drops, cache_stats)
        return

    train_raw = evaluate(train_signals, train_prices, args.iterations,
                         exit_rule="model_decay", trials_declared=TRIALS_AFTER)
    train_cell = compact(train_raw)
    train_gate = gate(train_cell, 60, 10)
    train_score = discovery_backtest_score(train_cell)

    validation = validation_raw = validation_drops = validation_cache = None
    if train_gate["passed"]:
        validation_prices = slice_prices(
            prices_all, VALIDATION_PRICE_START, VALIDATION_PRICE_END)
        validation_rows, validation_drops = _period_rows(
            detections, membership, validation_prices, *VALIDATION)
        validation_events, validation_cache = load_share_events(
            Path(args.companyfacts_dir),
            {row["symbol"] for row in validation_rows})
        validation_signals = share_contraction_signals(
            validation_rows, validation_events)
        validation_raw = evaluate(
            validation_signals, validation_prices, args.iterations,
            exit_rule="model_decay", trials_declared=TRIALS_AFTER)
        validation_cell = compact(validation_raw)
        validation = {"candidate_rows": len(validation_rows),
                      "signals": validation_signals, "cell": validation_cell,
                      "score": discovery_backtest_score(validation_cell),
                      "gate": gate(validation_cell, 60, 15)}

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/share_supply_contraction_v2/frozen_spec.md",
        "source": "repository-existing SEC Company Facts cache",
        "external_data_accessed": False,
        "backtest_score": train_score,
        "formal_validation_accessed": validation is not None,
        "best_available_oos_accessed": False,
        "coverage": coverage, "cache_stats": {"train": cache_stats,
                                                "validation": validation_cache},
        "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": TRIALS_AFTER - TRIALS_BEFORE,
        "trials_after": TRIALS_AFTER,
        "parameters": {"share_tags_priority": list(SHARE_TAGS),
                       "same_accession": True,
                       "share_growth_threshold": "<0",
                       "freshness_days": FRESHNESS_DAYS,
                       "entry": "close above frozen pivot, next open",
                       "hold_sessions": HOLD_SESSIONS,
                       "max_attempts": MAX_ATTEMPTS},
        "density": {"active_setup_rows": len(train_rows),
                    "signals": len(train_signals), "minimum": DENSITY_MIN,
                    "maximum": DENSITY_MAX, "passed": True},
        "chronology": {"train": FIT, "embargo": ["2018-07-01", "2018-12-31"],
                       "validation": VALIDATION,
                       "best_available_frozen_oos": ["2022-01-01", "2026-03-31"]},
        "membership_drops": {"train": train_drops,
                             "validation": validation_drops},
        "train": {"signals": train_signals, "cell": train_cell,
                  "gate": train_gate},
        "validation": validation,
        "open_best_available_oos": bool(validation and validation["gate"]["passed"]),
    }
    json_path = output / f"share_supply_contraction_{stamp}.json"
    md_path = output / f"share_supply_contraction_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    adjusted = (train_cell.get("robustness") or {}).get("risk_adjusted") or {}
    lines = ["# Trial 489–495 — SEC Share-Supply Contraction Lifecycle", "",
             "External data accessed: **NO**", "",
             "Best-available frozen OOS accessed: **NO**", "",
             *_score_table(train_score),
             f"Train signals {len(train_signals)}; trades "
             f"{train_cell['trade_stats']['trades']}; CAGR "
             f"{train_cell['summary']['cagr_pct']:.2f}%; Sharpe "
             f"{(adjusted.get('sharpe') or 0):.3f}; PF "
             f"{(train_cell['trade_stats'].get('profit_factor') or 0):.3f}; "
             f"MDD {train_cell['summary']['max_drawdown_pct']:.2f}%; trim-5 "
             f"expectancy {(train_cell['drop_top_5'].get('expectancy_pct') or 0):.2f}%.", "",
             f"Train gate: **{'PASS' if train_gate['passed'] else 'FAIL'}**", ""]
    lines.extend(f"- {'PASS' if passed else 'FAIL'} — {name}"
                 for name, passed in train_gate["checks"].items())
    lines += ["", f"2019–2021 validation accessed: "
              f"**{'YES' if validation else 'NO'}**", "",
              "2022–2026Q1 best-available OOS remains sealed.", ""]
    md_path.write_text("\n".join(lines))
    if train_raw["trades"]:
        pd.DataFrame(train_raw["trades"]).to_csv(
            output / f"share_supply_contraction_{stamp}_train_trades.csv", index=False)
        pd.DataFrame(train_raw["equity_curve"]).to_csv(
            output / f"share_supply_contraction_{stamp}_train_daily.csv", index=False)
    if validation_raw and validation_raw["trades"]:
        pd.DataFrame(validation_raw["trades"]).to_csv(
            output / f"share_supply_contraction_{stamp}_validation_trades.csv", index=False)
        pd.DataFrame(validation_raw["equity_curve"]).to_csv(
            output / f"share_supply_contraction_{stamp}_validation_daily.csv", index=False)
    print(json.dumps({"cache_stats": cache_stats,
                      "train_signals": len(train_signals),
                      "train_summary": train_cell["summary"],
                      "train_gate": train_gate, "backtest_score": train_score,
                      "validation_accessed": validation is not None,
                      "open_best_available_oos": report["open_best_available_oos"]},
                     indent=2))
    print(json_path); print(md_path)


if __name__ == "__main__":
    main()
