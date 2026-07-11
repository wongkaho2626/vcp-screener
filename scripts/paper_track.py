#!/usr/bin/env python3
"""Prospective paper-tracking ledger for frozen VCP Strategy v1.

This is the only remaining path to evidence that could legitimately score
well: signals are recorded *before* their outcomes exist, so the record is
survivorship-free and out-of-sample by construction. Every rule below is a
verbatim restatement of `references/frozen_strategy_v1.md`; nothing here may
be tuned in response to accumulating results (that would be a v2 with a
restarted clock).

Workflow (run daily after the live screen, then commit `paper/` so git
history notarises the timestamps):

    python3 scripts/paper_track.py record reports/vcp_screener_<stamp>.json
    python3 scripts/paper_track.py mark              # yfinance (or --price-csv)
    python3 scripts/paper_track.py report

The report includes a "score readiness" panel: which Backtest Score hard
caps and evidence gates the accumulated record currently clears. A score of
70+ ("Promising") is only reachable once every gate passes — no amount of
re-analysis of the existing CSV backtests can get there, because their
survivorship limitation caps them at 20.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from bisect import bisect_left
from dataclasses import dataclass
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trade_simulator import _bootstrap_ci, _t_stat  # noqa: E402

TERMINAL = frozenset({"closed", "invalidated", "expired_no_breakout", "window_expired"})

PROTOCOL = {
    "version": "paper-v1",
    "strategy": "frozen VCP Strategy v1 (references/frozen_strategy_v1.md)",
    "record_gates": "valid VCP pattern; Edge Rank >= 30; pivot present; dedup on (symbol, pivot)",
    "breakout": "first close at/above pivot after recording, within 40 sessions",
    "entry": "first MA20 touch-and-hold within 15 bars of breakout; fill next session open",
    "stop": "max(final-contraction low, 8% below fill); exit next open after a close below it",
    "timeout_bars": 60,
    "cost_bps_per_side": 10,
    "primary_metric": "per-trade excess vs SPY (close-to-close over the holding dates)",
    "analysis_contract": "no interim tuning; scoring only at >= 30 closed trades and >= 1 year",
}


@dataclass(frozen=True)
class TrackConfig:
    watch_window_bars: int = 40
    pullback_window_bars: int = 15
    ma_period: int = 20
    max_hold_bars: int = 60
    max_risk_pct: float = 8.0
    cost_bps_per_side: float = 10.0


def new_ledger(created_at: str) -> dict:
    return {"protocol": {**PROTOCOL, "created_at": created_at}, "setups": [], "runs": []}


def ingest_candidates(ledger: dict, results: list[dict], as_of_date: str,
                      recorded_at: str, min_edge: float = 30.0) -> dict:
    """Append new setups from live-screen candidates, applying the frozen
    record gates. Returns an audit counter; mutates ``ledger`` in place."""
    audit: dict[str, int] = {}

    def count(reason: str) -> None:
        audit[reason] = audit.get(reason, 0) + 1

    existing = {(s["symbol"], round(s["pivot"], 2)) for s in ledger["setups"]}
    for row in results:
        symbol = row.get("symbol")
        pivot = (row.get("pivot_proximity") or {}).get("pivot_price")
        if not symbol or not pivot:
            count("missing_pivot")
            continue
        if not row.get("valid_vcp"):
            count("invalid_vcp")
            continue
        edge = row.get("edge_rank")
        if edge is None or edge < min_edge:
            count("edge_below_min")
            continue
        if (symbol, round(pivot, 2)) in existing:
            count("duplicate")
            continue
        contractions = (row.get("vcp_pattern") or {}).get("contractions") or []
        pattern_stop = contractions[-1].get("low_price") if contractions else None
        ledger["setups"].append({
            "id": f"{symbol}-{as_of_date}", "symbol": symbol,
            "sector": row.get("sector") or "Unknown", "as_of_date": as_of_date,
            "recorded_at": recorded_at, "pivot": pivot, "pattern_stop": pattern_stop,
            "edge_rank": edge, "suggested_weight_pct": row.get("suggested_weight_pct"),
            "status": "watching",
        })
        existing.add((symbol, round(pivot, 2)))
        count("recorded")
    return audit


def evaluate_setup(setup: dict, chrono: list[dict], cfg: TrackConfig = TrackConfig()) -> dict:
    """Re-derive the setup's full frozen-v1 lifecycle from oldest-first bars.

    Pure and idempotent: the outcome is a deterministic function of the
    recorded (as_of_date, pivot, pattern_stop) and the bar series, so marking
    twice can never drift. Returns a new dict; never mutates the input.
    """
    out = {k: v for k, v in setup.items()}
    dates = [b["date"] for b in chrono]
    pivot = setup["pivot"]
    pattern_stop = setup.get("pattern_stop") or 0.0
    start = bisect_left(dates, setup["as_of_date"])

    # Phase 1 — watch for the first close at/above the pivot.
    breakout = None
    watch_end = start + cfg.watch_window_bars
    for k in range(max(start, 1), min(watch_end, len(chrono))):
        if chrono[k]["close"] < pattern_stop:
            return {**out, "status": "invalidated", "invalidated_date": dates[k]}
        if chrono[k - 1]["close"] < pivot <= chrono[k]["close"]:
            breakout = k
            break
    if breakout is None:
        if len(chrono) >= watch_end:
            return {**out, "status": "expired_no_breakout"}
        return {**out, "status": "watching"}
    out["breakout_date"] = dates[breakout]

    # Phase 2 — first MA20 touch-and-hold within the pullback window.
    signal = None
    window_end = breakout + 1 + cfg.pullback_window_bars
    for j in range(breakout + 1, min(window_end, len(chrono))):
        close = chrono[j]["close"]
        if close < pattern_stop:
            return {**out, "status": "invalidated", "invalidated_date": dates[j]}
        if j + 1 < cfg.ma_period:
            continue
        ma = statistics.fmean(b["close"] for b in chrono[j - cfg.ma_period + 1:j + 1])
        if chrono[j].get("low", close) <= ma <= close:
            signal = j
            break
    if signal is None:
        if len(chrono) >= window_end:
            return {**out, "status": "window_expired"}
        return {**out, "status": "awaiting_pullback"}
    out["signal_date"] = dates[signal]

    # Phase 3 — fill at the next session's open, both sides costed.
    entry = signal + 1
    if entry >= len(chrono):
        return {**out, "status": "entry_pending"}
    one_way = cfg.cost_bps_per_side / 10_000
    fill = chrono[entry]["open"] * (1 + one_way)
    stop = max(pattern_stop, fill * (1 - cfg.max_risk_pct / 100))
    out.update({"entry_date": dates[entry], "entry_price": round(fill, 4),
                "stop": round(stop, 4)})

    # Phase 4 — exit next open after a close below the stop, else 60-bar timeout.
    exit_idx, reason = None, None
    for k in range(entry, len(chrono)):
        if k - entry >= cfg.max_hold_bars:
            exit_idx, reason = k, "timeout"
            break
        if chrono[k]["close"] < stop:
            if k + 1 >= len(chrono):
                return {**out, "status": "exit_pending"}
            exit_idx, reason = k + 1, "stop"
            break
    if exit_idx is None:
        return {**out, "status": "open"}
    exit_price = chrono[exit_idx]["open"] * (1 - one_way)
    return {**out, "status": "closed", "exit_date": dates[exit_idx],
            "exit_price": round(exit_price, 4), "exit_reason": reason,
            "holding_bars": exit_idx - entry,
            "net_return_pct": round((exit_price / fill - 1) * 100, 2)}


def attach_excess(trade: dict, spy_chrono: list[dict]) -> dict:
    """Per-trade excess vs SPY close-to-close over the holding dates. Pure."""
    closes = {b["date"]: b["close"] for b in spy_chrono}
    spy_in = closes.get(trade.get("entry_date"))
    spy_out = closes.get(trade.get("exit_date"))
    if not spy_in or not spy_out:
        return {**trade, "excess_vs_spy_pct": None}
    spy_ret = (spy_out / spy_in - 1) * 100
    return {**trade, "spy_return_pct": round(spy_ret, 2),
            "excess_vs_spy_pct": round(trade["net_return_pct"] - spy_ret, 4)}


def ledger_stats(setups: list[dict]) -> dict:
    status_counts: dict[str, int] = {}
    for s in setups:
        status_counts[s["status"]] = status_counts.get(s["status"], 0) + 1
    closed = [s for s in setups if s["status"] == "closed"]
    nets = [s["net_return_pct"] for s in closed]
    excess = [s["excess_vs_spy_pct"] for s in closed
              if s.get("excess_vs_spy_pct") is not None]
    gains = sum(r for r in nets if r > 0)
    losses = -sum(r for r in nets if r < 0)
    span_days = None
    entries = sorted(s["entry_date"] for s in closed if s.get("entry_date"))
    exits = sorted(s["exit_date"] for s in closed if s.get("exit_date"))
    if entries and exits:
        try:
            span_days = (date.fromisoformat(exits[-1]) - date.fromisoformat(entries[0])).days
        except ValueError:
            span_days = None
    return {
        "setups": len(setups), "status_counts": status_counts,
        "closed_trades": len(closed),
        "wins": sum(1 for r in nets if r > 0),
        "win_rate_pct": round(100 * sum(1 for r in nets if r > 0) / len(nets), 1) if nets else None,
        "mean_net_pct": round(statistics.fmean(nets), 2) if nets else None,
        "mean_excess_pct": round(statistics.fmean(excess), 2) if excess else None,
        "t_stat_excess": _t_stat(excess),
        "excess_ci_95": _bootstrap_ci(excess),
        "profit_factor": (round(gains / losses, 2) if losses
                          else (math.inf if gains else None)),
        "first_entry": entries[0] if entries else None,
        "last_exit": exits[-1] if exits else None,
        "span_days": span_days,
    }


def score_readiness(stats: dict) -> list[dict]:
    """Which Backtest Score hard caps and evidence gates the record clears.

    The first four are the caps that keep every CSV backtest at <= 55 (and
    survivorship at <= 20); prospective data clears two of them by
    construction. The rest are the evidence a 70+ 'Promising' verdict needs.
    """
    n = stats["closed_trades"]
    span = stats.get("span_days")
    t = stats.get("t_stat_excess")
    mean_excess = stats.get("mean_excess_pct")
    pf = stats.get("profit_factor")
    return [
        {"gate": "at least 30 closed trades", "value": n, "passed": n >= 30,
         "why": "below 30 the score is hard-capped at 40"},
        {"gate": "at least 1 year of trade history", "value": span,
         "passed": bool(span and span >= 365),
         "why": "below 1 year the score is hard-capped at 40"},
        {"gate": "prospective data (survivorship-free)", "value": True, "passed": True,
         "why": "by construction; lifts the cap of 20 that binds all CSV backtests"},
        {"gate": "true out-of-sample", "value": True, "passed": True,
         "why": "signals recorded before outcomes; lifts the no-OOS cap of 55"},
        {"gate": "t-stat >= 2 on per-trade excess vs SPY", "value": t,
         "passed": bool(t is not None and t >= 2.0),
         "why": "statistical-significance component of a 70+ score"},
        {"gate": "positive mean excess vs SPY", "value": mean_excess,
         "passed": bool(mean_excess is not None and mean_excess > 0),
         "why": "no robustness result can rescue a negative edge"},
        {"gate": "profit factor >= 1.2", "value": pf,
         "passed": bool(pf is not None and pf >= 1.2),
         "why": "trade-quality component of a 70+ score"},
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load_ledger(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return new_ledger(_now())


def _save_ledger(path: str, ledger: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(ledger, f, indent=2)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _price_source(price_csv: str | None):
    if price_csv:
        from csv_client import CSVClient  # noqa: PLC0415 — keep CLI deps lazy
        return CSVClient(price_csv)
    from yf_client import YFClient  # noqa: PLC0415
    return YFClient()


def cmd_record(args: argparse.Namespace) -> None:
    with open(args.screen_json) as f:
        report = json.load(f)
    results = report.get("results") or []
    generated = (report.get("metadata") or {}).get("generated_at") or _now()
    as_of = args.as_of or str(generated).split(" ")[0].split("T")[0]
    ledger = _load_ledger(args.ledger)
    audit = ingest_candidates(ledger, results, as_of, _now())
    ledger["runs"].append({"at": _now(), "action": "record",
                           "source": os.path.basename(args.screen_json), "audit": audit})
    _save_ledger(args.ledger, ledger)
    print(f"record audit: {json.dumps(audit)}")
    print(f"ledger: {args.ledger} ({len(ledger['setups'])} setups)")


def cmd_mark(args: argparse.Namespace) -> None:
    ledger = _load_ledger(args.ledger)
    client = _price_source(args.price_csv)

    def chrono(symbol: str) -> list[dict]:
        data = client.get_historical_prices(symbol, days=args.days) or {}
        return list(reversed(data.get("historical") or []))

    spy = chrono("SPY")
    updated, data_gaps = [], 0
    for setup in ledger["setups"]:
        if setup["status"] in TERMINAL and setup["status"] != "closed":
            updated.append(setup)
            continue
        if setup["status"] == "closed" and setup.get("excess_vs_spy_pct") is not None:
            updated.append(setup)
            continue
        bars = chrono(setup["symbol"])
        if not bars:
            data_gaps += 1
            updated.append(setup)
            continue
        result = setup if setup["status"] == "closed" else evaluate_setup(setup, bars)
        if result["status"] == "closed":
            result = attach_excess(result, spy)
        updated.append(result)
    ledger["setups"] = updated
    stats = ledger_stats(updated)
    ledger["runs"].append({"at": _now(), "action": "mark", "data_gaps": data_gaps,
                           "status_counts": stats["status_counts"]})
    _save_ledger(args.ledger, ledger)
    print(f"marked {len(updated)} setups ({data_gaps} data gaps)")
    print(json.dumps(stats["status_counts"], indent=2))


def cmd_report(args: argparse.Namespace) -> None:
    ledger = _load_ledger(args.ledger)
    stats = ledger_stats(ledger["setups"])
    gates = score_readiness(stats)
    lines = ["# Prospective Paper-Tracking Report", "",
             f"Generated {_now()} from `{args.ledger}`.", "",
             "## Protocol (frozen)", ""]
    lines += [f"- {k}: {v}" for k, v in ledger["protocol"].items()]
    lines += ["", "## Ledger state", "", "| Status | Count |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(stats["status_counts"].items())]
    lines += ["", "## Closed-trade statistics", "", "| Metric | Value |", "|---|---:|"]
    for key in ("closed_trades", "win_rate_pct", "mean_net_pct", "mean_excess_pct",
                "t_stat_excess", "excess_ci_95", "profit_factor",
                "first_entry", "last_exit", "span_days"):
        lines.append(f"| {key} | {stats.get(key)} |")
    lines += ["", "## Score readiness (path to 70+)", "",
              "| Gate | Value | Passed | Why it matters |", "|---|---:|---|---|"]
    for g in gates:
        lines.append(f'| {g["gate"]} | {g["value"]} | {"yes" if g["passed"] else "NO"} '
                     f'| {g["why"]} |')
    caps_clear = all(g["passed"] for g in gates[:4])
    evidence = all(g["passed"] for g in gates)
    lines += ["", f"- Hard caps cleared: {'yes' if caps_clear else 'not yet'}",
              f"- Evidence currently supports a 70+ score: {'yes' if evidence else 'no'}",
              "", "Run the backtest-analyst skill on this ledger for the full scored report",
              "once every gate above passes. Do not tune the strategy in response to",
              "interim readings — that voids the prospective contract."]
    text = "\n".join(lines) + "\n"
    os.makedirs(args.output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = os.path.join(args.output_dir, f"paper_report_{stamp}.md")
    with open(path, "w") as f:
        f.write(text)
    print(text)
    print(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn in (("record", cmd_record), ("mark", cmd_mark), ("report", cmd_report)):
        p = sub.add_parser(name)
        p.add_argument("--ledger", default="paper/ledger.json")
        p.set_defaults(fn=fn)
        if name == "record":
            p.add_argument("screen_json")
            p.add_argument("--as-of", help="Override the screen's as-of date (YYYY-MM-DD)")
        if name == "mark":
            p.add_argument("--price-csv", help="Offline CSV source (default: yfinance)")
            p.add_argument("--days", type=int, default=400)
        if name == "report":
            p.add_argument("--output-dir", default="paper/reports")
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
