#!/usr/bin/env python3
"""M.E.T. framework experiment — mechanizable slice of the M.E.T.A. playbook.

Takes the accepted trades of a ``vcp_trades_*.json`` and tests whether the
mechanizable parts of the M.E.T. framework improve excess-vs-SPY:

Entry edges (computed at the entry bar, history-only, no lookahead):
  - trend      : 200MA rising over the last 20 bars AND close above it
  - ma_support : a low in the last 15 bars touched the 10/20/50MA (within 2%)
                 and closed at/above it, and the current close still holds it
  - low_vol    : mean volume of down bars (last 10) < 0.7 x mean volume of
                 up bars (last 30) — the "low volume pullback" edge
  - tight_risk : entry-to-stop risk <= 5% (a 20% move = 4R, so 4:1 is at
                 least geometrically available)

Exit rules (re-simulated over the same entries via simulate_exit):
  - ma_break 10/20/50 : sell into weakness on a close below the SMA
  - PT 4R             : sell into strength at 4 x initial risk
  - combos with the baseline hard stop + 60-bar timeout

NOT mechanized (and deliberately omitted): trendline touches, resistance-flip
zones, profit-cushion position sizing, strategy-market fit switching — these
are discretionary/portfolio-level and cannot be scored per trade honestly.

Usage:
    python3 scripts/meta_experiment.py backtests/.../vcp_trades_X.json \
        --price-csv SP500_Historical_Data.csv
"""

from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trade_simulator import _bootstrap_ci, _t_stat, _to_chrono, simulate_exit  # noqa: E402
from yf_client import YFClient  # noqa: E402

TIGHT_RISK_MAX_PCT = 5.0


# ---------------------------------------------------------------------------
# Pure feature functions (M.E.T. edges)
# ---------------------------------------------------------------------------

def sma_at(chrono: list[dict], idx: int, period: int, key: str = "close") -> float | None:
    """Simple MA of ``key`` over the ``period`` bars ending at ``idx``."""
    if idx < 0 or idx + 1 < period:
        return None
    return st.fmean(b[key] for b in chrono[idx - period + 1 : idx + 1])


def ma200_uptrend(chrono: list[dict], i: int, period: int = 200, slope_bars: int = 20) -> bool:
    """Long-term trend edge: MA rising over ``slope_bars`` and close above it."""
    now = sma_at(chrono, i, period)
    then = sma_at(chrono, i - slope_bars, period)
    if now is None or then is None:
        return False
    return now > then and chrono[i]["close"] > now


def ma_support_edge(
    chrono: list[dict], i: int,
    periods: tuple[int, ...] = (10, 20, 50), lookback: int = 15, touch_pct: float = 2.0,
) -> bool:
    """MA-support edge: a recent low touched an MA and held, and the current
    close still sits at/above that MA (support not currently broken)."""
    for p in periods:
        current_ma = sma_at(chrono, i, p)
        if current_ma is None or chrono[i]["close"] < current_ma:
            continue
        for k in range(max(0, i - lookback + 1), i + 1):
            m = sma_at(chrono, k, p)
            if m is None:
                continue
            low = chrono[k].get("low", chrono[k]["close"])
            if low <= m * (1 + touch_pct / 100) and chrono[k]["close"] >= m:
                return True
    return False


def low_volume_pullback(
    chrono: list[dict], i: int,
    down_window: int = 10, up_window: int = 30, ratio: float = 0.7,
) -> bool:
    """Volume edge: down-bar volume (recent) dries up vs up-bar volume."""
    down_vols = [
        chrono[k]["volume"]
        for k in range(max(1, i - down_window + 1), i + 1)
        if chrono[k]["close"] < chrono[k - 1]["close"]
    ]
    up_vols = [
        chrono[k]["volume"]
        for k in range(max(1, i - up_window + 1), i + 1)
        if chrono[k]["close"] > chrono[k - 1]["close"]
    ]
    if not down_vols or not up_vols:
        return False
    return st.fmean(down_vols) < ratio * st.fmean(up_vols)


def trade_edges(chrono: list[dict], i: int, trade: dict) -> dict:
    """All M.E.T. edges for one trade at its entry bar. Pure."""
    risk_pct = (trade["entry_price"] - trade["stop_price"]) / trade["entry_price"] * 100
    return {
        "trend": ma200_uptrend(chrono, i),
        "ma_support": ma_support_edge(chrono, i),
        "low_vol": low_volume_pullback(chrono, i),
        "tight_risk": risk_pct <= TIGHT_RISK_MAX_PCT,
        "risk_pct": round(risk_pct, 2),
    }


