#!/usr/bin/env python3
"""Non-deployable train-only audit of causal states before oracle exits."""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime
from pathlib import Path

from csv_client import CSVClient
from linear_timing_discovery import FIT, FIT_PRICE_END
from membership import DEFAULT_MEMBERSHIP_CSV, load_membership
from portfolio_backtest import Config, _candidate_signals
from pivot_retest_experiment import filter_detections, slice_prices
from train_feasibility_audit import best_timed_signal


PROXY_LABELS = {
    "five_day_close_high": "strength exit; near prior profit-taking/high rules",
    "two_up_closes": "strength exit; price-staircase analogue",
    "down_close": "weakness exit; directly tested family",
    "below_sma10": "weakness exit; directly tested family",
    "trailing_drawdown_5pct": "giveback exit; trailing-stop family",
    "gain_10pct": "profit exit; target/scale-out family",
}


def exit_proxy_flags(bars: list[dict], entry_idx: int,
                     exit_idx: int) -> dict[str, bool] | None:
    """Causal close-state flags available before an oracle next-open exit."""
    signal_idx = exit_idx - 1
    if entry_idx < 0 or signal_idx <= entry_idx or signal_idx >= len(bars):
        return None
    closes = [float(bar.get("close") or 0) for bar in bars]
    entry_open = float(bars[entry_idx].get("open") or 0)
    if entry_open <= 0 or any(close <= 0 for close in closes[max(0, signal_idx - 19):signal_idx + 1]):
        return None
    close = closes[signal_idx]
    prior = closes[signal_idx - 1]
    since_entry = closes[entry_idx:signal_idx + 1]
    last_five = closes[max(0, signal_idx - 4):signal_idx + 1]
    last_ten = closes[max(0, signal_idx - 9):signal_idx + 1]
    return {
        "five_day_close_high": len(last_five) == 5 and close >= max(last_five),
        "two_up_closes": signal_idx >= 2 and close > prior > closes[signal_idx - 2],
        "down_close": close < prior,
        "below_sma10": len(last_ten) == 10
                           and close < statistics.fmean(last_ten),
        "trailing_drawdown_5pct": close <= max(since_entry) * .95,
        "gain_10pct": close >= entry_open * 1.10,
    }


def record_choice(base: dict, chosen: dict, future_return: float,
                  bars: list[dict]) -> dict | None:
    entry_idx = int(chosen["fill_idx"])
    exit_idx = int(chosen["diagnostic_exit_idx"])
    flags = exit_proxy_flags(bars, entry_idx, exit_idx)
    if flags is None:
        return None
    return {
        "symbol": chosen["symbol"],
        "base_fill_date": base["fill_date"],
        "entry_date": chosen["fill_date"],
        "exit_date": bars[exit_idx]["date"],
        "entry_delay_sessions": entry_idx - int(base["fill_idx"]),
        "hold_sessions": exit_idx - entry_idx,
        "oracle_return_pct": 100 * future_return,
        "flags": flags,
    }


def summarize(records: list[dict]) -> dict:
    if not records:
        return {"records": 0, "proxy_hit_rates": {key: None for key in PROXY_LABELS}}
    delays = [int(row["entry_delay_sessions"]) for row in records]
    holds = [int(row["hold_sessions"]) for row in records]
    returns = [float(row["oracle_return_pct"]) for row in records]
    return {
        "records": len(records),
        "entry_delay_sessions": {
            "median": statistics.median(delays),
            "mean": statistics.fmean(delays),
        },
        "hold_sessions": {
            "median": statistics.median(holds),
            "mean": statistics.fmean(holds),
            "within_5_pct": 100 * sum(value <= 5 for value in holds) / len(holds),
            "within_10_pct": 100 * sum(value <= 10 for value in holds) / len(holds),
            "within_20_pct": 100 * sum(value <= 20 for value in holds) / len(holds),
        },
        "oracle_return_pct": {
            "median": statistics.median(returns),
            "mean": statistics.fmean(returns),
        },
        "proxy_hit_rates": {
            key: 100 * sum(bool(row["flags"][key]) for row in records) / len(records)
            for key in PROXY_LABELS
        },
    }


