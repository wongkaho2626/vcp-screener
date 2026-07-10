#!/usr/bin/env python3
"""Predeclared earnings-catalyst gate for the frozen VCP portfolio backtest.

This is deliberately a single-hypothesis experiment: thresholds are constants,
not CLI options, so the validation and evaluation segments cannot be tuned.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import date, datetime

from csv_client import CSVClient
from portfolio_backtest import Config, run_portfolio

EVENT_LOOKBACK_DAYS = 90
MIN_GAP_PCT = 2.0
SEGMENTS = (
    ("development", "2016-01-01", "2021-12-31"),
    ("validation", "2022-01-01", "2024-12-31"),
    ("evaluation", "2025-01-01", "2026-12-31"),
)


def load_earnings_events(path: str) -> dict[str, list[dict]]:
    """Load and validate point-in-time earnings events, sorted by event date."""
    required = {"symbol", "event_date", "eps_estimate", "reported_eps", "surprise_pct"}
    events: dict[str, list[dict]] = defaultdict(list)
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"earnings CSV missing columns: {', '.join(sorted(missing))}")
        for line, row in enumerate(reader, 2):
            try:
                event_date = date.fromisoformat(row["event_date"].strip())
                estimate = float(row["eps_estimate"])
                reported = float(row["reported_eps"])
                surprise = float(row["surprise_pct"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid earnings row {line}: {exc}") from exc
            symbol = row["symbol"].strip().upper()
            if not symbol or not all(math.isfinite(x) for x in (estimate, reported, surprise)):
                raise ValueError(f"invalid earnings row {line}: non-finite or empty value")
            events[symbol].append({"symbol": symbol, "event_date": event_date.isoformat(),
                                   "eps_estimate": estimate, "reported_eps": reported,
                                   "surprise_pct": surprise})
    for rows in events.values():
        rows.sort(key=lambda x: x["event_date"])
    return dict(events)


def earnings_gate(event_rows: list[dict], bars: list[dict], breakout_date: str) -> tuple[bool, dict]:
    """Apply the frozen catalyst gate using only information known by breakout."""
    bar_dates = [b["date"] for b in bars]
    bo = bisect_left(bar_dates, breakout_date)
    if bo >= len(bars) or bar_dates[bo] != breakout_date:
        return False, {"reason": "missing_breakout_bar"}
    eligible = [e for e in event_rows if e["event_date"] <= breakout_date]
    if not eligible:
        return False, {"reason": "no_completed_event"}
    event = eligible[-1]
    age = (date.fromisoformat(breakout_date) - date.fromisoformat(event["event_date"])).days
    if age < 0 or age > EVENT_LOOKBACK_DAYS:
        return False, {"reason": "event_outside_90_days", "event": event, "age_days": age}
    if event["surprise_pct"] <= 0:
        return False, {"reason": "nonpositive_surprise", "event": event, "age_days": age}
    event_pos = bisect_right(bar_dates, event["event_date"])
    if event_pos == 0 or event_pos >= len(bars) or event_pos > bo:
        return False, {"reason": "missing_completed_event_session", "event": event}
    pre_close = bars[event_pos - 1]["close"]
    next_open = bars[event_pos]["open"]
    gap_pct = (next_open / pre_close - 1) * 100 if pre_close else float("nan")
    if not math.isfinite(gap_pct) or gap_pct < MIN_GAP_PCT:
        return False, {"reason": "event_gap_below_2pct", "event": event,
                       "gap_pct": round(gap_pct, 4)}
    if bars[bo]["close"] <= pre_close:
        return False, {"reason": "price_not_above_pre_event_close", "event": event,
                       "pre_event_close": pre_close, "breakout_close": bars[bo]["close"]}
    return True, {"reason": "passed", "event": event, "age_days": age,
                  "gap_pct": round(gap_pct, 4), "pre_event_close": pre_close,
                  "breakout_close": bars[bo]["close"]}


def filter_detections(detections: dict, events: dict, prices: dict) -> tuple[dict, dict]:
    """Keep only breakout detections passing the predeclared earnings gate."""
    kept: dict[str, list[dict]] = {}
    audit: dict[str, int] = defaultdict(int)
    for symbol, rows in detections.items():
        accepted = []
        for det in rows:
            outcome = det.get("forward_outcome") or {}
            if outcome.get("outcome_type") != "breakout" or not outcome.get("exit_date"):
                continue
            passed, detail = earnings_gate(events.get(symbol.upper(), []), prices.get(symbol, []),
                                            outcome["exit_date"])
            audit[detail["reason"]] += 1
            if passed:
                copy = dict(det)
                copy["earnings_gate"] = detail
                accepted.append(copy)
        if accepted:
            kept[symbol] = accepted
    return kept, dict(sorted(audit.items()))


def _metrics(result: dict) -> dict:
    curve = result["equity_curve"]
    returns = [r["portfolio_return"] for r in curve]
    std = statistics.stdev(returns) if len(returns) > 1 else 0.0
    sharpe = statistics.fmean(returns) / std * math.sqrt(252) if std else 0.0
    trade_returns = [t["net_return_pct"] / 100 for t in result["trades"]]
    gains = sum(r for r in trade_returns if r > 0)
    losses = -sum(r for r in trade_returns if r < 0)
    return {**result["summary"], "sharpe": round(sharpe, 3),
            "profit_factor": round(gains / losses, 3) if losses else None}


def _subset(detections: dict, start: str, end: str) -> dict:
    out = {}
    for symbol, rows in detections.items():
        selected = []
        for detection in rows:
            exit_date = (detection.get("forward_outcome") or {}).get("exit_date")
            if exit_date and start <= exit_date <= end:
                selected.append(detection)
        if selected:
            out[symbol] = selected
    return out


def _clip_prices(prices: dict, start: str, end: str) -> dict:
    # Keep prior history for MA20/ADV planning while preventing marks beyond the segment.
    return {s: [b for b in bars if b["date"] <= end] for s, bars in prices.items()}


def run_experiment(detections: dict, events: dict, prices: dict, cfg: Config) -> dict:
    gated, audit = filter_detections(detections, events, prices)
    baseline = run_portfolio(detections, prices, cfg)
    catalyst = run_portfolio(gated, prices, cfg)
    segments = {}
    for name, start, end in SEGMENTS:
        px = _clip_prices(prices, start, end)
        base_seg = run_portfolio(_subset(detections, start, end), px, cfg)
        gate_seg = run_portfolio(_subset(gated, start, end), px, cfg)
        segments[name] = {"start": start, "end": end,
                          "baseline": _metrics(base_seg), "earnings_gated": _metrics(gate_seg)}
    return {"frozen_hypothesis": {"event_lookback_calendar_days": EVENT_LOOKBACK_DAYS,
            "minimum_positive_surprise_pct": "> 0", "minimum_next_session_gap_pct": MIN_GAP_PCT,
            "price_at_breakout_above_pre_event_close": True, "threshold_sweep": False},
            "config": cfg.__dict__, "gate_audit": audit, "segments": segments,
            "baseline": baseline, "earnings_gated": catalyst}


def _write_daily(path: str, curve: list[dict]) -> None:
    fields = ["date", "equity", "cash", "positions", "gross_exposure_pct", "portfolio_return",
              "spy_return", "excess_return", "exposure_matched_spy_return",
              "exposure_matched_excess_return"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(curve)


def _write_markdown(path: str, result: dict) -> None:
    lines = ["# Earnings-Catalyst VCP Experiment", "", "## Frozen gate", "",
             "Latest completed earnings event within 90 calendar days before breakout; positive "
             "EPS surprise; next-session opening gap of at least 2%; breakout close above the "
             "pre-event close. No threshold sweep was performed.", "", "## Chronological results", "",
             "| Segment | Variant | Trades | Return | CAGR | Sharpe | MDD | Profit factor |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for name, rows in result["segments"].items():
        for variant in ("baseline", "earnings_gated"):
            m = rows[variant]
            pf = "n/a" if m["profit_factor"] is None else f'{m["profit_factor"]:.2f}'
            lines.append(f'| {name} ({rows["start"][:4]}–{rows["end"][:4]}) | {variant} | '
                         f'{m["trades"]} | {m["total_return_pct"]:.2f}% | {m["cagr_pct"]:.2f}% | '
                         f'{m["sharpe"]:.2f} | {m["max_drawdown_pct"]:.2f}% | {pf} |')
    lines += ["", "## Gate audit", ""] + [f"- {k}: {v}" for k, v in result["gate_audit"].items()]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--earnings-csv", required=True)
    parser.add_argument("--output-dir", default="backtests/earnings_vcp")
    args = parser.parse_args()
    with open(args.backtest_json) as f:
        detections = json.load(f).get("detections_by_ticker") or {}
    client = CSVClient(args.price_csv)
    symbols = [r["symbol"] for r in client.get_constituents()] + ["SPY"]
    prices = {s: list(reversed(client.get_historical_prices(s, days=100_000)["historical"]))
              for s in symbols if client.get_historical_prices(s, days=1)}
    result = run_experiment(detections, load_earnings_events(args.earnings_csv), prices, Config())
    os.makedirs(args.output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    root = os.path.join(args.output_dir, f"earnings_vcp_{stamp}")
    with open(root + ".json", "w") as f:
        json.dump(result, f, indent=2)
    _write_daily(root + "_baseline_daily.csv", result["baseline"]["equity_curve"])
    _write_daily(root + "_gated_daily.csv", result["earnings_gated"]["equity_curve"])
    _write_markdown(root + ".md", result)
    print(root + ".json")
    print(root + ".md")


if __name__ == "__main__":
    main()
