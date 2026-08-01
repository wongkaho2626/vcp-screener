#!/usr/bin/env python3
"""Outcome-free Trial 467-470 PIT membership-tenure density audit."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

from csv_client import CSVClient
from linear_timing_discovery import FIT, FIT_PRICE_END
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from portfolio_backtest import Config, _candidate_signals
from pivot_retest_experiment import filter_detections, slice_prices

TENURE_CAPS = (90, 180, 365, 730)
DENSITY_MIN = 80
DENSITY_MAX = 500
TRIALS_BEFORE = 466
TRIALS_AFTER = 470


def containing_interval(intervals: dict[str, list[tuple[str, str]]],
                        symbol: str, signal_date: str,
                        fill_date: str) -> tuple[str, str] | None:
    """Return the one interval containing both signal and fill dates."""
    matches = [(start, end) for start, end in intervals.get(symbol, [])
               if start <= signal_date <= end and start <= fill_date <= end]
    if len(matches) > 1:
        raise ValueError("overlapping membership intervals")
    return matches[0] if matches else None


def membership_tenure_days(interval_start: str, signal_date: str) -> int:
    """Calendar-day tenure known on the signal date."""
    value = (date.fromisoformat(signal_date) - date.fromisoformat(interval_start)).days
    if value < 0:
        raise ValueError("signal precedes membership interval")
    return value


def annotate_candidates(signals: list[dict],
                        intervals: dict[str, list[tuple[str, str]]]
                        ) -> tuple[list[dict], dict[str, int]]:
    """Attach causal interval-start tenure; never expose interval end."""
    annotated = []
    drops = {"not_member_on_signal_and_fill": 0}
    for signal in signals:
        interval = containing_interval(
            intervals, signal["symbol"], signal["signal_date"], signal["fill_date"])
        if interval is None:
            drops["not_member_on_signal_and_fill"] += 1
            continue
        start, _end = interval
        annotated.append({
            "symbol": signal["symbol"],
            "signal_date": signal["signal_date"],
            "fill_date": signal["fill_date"],
            "membership_start": start,
            "tenure_days": membership_tenure_days(start, signal["signal_date"]),
        })
    return annotated, drops


def density_counts(annotated: list[dict]) -> dict[str, dict]:
    return {
        str(cap): {
            "signals": sum(int(row["tenure_days"]) <= cap for row in annotated),
            "symbols": len({row["symbol"] for row in annotated
                            if int(row["tenure_days"]) <= cap}),
        }
        for cap in TENURE_CAPS
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--output-dir", default="backtests/membership_tenure_v2/results")
    args = parser.parse_args()
    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/benchmark gate failed")
    membership = load_membership(args.membership_csv)
    payload = json.loads(Path(args.backtest_json).read_text())
    detections, detection_drops = filter_detections(
        payload.get("detections_by_ticker") or {}, membership, *FIT)
    client = CSVClient(args.price_csv)
    prices = slice_prices({
        row["symbol"]: list(reversed(client.get_historical_prices(
            row["symbol"], days=100_000)["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]
    }, FIT[0], FIT_PRICE_END)
    candidates = _candidate_signals(
        detections, prices, Config(), entry_rule="detection_entry")
    candidates = [row for row in candidates if row["symbol"] != "SPY"]
    annotated, membership_drops = annotate_candidates(candidates, membership)
    counts = density_counts(annotated)
    qualifying = [cap for cap in TENURE_CAPS
                  if DENSITY_MIN <= counts[str(cap)]["signals"] <= DENSITY_MAX]
    selected = min(qualifying) if qualifying else None
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "family_spec": "backtests/membership_tenure_v2/density_spec.md",
        "classification": "outcome_free_density_only",
        "return_evaluation_accessed": False,
        "validation_accessed": False,
        "best_available_oos_accessed": False,
        "period": list(FIT), "price_end_for_fill_bookkeeping": FIT_PRICE_END,
        "coverage": coverage, "trials_before": TRIALS_BEFORE,
        "new_multiplicity_units": len(TENURE_CAPS), "trials_after": TRIALS_AFTER,
        "parameters": {"tenure_caps_calendar_days": list(TENURE_CAPS),
                       "selection": "shortest cap with 80-500 signals",
                       "feature_uses_membership_end": False,
                       "signal_and_fill_membership_verified": True},
        "base_detection_candidates": len(candidates),
        "annotated_candidates": len(annotated),
        "detection_membership_drops": detection_drops,
        "candidate_membership_drops": membership_drops,
        "density": counts, "selected_cap_days": selected,
        "permission_to_freeze_strategy": selected is not None,
    }
    output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = output / f"membership_tenure_density_{stamp}.json"
    md_path = output / f"membership_tenure_density_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    lines = ["# Trial 467–470 — PIT Membership-Tenure Density Audit", "",
             "Return evaluation accessed: **NO**", "",
             f"Base candidates: {len(candidates)}; membership-verified: {len(annotated)}.", "",
             "| Tenure cap | Signals | Symbols | Density gate |",
             "|---:|---:|---:|---|"]
    for cap in TENURE_CAPS:
        cell = counts[str(cap)]
        passed = DENSITY_MIN <= cell["signals"] <= DENSITY_MAX
        lines.append(f"| {cap} days | {cell['signals']} | {cell['symbols']} | "
                     f"{'PASS' if passed else 'FAIL'} |")
    lines += ["", f"Selected cap: **{selected if selected is not None else 'NONE'}**.", ""]
    if selected is None:
        lines.append("Family closed outcome-free; no return, validation or OOS partition was opened.")
    else:
        lines.append("Density permits a separately frozen strategy specification; returns remain unopened.")
    md_path.write_text("\n".join(lines) + "\n")
    print(json.dumps({"base_candidates": len(candidates), "density": counts,
                      "selected_cap_days": selected,
                      "permission_to_freeze_strategy": selected is not None}, indent=2))
    print(json_path); print(md_path)


if __name__ == "__main__":
    main()