# ---------------------------------------------------------------------------
# Experiment driver
# ---------------------------------------------------------------------------

def summarize(rows: list[dict]) -> dict | None:
    """Excess-vs-SPY summary for a list of {excess, ret} rows."""
    exc = [r["excess"] for r in rows if r["excess"] is not None]
    if len(exc) < 6:
        return None
    return {
        "n": len(exc),
        "mean_exc": round(st.fmean(exc), 2),
        "t": _t_stat(exc),
        "ci": _bootstrap_ci(exc),
        "median_exc": round(st.median(exc), 2),
        "exc_win_pct": round(sum(1 for e in exc if e > 0) / len(exc) * 100, 1),
    }


def _fmt(v):
    return f"{v}" if v is not None else "—"


def _print_row(label: str, s: dict | None) -> None:
    if s is None:
        print(f"{label:<26} (fewer than 6 trades)")
    else:
        print(f"{label:<26}{s['n']:>5}{_fmt(s['mean_exc']):>9}{_fmt(s['t']):>7}"
              f"{_fmt(s['median_exc']):>9}{_fmt(s['exc_win_pct']):>7}  CI {s['ci']}")


def _md_row(label: str, s: dict | None) -> str:
    if s is None:
        return f"| {label} | <6 trades | | | | |"
    return (f"| {label} | {s['n']} | {s['mean_exc']}% | {s['t']} | "
            f"{s['median_exc']}% | {s['exc_win_pct']}% |")


MD_TABLE_HEADER = [
    "| Config | N | Mean excess | t | Median excess | Win% |",
    "|---|---|---|---|---|---|",
]


