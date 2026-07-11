#!/usr/bin/env python3
"""Daily-marked VCP portfolio simulation with conservative execution.

The strategy specification is intentionally frozen: a breakout must be followed
by an MA20 touch-and-hold within 15 sessions, then the order fills at the next
session's open.  Edge Rank v2 is computed from same-date detection features and
only affects capped position size.  The simulator enforces cash, concurrent-name,
sector and trailing-ADV constraints and charges costs on both sides.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import os
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from csv_client import CSVClient  # noqa: E402
from edge_rank import DEFAULT_W_EXT, DEFAULT_W_RS, SIZING_MIN_EDGE, compute_edge_rank  # noqa: E402

LIVE_MA_PERIOD = 20
LIVE_WINDOW = 15
REBREAK_WINDOW = 60


def _plan_frozen_pullback(bars: list[dict], breakout_idx: int, stop: float) -> int | None:
    """MA20 touch-and-hold within 15 bars; matches pullback_experiment's rule."""
    for i in range(breakout_idx + 1, min(breakout_idx + 1 + LIVE_WINDOW, len(bars))):
        if bars[i]["close"] < stop:
            return None
        if i + 1 < LIVE_MA_PERIOD:
            continue
        ma = statistics.fmean(b["close"] for b in bars[i - LIVE_MA_PERIOD + 1:i + 1])
        if bars[i].get("low", bars[i]["close"]) <= ma <= bars[i]["close"]:
            return i
    return None


def _plan_rebreak_after_pullback(
    bars: list[dict], breakout_idx: int, stop: float, rebreak_window: int = REBREAK_WINDOW,
) -> int | None:
    """Close above the breakout-to-pullback high after a valid MA20 retest.

    The reference high is frozen on the pullback bar.  A close below the
    pattern stop invalidates the setup while waiting, and the rebreak must
    occur within ``rebreak_window`` sessions after the pullback.
    """
    pullback_idx = _plan_frozen_pullback(bars, breakout_idx, stop)
    if pullback_idx is None:
        return None
    prior_high = max(b.get("high", b["close"]) for b in bars[breakout_idx:pullback_idx + 1])
    end = min(pullback_idx + 1 + rebreak_window, len(bars))
    for i in range(pullback_idx + 1, end):
        if bars[i]["close"] < stop:
            return None
        if bars[i]["close"] > prior_high:
            return i
    return None


@dataclass(frozen=True)
class Config:
    initial_cash: float = 100_000.0
    max_positions: int = 10
    max_position_pct: float = 10.0
    max_sector_pct: float = 30.0
    adv_participation_pct: float = 1.0
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    max_risk_pct: float = 8.0
    max_hold_bars: int = 60
    min_edge: float = SIZING_MIN_EDGE
    edge_cap: float = 82.5


def _candidate_signals(
    detections: dict, prices: dict[str, list[dict]], cfg: Config,
    entry_rule: str = "pullback",
) -> list[dict]:
    """Build causal, next-bar-open orders from frozen MA20 pullback signals."""
    edges = compute_edge_rank(detections, DEFAULT_W_RS, DEFAULT_W_EXT)
    signals = []
    for sym, dets in detections.items():
        bars = prices.get(sym) or []
        idx = {b["date"]: i for i, b in enumerate(bars)}
        for det in dets:
            fo = det.get("forward_outcome") or {}
            if fo.get("outcome_type") != "breakout":
                continue
            edge = (edges.get((sym, det.get("as_of_date"))) or {}).get("edge_rank")
            if edge is None or edge < cfg.min_edge:
                continue
            bo = idx.get(fo.get("exit_date"))
            if bo is None or bo + 1 >= len(bars):
                continue
            pivot = fo.get("pivot_price")
            pattern_stop = fo.get("stop_price") or 0.0
            if not pivot:
                continue
            if entry_rule == "pullback":
                signal_idx = _plan_frozen_pullback(bars, bo, pattern_stop)
            elif entry_rule == "rebreak":
                signal_idx = _plan_rebreak_after_pullback(bars, bo, pattern_stop)
            else:
                raise ValueError(f"unknown entry rule: {entry_rule}")
            if signal_idx is None or signal_idx + 1 >= len(bars):
                continue
            fill_idx = signal_idx + 1
            signals.append({
                "symbol": sym, "sector": det.get("sector") or "Unknown",
                "signal_date": bars[signal_idx]["date"],
                "fill_date": bars[fill_idx]["date"], "fill_idx": fill_idx,
                "edge_rank": edge, "pattern_stop": pattern_stop,
            })
    return sorted(signals, key=lambda x: (x["fill_date"], -x["edge_rank"], x["symbol"]))