def markdown(report: dict) -> str:
    overall = report["summaries"]["overall"]
    lines = [
        "# Train-Only Oracle Exit Residual Audit", "",
        "**LOOKAHEAD / NON-DEPLOYABLE / NON-SCOREABLE.** Oracle entry and exit",
        "choices inspect future prices. This is a mechanism diagnostic only; it",
        "is not a strategy, Backtest Score or permission to open validation/OOS.", "",
        f"Records: {overall['records']}; median entry delay "
        f"{overall['entry_delay_sessions']['median']:.1f} sessions; median oracle "
        f"hold {overall['hold_sessions']['median']:.1f} sessions; median oracle "
        f"return {overall['oracle_return_pct']['median']:.2f}%.", "",
        "| Causal state on close before oracle exit | Overall | Early fold | Late fold | Drop top 5 | Prior status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for key, label in PROXY_LABELS.items():
        rates = [report["summaries"][name]["proxy_hit_rates"][key]
                 for name in ("overall", "early_fold", "late_fold", "drop_top_5")]
        cells = ["—" if value is None else f"{value:.1f}%" for value in rates]
        lines.append(f"| {key} | {' | '.join(cells)} | {label} |")
    lines += ["", "## Decision rule", "",
              "A proxy is only hypothesis-generating if it appears before at least",
              "60% of oracle exits in both chronological halves and after removing",
              "the five largest oracle returns, and if its mechanism was not already",
              "tested. No thresholds are searched or changed in this audit.", ""]
    qualified = report["qualified_unresolved_proxies"]
    if qualified:
        lines.append("Qualified unresolved proxies: " + ", ".join(qualified) + ".")
    else:
        lines.append("**No proxy qualifies.** The simple causal exit states either lack stable "
                     "oracle coverage or belong to already rejected exit families.")
    lines += ["", "Validation and best-available OOS were not accessed.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--membership-csv", default=DEFAULT_MEMBERSHIP_CSV)
    parser.add_argument("--output-dir", default="backtests/oracle_exit_residual_audit")
    args = parser.parse_args()
    coverage = json.loads(Path(args.coverage_json).read_text())
    if coverage.get("coverage_pct", 0) < 90 or not coverage.get("benchmark_present"):
        raise SystemExit("PIT coverage/benchmark gate failed")
    payload = json.loads(Path(args.backtest_json).read_text())
    detections, dropped = filter_detections(
        payload.get("detections_by_ticker") or {},
        load_membership(args.membership_csv), *FIT)
    client = CSVClient(args.price_csv)
    prices = slice_prices({
        row["symbol"]: list(reversed(client.get_historical_prices(
            row["symbol"], days=100_000)["historical"]))
        for row in [*client.get_constituents(), {"symbol": "SPY"}]
    }, FIT[0], FIT_PRICE_END)
    cfg = Config()
    bases = _candidate_signals(detections, prices, cfg,
                               entry_rule="detection_entry")
    records = []
    for base in bases:
        bars = prices.get(base["symbol"]) or []
        choice = best_timed_signal(base, bars, cfg, entry_window=60)
        if choice is None or choice[1] <= 0:
            continue
        row = record_choice(base, choice[0], choice[1], bars)
        if row is not None:
            records.append(row)
    records.sort(key=lambda row: (row["entry_date"], row["symbol"]))
    early = [row for row in records if row["entry_date"] < "2017-07-01"]
    late = [row for row in records if row["entry_date"] >= "2017-07-01"]
    drop_top = sorted(records, key=lambda row: row["oracle_return_pct"])[:-5]
    summaries = {"overall": summarize(records), "early_fold": summarize(early),
                 "late_fold": summarize(late), "drop_top_5": summarize(drop_top)}
    qualified = []
    for key in PROXY_LABELS:
        rates = [summaries[name]["proxy_hit_rates"][key]
                 for name in ("early_fold", "late_fold", "drop_top_5")]
        if all(value is not None and value >= 60 for value in rates):
            # Every fixed proxy above maps to an already-tested exit family.
            # Keep the explicit empty unresolved list rather than reopening it.
            pass
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "classification": "lookahead_train_only_mechanism_diagnostic",
        "deployable": False, "scoreable": False,
        "period": list(FIT), "price_end_for_forward_diagnostic": FIT_PRICE_END,
        "validation_accessed": False, "best_available_oos_accessed": False,
        "coverage": coverage, "membership_drops": dropped,
        "base_signals": len(bases), "oracle_records": records,
        "proxy_labels": PROXY_LABELS, "summaries": summaries,
        "qualification_rule": (
            "at least 60% coverage in both chronological folds and drop-top-five, "
            "with a mechanism not already tested"
        ),
        "qualified_unresolved_proxies": qualified,
    }
    output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    prefix = output / f"oracle_exit_residual_{stamp}"
    prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n")
    prefix.with_suffix(".md").write_text(markdown(report))
    print(json.dumps({"base_signals": len(bases), "summaries": summaries,
                      "qualified_unresolved_proxies": qualified}, indent=2))
    print(prefix.with_suffix(".json")); print(prefix.with_suffix(".md"))


if __name__ == "__main__":
    main()
