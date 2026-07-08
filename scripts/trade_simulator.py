#!/usr/bin/env python3
"""Trade simulator — convert VCP backtest detections into Minervini-style
trades and report statistics with excess-over-SPY as the primary metric.

Trade rules:
- Only ``breakout`` detections generate trades (a stop-hit before the pivot
  cross means the trade was never entered).
- Entry: close of the first bar that closed above the pivot.
- Entry-extension cap: skip fills more than ``--max-extension-pct`` above the
  pivot (chasing extended breakouts is outside the Minervini playbook).
- Stop: ``max(last contraction low, entry * (1 - max_risk_pct/100))`` — the
  pattern stop, floored so no single trade risks more than ``--max-risk-pct``.
- Exit: first close below the stop, else close ``--max-hold-bars`` after
  entry, else the last available close (flagged "open").
- Optional point-in-time filter: drop detections made while the ticker was
  not an S&P 500 member (``--membership-csv``).

Usage:
    python3 scripts/trade_simulator.py backtests/vcp_backtest_YYYY.json \
        --membership-csv scripts/data/sp500_membership.csv
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from membership import is_member, load_membership  # noqa: E402
from yf_client import YFClient  # noqa: E402


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulate Minervini trades from a VCP backtest JSON"
    )
    parser.add_argument("backtest_json", help="Path to a vcp_backtest_*.json report")
    parser.add_argument(
        "--max-extension-pct",
        type=float,
        default=5.0,
        help="Skip entries more than this %% above pivot (default: 5.0)",
    )
    parser.add_argument(
        "--max-risk-pct",
        type=float,
        default=8.0,
        help="Stop floor: entry minus this %% (default: 8.0)",
    )
    parser.add_argument(
        "--max-hold-bars",
        type=int,
        default=60,
        help="Timeout exit after this many bars (default: 60)",
    )
    parser.add_argument(
        "--membership-csv",
        help="Point-in-time membership CSV; drops detections made while the "
        "ticker was not an index member",
    )
    parser.add_argument("--output-dir", default="backtests/", help="Report directory")
    parser.add_argument(
        "--sleep-secs", type=float, default=0.3, help="Pause between fetches"
    )
    args = parser.parse_args()
    if not (0.0 <= args.max_extension_pct <= 50.0):
        parser.error("--max-extension-pct must be 0-50")
    if not (1.0 <= args.max_risk_pct <= 50.0):
        parser.error("--max-risk-pct must be 1-50")
    if not (5 <= args.max_hold_bars <= 252):
        parser.error("--max-hold-bars must be 5-252")
    return args


def plan_trade(detection: dict, max_extension_pct: float, max_risk_pct: float) -> dict:
    """Decide whether a detection becomes a trade. Pure function.

    Returns ``{"action": "trade", "entry_date", "entry_price", "stop_price"}``
    or ``{"action": "skip", "reason": <no_fill|extended|missing_fields>}``.
    """
    fo = detection.get("forward_outcome") or {}
    if fo.get("outcome_type") != "breakout":
        return {"action": "skip", "reason": "no_fill"}

    entry_price = fo.get("exit_price")
    entry_date = fo.get("exit_date")
    pivot = fo.get("pivot_price")
    pattern_stop = fo.get("stop_price")
    if not entry_price or not entry_date or not pivot:
        return {"action": "skip", "reason": "missing_fields"}

    extension_pct = (entry_price / pivot - 1) * 100
    if extension_pct > max_extension_pct:
        return {"action": "skip", "reason": "extended"}

    risk_floor = entry_price * (1 - max_risk_pct / 100)
    stop = max(pattern_stop or 0, risk_floor)
    return {
        "action": "trade",
        "entry_date": entry_date,
        "entry_price": entry_price,
        "stop_price": stop,
        "extension_pct": round(extension_pct, 2),
    }


def simulate_exit(
    chrono_bars: list[dict], start_idx: int, stop_price: float, max_hold_bars: int
) -> dict | None:
    """Walk forward from ``start_idx`` and find the exit. Pure function.

    ``chrono_bars`` is oldest-first. Returns exit dict or None when there is
    not a single forward bar.
    """
    end = min(start_idx + 1 + max_hold_bars, len(chrono_bars))
    for j in range(start_idx + 1, end):
        if chrono_bars[j]["close"] < stop_price:
            return {
                "exit_date": chrono_bars[j]["date"],
                "exit_price": chrono_bars[j]["close"],
                "hold_bars": j - start_idx,
                "exit_reason": "stop",
            }
    j = min(start_idx + max_hold_bars, len(chrono_bars) - 1)
    if j <= start_idx:
        return None
    reason = "timeout" if j == start_idx + max_hold_bars else "open"
    return {
        "exit_date": chrono_bars[j]["date"],
        "exit_price": chrono_bars[j]["close"],
        "hold_bars": j - start_idx,
        "exit_reason": reason,
    }


def _to_chrono(bars: list[dict]) -> tuple[list[dict], dict[str, int]]:
    chrono = list(reversed(bars))
    return chrono, {b["date"]: i for i, b in enumerate(chrono)}


def _mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 2) if values else None


def _t_stat(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    sd = statistics.stdev(values)
    if sd == 0:
        return None
    return round(statistics.fmean(values) / (sd / math.sqrt(len(values))), 2)


def _bootstrap_ci(values: list[float], n_iter: int = 10000, seed: int = 42) -> list[float] | None:
    if len(values) < 6:
        return None
    rng = random.Random(seed)
    means = sorted(
        statistics.fmean(rng.choices(values, k=len(values))) for _ in range(n_iter)
    )
    return [round(means[int(0.025 * n_iter)], 2), round(means[int(0.975 * n_iter)], 2)]


def compute_trade_stats(trades: list[dict], skips: dict[str, int]) -> dict:
    """Aggregate per-trade results. Excess-over-SPY is the primary metric."""
    rets = [t["ret_pct"] for t in trades]
    excess = [t["excess_vs_spy_pct"] for t in trades if t["excess_vs_spy_pct"] is not None]
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    gross_loss = -sum(losses)
    return {
        "n_trades": len(trades),
        "skips": skips,
        "primary_mean_excess_vs_spy_pct": _mean(excess),
        "primary_t_stat_excess": _t_stat(excess),
        "primary_bootstrap_95ci_excess_pct": _bootstrap_ci(excess),
        "excess_win_rate_pct": round(
            sum(1 for e in excess if e > 0) / len(excess) * 100, 1
        )
        if excess
        else None,
        "mean_ret_pct": _mean(rets),
        "t_stat_ret": _t_stat(rets),
        "bootstrap_95ci_ret_pct": _bootstrap_ci(rets),
        "win_rate_pct": round(len(wins) / len(rets) * 100, 1) if rets else None,
        "avg_win_pct": _mean(wins),
        "avg_loss_pct": _mean(losses),
        "profit_factor": round(sum(wins) / gross_loss, 2) if gross_loss > 0 else None,
        "worst_trade_pct": round(min(rets), 2) if rets else None,
        "best_trade_pct": round(max(rets), 2) if rets else None,
        "avg_hold_bars": _mean([t["hold_bars"] for t in trades]),
        "exit_reasons": {
            r: sum(1 for t in trades if t["exit_reason"] == r)
            for r in ("stop", "timeout", "open")
        },
    }


def group_stats_by_year(trades: list[dict]) -> dict[str, dict]:
    years = sorted({t["entry_date"][:4] for t in trades})
    return {
        y: {
            "n_trades": len(batch),
            "mean_excess_vs_spy_pct": _mean(
                [t["excess_vs_spy_pct"] for t in batch if t["excess_vs_spy_pct"] is not None]
            ),
            "mean_ret_pct": _mean([t["ret_pct"] for t in batch]),
        }
        for y in years
        for batch in [[t for t in trades if t["entry_date"][:4] == y]]
    }


def _render_markdown(stats: dict, by_year: dict, metadata: dict) -> str:
    lines = [
        "# VCP Trade Simulation Report",
        "",
        f"Generated: {metadata['generated_at']}",
        f"Source backtest: {metadata['backtest_json']}",
        "",
        f"- Entry cap: ≤{metadata['max_extension_pct']}% above pivot | "
        f"Stop: max(contraction low, entry −{metadata['max_risk_pct']}%) | "
        f"Max hold: {metadata['max_hold_bars']} bars",
        f"- Membership filter: {metadata['membership_filter']}",
        "",
        "## Primary metric — excess over SPY (same holding windows)",
        "",
        f"- **Mean excess vs SPY: {stats['primary_mean_excess_vs_spy_pct']}%** "
        f"(t = {stats['primary_t_stat_excess']}, "
        f"95% CI {stats['primary_bootstrap_95ci_excess_pct']})",
        f"- Excess win rate (beat SPY): {stats['excess_win_rate_pct']}%",
        "",
        "## Raw trade statistics",
        "",
        f"- Trades: {stats['n_trades']} (skips: {stats['skips']})",
        f"- Mean return: {stats['mean_ret_pct']}% (t = {stats['t_stat_ret']}, "
        f"95% CI {stats['bootstrap_95ci_ret_pct']})",
        f"- Win rate: {stats['win_rate_pct']}% | avg win {stats['avg_win_pct']}% | "
        f"avg loss {stats['avg_loss_pct']}% | PF {stats['profit_factor']}",
        f"- Best {stats['best_trade_pct']}% | worst {stats['worst_trade_pct']}% | "
        f"avg hold {stats['avg_hold_bars']} bars | exits {stats['exit_reasons']}",
        "",
        "## By entry year",
        "",
        "| Year | Trades | Mean excess vs SPY | Mean return |",
        "|---|---|---|---|",
    ]
    lines.extend(
        f"| {y} | {s['n_trades']} | {s['mean_excess_vs_spy_pct']}% | {s['mean_ret_pct']}% |"
        for y, s in by_year.items()
    )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Excess vs SPY holds SPY over each trade's exact entry/exit dates.",
            "- Close-based fills and stops; no slippage/commissions (low-turnover,",
            "  large-cap assumption).",
            "- Overlapping trades are treated as independent observations; the",
            "  effective sample size is somewhat smaller than n_trades.",
            "",
        ]
    )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> None:
    with open(args.backtest_json) as f:
        payload = json.load(f)
    detections_by_ticker = payload.get("detections_by_ticker") or {}
    if not detections_by_ticker:
        print("ERROR: backtest JSON has no detections_by_ticker", file=sys.stderr)
        sys.exit(1)

    intervals = load_membership(args.membership_csv) if args.membership_csv else None
    scan_days = (payload.get("metadata") or {}).get("scan_days", 2520)
    fetch_days = scan_days + 500

    client = YFClient()
    print("Fetching SPY history...", end=" ", flush=True)
    spy_chrono, spy_idx = _to_chrono(
        client.get_historical_prices("SPY", days=fetch_days)["historical"]
    )
    print(f"OK ({len(spy_chrono)} bars)")

    trades: list[dict] = []
    skips = {"no_fill": 0, "extended": 0, "non_member": 0, "missing_fields": 0, "no_data": 0}
    active = {sym: dets for sym, dets in detections_by_ticker.items() if dets}
    for i, (sym, dets) in enumerate(sorted(active.items()), 1):
        print(f"[{i}/{len(active)}] {sym}...", end=" ", flush=True)
        try:
            hist = client.get_historical_prices(sym, days=fetch_days)
        except Exception as e:  # noqa: BLE001 — skip bad tickers, keep the run alive
            print(f"FETCH ERROR ({e})")
            skips = {**skips, "no_data": skips["no_data"] + len(dets)}
            continue
        chrono, idx_map = _to_chrono(hist.get("historical") or [] if hist else [])
        n_before = len(trades)
        for det in dets:
            if intervals is not None and not is_member(
                intervals, sym, det.get("as_of_date") or ""
            ):
                skips = {**skips, "non_member": skips["non_member"] + 1}
                continue
            plan = plan_trade(det, args.max_extension_pct, args.max_risk_pct)
            if plan["action"] == "skip":
                skips = {**skips, plan["reason"]: skips[plan["reason"]] + 1}
                continue
            start_idx = idx_map.get(plan["entry_date"])
            if start_idx is None:
                skips = {**skips, "no_data": skips["no_data"] + 1}
                continue
            exit_info = simulate_exit(
                chrono, start_idx, plan["stop_price"], args.max_hold_bars
            )
            if exit_info is None:
                skips = {**skips, "no_data": skips["no_data"] + 1}
                continue
            ret_pct = (exit_info["exit_price"] / plan["entry_price"] - 1) * 100
            si, sj = spy_idx.get(plan["entry_date"]), spy_idx.get(exit_info["exit_date"])
            spy_ret = (
                (spy_chrono[sj]["close"] / spy_chrono[si]["close"] - 1) * 100
                if si is not None and sj is not None and sj > si
                else None
            )
            trades.append(
                {
                    "symbol": sym,
                    "as_of_date": det.get("as_of_date"),
                    "composite_score": det.get("composite_score"),
                    **{k: v for k, v in plan.items() if k != "action"},
                    **exit_info,
                    "ret_pct": round(ret_pct, 2),
                    "spy_ret_pct": round(spy_ret, 2) if spy_ret is not None else None,
                    "excess_vs_spy_pct": round(ret_pct - spy_ret, 2)
                    if spy_ret is not None
                    else None,
                }
            )
        print(f"{len(trades) - n_before} trades")
        if args.sleep_secs > 0 and i < len(active):
            time.sleep(args.sleep_secs)

    trades = sorted(trades, key=lambda t: t["entry_date"])
    stats = compute_trade_stats(trades, skips)
    by_year = group_stats_by_year(trades)
    metadata = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "backtest_json": os.path.basename(args.backtest_json),
        "max_extension_pct": args.max_extension_pct,
        "max_risk_pct": args.max_risk_pct,
        "max_hold_bars": args.max_hold_bars,
        "membership_filter": args.membership_csv or "none",
    }

    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = os.path.join(args.output_dir, f"vcp_trades_{timestamp}.json")
    md_path = os.path.join(args.output_dir, f"vcp_trades_{timestamp}.md")
    with open(json_path, "w") as f:
        json.dump(
            {"metadata": metadata, "stats": stats, "by_year": by_year, "trades": trades},
            f,
            indent=2,
        )
    with open(md_path, "w") as f:
        f.write(_render_markdown(stats, by_year, metadata))

    print()
    print("=" * 70)
    print("Trade simulation complete")
    print("=" * 70)
    print(f"  Trades: {stats['n_trades']}  |  skips: {stats['skips']}")
    print(
        f"  PRIMARY — mean excess vs SPY: {stats['primary_mean_excess_vs_spy_pct']}% "
        f"(t = {stats['primary_t_stat_excess']}, "
        f"CI {stats['primary_bootstrap_95ci_excess_pct']})"
    )
    print(f"  Mean return: {stats['mean_ret_pct']}%  |  PF {stats['profit_factor']}  |  "
          f"worst {stats['worst_trade_pct']}%")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")


def main() -> None:
    run(parse_arguments())


if __name__ == "__main__":
    main()