def _adv_dollars(bars: list[dict], i: int, lookback: int = 20) -> float:
    prior = bars[max(0, i - lookback):i]
    if not prior:
        return 0.0
    return statistics.fmean(b["close"] * b.get("volume", 0) for b in prior)


def run_portfolio(
    detections: dict, prices: dict[str, list[dict]], cfg: Config = Config(),
    entry_rule: str = "pullback",
) -> dict:
    """Run the portfolio. ``prices`` bars must be oldest-first."""
    signals = _candidate_signals(detections, prices, cfg, entry_rule=entry_rule)
    by_date = collections.defaultdict(list)
    for s in signals:
        by_date[s["fill_date"]].append(s)
    if not signals:
        return {"config": cfg.__dict__, "summary": {"signals": 0, "trades": 0,
                "end_value": cfg.initial_cash, "total_return_pct": 0.0,
                "cagr_pct": 0.0, "max_drawdown_pct": 0.0, "rejected": {}},
                "trades": [], "equity_curve": []}
    first_signal_date = min(s["fill_date"] for s in signals)
    dates = sorted({b["date"] for bars in prices.values() for b in bars
                    if b["date"] >= first_signal_date})
    index = {s: {b["date"]: i for i, b in enumerate(bars)} for s, bars in prices.items()}
    cash = cfg.initial_cash
    positions: dict[str, dict] = {}
    trades, equity_curve, rejected = [], [], collections.Counter()
    last_close: dict[str, float] = {}
    previous_equity = cfg.initial_cash
    previous_spy = None
    previous_gross_exposure = 0.0
    one_way_cost = (cfg.commission_bps + cfg.slippage_bps) / 10_000

    for date in dates:
        for sym, bars in prices.items():
            i = index[sym].get(date)
            if i is not None:
                last_close[sym] = bars[i]["close"]
        # Stops are conservatively filled at min(open, stop) when the day's low breaches.
        for sym, pos in list(positions.items()):
            i = index[sym].get(date)
            if i is None or i <= pos["entry_idx"]:
                continue
            bar = prices[sym][i]
            reason = None
            raw_exit = None
            if bar["low"] <= pos["stop"]:
                reason, raw_exit = "stop", min(bar["open"], pos["stop"])
            elif i - pos["entry_idx"] >= cfg.max_hold_bars:
                # The timeout is known only after the prior bar completes;
                # execute conservatively at this session's open.
                reason, raw_exit = "timeout", bar["open"]
            if reason:
                exit_price = raw_exit * (1 - one_way_cost)
                proceeds = pos["shares"] * exit_price
                cash += proceeds
                trades.append({**pos, "exit_date": date, "exit_price": round(exit_price, 4),
                               "exit_reason": reason,
                               "net_return_pct": round((exit_price / pos["entry_price"] - 1) * 100, 2)})
                del positions[sym]

        # Existing names cannot be doubled; strongest Edge Rank wins scarce capacity.
        for sig in by_date.get(date, []):
            sym = sig["symbol"]
            if sym in positions or len(positions) >= cfg.max_positions:
                rejected["duplicate_or_position_limit"] += 1
                continue
            i = index[sym].get(date)
            if i is None:
                rejected["missing_bar"] += 1
                continue
            bar = prices[sym][i]
            equity = cash + sum(
                p["shares"] * last_close.get(s, p["entry_price"])
                for s, p in positions.items()
            )
            sector_value = sum(p["shares"] * p["entry_price"] for p in positions.values()
                               if p["sector"] == sig["sector"])
            sector_room = max(0.0, equity * cfg.max_sector_pct / 100 - sector_value)
            edge_scale = min(sig["edge_rank"], cfg.edge_cap) / cfg.edge_cap
            target = equity * cfg.max_position_pct / 100 * edge_scale
            liquidity = _adv_dollars(prices[sym], i) * cfg.adv_participation_pct / 100
            budget = min(target, sector_room, liquidity, cash / (1 + one_way_cost))
            fill_price = bar["open"] * (1 + one_way_cost)
            shares = math.floor(budget / fill_price)
            if shares <= 0:
                rejected["cash_sector_or_liquidity"] += 1
                continue
            cost = shares * fill_price
            cash -= cost
            stop = max(sig["pattern_stop"], fill_price * (1 - cfg.max_risk_pct / 100))
            positions[sym] = {
                "symbol": sym, "sector": sig["sector"], "entry_date": date,
                "entry_idx": i, "entry_price": round(fill_price, 4), "shares": shares,
                "stop": round(stop, 4), "edge_rank": sig["edge_rank"],
                "signal_date": sig["signal_date"], "entry_adv_dollars": round(_adv_dollars(prices[sym], i), 2),
            }

        marked = cash
        for sym, pos in positions.items():
            marked += pos["shares"] * last_close.get(sym, pos["entry_price"])
        portfolio_return = marked / previous_equity - 1 if previous_equity else 0.0
        spy_close = last_close.get("SPY")
        spy_return = (spy_close / previous_spy - 1) if spy_close and previous_spy else 0.0
        matched_spy_return = spy_return * previous_gross_exposure
        gross_value = sum(pos["shares"] * last_close.get(sym, pos["entry_price"])
                          for sym, pos in positions.items())
        gross_exposure = gross_value / marked if marked else 0.0
        equity_curve.append({"date": date, "equity": round(marked, 2), "cash": round(cash, 2),
                             "positions": len(positions),
                             "gross_exposure_pct": round(gross_exposure * 100, 4),
                             "portfolio_return": round(portfolio_return, 8),
                             "spy_return": round(spy_return, 8),
                             "excess_return": round(portfolio_return - spy_return, 8),
                             "exposure_matched_spy_return": round(matched_spy_return, 8),
                             "exposure_matched_excess_return": round(portfolio_return - matched_spy_return, 8)})
        previous_equity = marked
        previous_gross_exposure = gross_exposure
        if spy_close:
            previous_spy = spy_close

    # Liquidate remaining positions at their final available close, including costs.
    for sym, pos in list(positions.items()):
        bar = prices[sym][-1]
        exit_price = bar["close"] * (1 - one_way_cost)
        cash += pos["shares"] * exit_price
        trades.append({**pos, "exit_date": bar["date"], "exit_price": round(exit_price, 4),
                       "exit_reason": "end_of_data",
                       "net_return_pct": round((exit_price / pos["entry_price"] - 1) * 100, 2)})
    end_value = cash
    peak, max_dd = cfg.initial_cash, 0.0
    for row in equity_curve:
        peak = max(peak, row["equity"])
        max_dd = min(max_dd, row["equity"] / peak - 1)
    years = max(len(equity_curve) / 252, 1 / 252)
    cagr = (end_value / cfg.initial_cash) ** (1 / years) - 1
    return {"config": cfg.__dict__, "summary": {"signals": len(signals), "trades": len(trades),
            "end_value": round(end_value, 2), "total_return_pct": round((end_value / cfg.initial_cash - 1) * 100, 2),
            "cagr_pct": round(cagr * 100, 2), "max_drawdown_pct": round(max_dd * 100, 2),
            "rejected": dict(rejected)}, "trades": trades, "equity_curve": equity_curve}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_json")
    ap.add_argument("--price-csv", required=True)
    ap.add_argument("--output-dir", default="backtests")
    ap.add_argument("--initial-cash", type=float, default=100_000)
    ap.add_argument("--commission-bps", type=float, default=5.0)
    ap.add_argument("--slippage-bps", type=float, default=5.0)
    args = ap.parse_args()
    payload = json.load(open(args.backtest_json))
    client = CSVClient(args.price_csv)
    symbols = [r["symbol"] for r in client.get_constituents()] + ["SPY"]
    prices = {sym: list(reversed(client.get_historical_prices(sym, days=100_000)["historical"]))
              for sym in symbols}
    if args.commission_bps < 0 or args.slippage_bps < 0:
        ap.error("cost inputs must be non-negative")
    result = run_portfolio(payload.get("detections_by_ticker") or {}, prices,
                           Config(initial_cash=args.initial_cash,
                                  commission_bps=args.commission_bps,
                                  slippage_bps=args.slippage_bps))
    os.makedirs(args.output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = os.path.join(args.output_dir, f"vcp_portfolio_{stamp}.json")
    with open(path, "w") as f:
        json.dump(result, f, indent=2)
    csv_path = path.replace(".json", "_daily.csv")
    with open(csv_path, "w", newline="") as f:
        fields = ["date", "equity", "cash", "positions", "gross_exposure_pct",
                  "portfolio_return", "spy_return", "excess_return",
                  "exposure_matched_spy_return", "exposure_matched_excess_return"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(result["equity_curve"])
    print(json.dumps(result["summary"], indent=2))
    print(path)
    print(csv_path)


if __name__ == "__main__":
    main()