def run(args: argparse.Namespace) -> None:
    payload = json.load(open(args.trades_json))
    trades = payload["trades"]
    max_hold = (payload.get("metadata") or {}).get("max_hold_bars", 60)
    fetch_days = 2520 + 500

    if args.price_csv:
        from csv_client import CSVClient  # noqa: PLC0415 — optional offline path

        client = CSVClient(args.price_csv)
        sleep_secs = 0.0
    else:
        client = YFClient()
        sleep_secs = args.sleep_secs

    print("Fetching SPY...", end=" ", flush=True)
    spy_chrono, spy_idx = _to_chrono(
        client.get_historical_prices("SPY", days=fetch_days)["historical"]
    )
    print(f"OK ({len(spy_chrono)} bars)")

    symbols = sorted({t["symbol"] for t in trades})
    bars: dict[str, tuple] = {}
    for i, sym in enumerate(symbols, 1):
        try:
            hist = client.get_historical_prices(sym, days=fetch_days)
            bars[sym] = _to_chrono((hist or {}).get("historical") or [])
        except Exception as e:  # noqa: BLE001 — skip bad tickers, keep the run alive
            print(f"[{sym}: fetch error {e}]", end=" ")
            bars[sym] = ([], {})
        if sleep_secs > 0 and i < len(symbols):
            time.sleep(sleep_secs)

    def spy_ret(entry_date: str, exit_date: str) -> float | None:
        si, sj = spy_idx.get(entry_date), spy_idx.get(exit_date)
        if si is None or sj is None or sj <= si:
            return None
        return (spy_chrono[sj]["close"] / spy_chrono[si]["close"] - 1) * 100

    # Attach edges once per trade (entry bar, history only).
    enriched: list[dict] = []
    for t in trades:
        chrono, idx_map = bars.get(t["symbol"], ([], {}))
        i = idx_map.get(t["entry_date"])
        if i is None:
            continue
        enriched.append({**t, "edges": trade_edges(chrono, i, t), "entry_idx": i})

    chart_edges = ("trend", "ma_support", "low_vol")

    def n_edges(t: dict) -> int:
        return sum(1 for e in chart_edges if t["edges"][e])

    def stored_rows(sub: list[dict]) -> list[dict]:
        return [{"excess": t["excess_vs_spy_pct"], "ret": t["ret_pct"]} for t in sub]

    def resim_rows(sub: list[dict], exit_kwargs_fn) -> list[dict]:
        rows = []
        for t in sub:
            chrono, _ = bars[t["symbol"]]
            ex = simulate_exit(chrono, t["entry_idx"], t["stop_price"], max_hold,
                               **exit_kwargs_fn(t))
            if ex is None:
                continue
            ret = (ex["exit_price"] / t["entry_price"] - 1) * 100
            sr = spy_ret(t["entry_date"], ex["exit_date"])
            rows.append({"excess": ret - sr if sr is not None else None, "ret": ret})
        return rows

    md_lines = ["# M.E.T. Framework Experiment", "",
                f"Source: {os.path.basename(args.trades_json)} | trades with data: "
                f"{len(enriched)}/{len(trades)}", ""]
    hdr = f"{'Config':<26}{'N':>5}{'meanExc':>9}{'t':>7}{'medExc':>9}{'win%':>7}"

    print("\n" + "=" * 84)
    print("ENTRY GATES — M.E.T. edges as trade filters (baseline stop+timeout exit)")
    print("=" * 84)
    print(hdr)
    entry_configs = [
        ("ALL (baseline)", lambda t: True),
        ("trend (200MA up)", lambda t: t["edges"]["trend"]),
        ("ma_support", lambda t: t["edges"]["ma_support"]),
        ("low_vol pullback", lambda t: t["edges"]["low_vol"]),
        ("tight_risk <=5%", lambda t: t["edges"]["tight_risk"]),
        ("edges >= 2 (of 3)", lambda t: n_edges(t) >= 2),
        ("edges == 3", lambda t: n_edges(t) == 3),
        ("edges>=2 + tight_risk", lambda t: n_edges(t) >= 2 and t["edges"]["tight_risk"]),
    ]
    md_lines += ["## Entry gates", "", *MD_TABLE_HEADER]
    for label, pred in entry_configs:
        s = summarize(stored_rows([t for t in enriched if pred(t)]))
        _print_row(label, s)
        md_lines.append(_md_row(label, s))

    print("\n" + "=" * 84)
    print("EXIT RULES — all trades, re-simulated (hard stop + 60-bar timeout retained)")
    print("=" * 84)
    print(hdr)
    exit_configs = [
        ("baseline (timeout)", lambda t: {}),
        ("MA10 break", lambda t: {"ma_exit_period": 10}),
        ("MA20 break", lambda t: {"ma_exit_period": 20}),
        ("MA50 break", lambda t: {"ma_exit_period": 50}),
        ("PT 4R", lambda t: {"profit_target_pct": 4 * t["edges"]["risk_pct"]}),
        ("PT 4R + MA20 break", lambda t: {"profit_target_pct": 4 * t["edges"]["risk_pct"],
                                          "ma_exit_period": 20}),
        ("PT 20% + MA20 break", lambda t: {"profit_target_pct": 20.0, "ma_exit_period": 20}),
    ]
    md_lines += ["", "## Exit rules (all trades)", "", *MD_TABLE_HEADER]
    for label, kw_fn in exit_configs:
        s = summarize(resim_rows(enriched, kw_fn))
        _print_row(label, s)
        md_lines.append(_md_row(label, s))

    print("\n" + "=" * 84)
    print("COMBOS — edges>=2 entry subset x M.E.T. exits")
    print("=" * 84)
    print(hdr)
    gated = [t for t in enriched if n_edges(t) >= 2]
    combo_configs = [
        ("edges>=2 + MA20 break", lambda t: {"ma_exit_period": 20}),
        ("edges>=2 + PT4R + MA20", lambda t: {"profit_target_pct": 4 * t["edges"]["risk_pct"],
                                              "ma_exit_period": 20}),
    ]
    md_lines += ["", "## Combos (edges>=2 entries)", "", *MD_TABLE_HEADER]
    for label, kw_fn in combo_configs:
        s = summarize(resim_rows(gated, kw_fn))
        _print_row(label, s)
        md_lines.append(_md_row(label, s))

    md_lines += ["", "## Notes", "",
                 "- Edges computed at the entry bar from history only (no lookahead).",
                 "- Omitted as non-mechanizable: trendlines, resistance-flip zones,",
                 "  profit-cushion sizing, market-fit switching.",
                 "- Excess vs SPY over each trade's exact entry/exit dates; no costs.", ""]

    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    md_path = os.path.join(args.output_dir, f"vcp_meta_experiment_{ts}.md")
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines))
    print(f"\nMarkdown: {md_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="M.E.T. framework gate/exit experiment")
    ap.add_argument("trades_json", help="Path to a vcp_trades_*.json report")
    ap.add_argument("--price-csv", help="Offline OHLCV CSV (CSVClient); else yfinance")
    ap.add_argument("--output-dir", default="backtests/")
    ap.add_argument("--sleep-secs", type=float, default=0.3)
    run(ap.parse_args())


if __name__ == "__main__":
    main()
