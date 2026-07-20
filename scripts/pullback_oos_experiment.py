#!/usr/bin/env python3
"""Pre-2016 out-of-sample replication of the MA20 pullback entry.

Frozen spec: backtests/pullback_oos/frozen_spec.md (declared before any
result was computed). For every breakout detection in a 2006-2015
``vcp_backtest_*.json`` this compares, on the SAME pattern, the shipped
breakout entry (breakout-bar close, skipped when >5% extended above the
pivot) against the shipped MA20 touch-and-hold pullback entry
(``plan_pullback_entry``, window 15, ma_period 20). Both legs exit via
``simulate_exit`` (stop = max(pattern stop, entry - 8%) + 60-bar timeout).
Metric: paired delta of per-trade excess vs the synthetic equal-weight
benchmark ("SPY" from csv_client). Declared direction: delta > 0
(replication of the +1.36 pp / t 3.13 result validated on 2016-2026).
Signals consult only bars at/after the breakout; ``forward_outcome`` is
used solely to locate the breakout bar and pattern levels fixed at
detection time. Round-trip costs cancel exactly in the paired delta.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from membership import is_member, load_membership  # noqa: E402
from pullback_experiment import plan_pullback_entry  # noqa: E402
from trade_simulator import _bootstrap_ci, _t_stat, _to_chrono, simulate_exit  # noqa: E402

FOLDS = (
    ("2006-2010", "2006-01-01", "2010-12-31"),
    ("2011-2015", "2011-01-01", "2015-12-31"),
)

# Frozen parameters — shipped defaults, zero re-tuning (see frozen_spec.md).
TOLERANCE_PCT = 2.0
MAX_EXTENSION_PCT = 5.0
MAX_RISK_PCT = 8.0
MAX_HOLD_BARS = 60
PULLBACK_WINDOW = 15
PULLBACK_MA_PERIOD = 20
TRIM_KS = (5, 10)
COST_BPS_PER_SIDE = (10, 20, 50, 100)


def filter_member_detections(
    detections_by_ticker: dict[str, list[dict]],
    intervals: dict[str, list[tuple[str, str]]] | None,
) -> tuple[dict[str, list[dict]], int]:
    """Keep only detections whose symbol was an index member on `as_of_date`
    (PIT gate, see pit_addendum.md). Pure; returns (kept, dropped_count).
    With `intervals` None the input passes through unchanged."""
    if intervals is None:
        return detections_by_ticker, 0
    kept: dict[str, list[dict]] = {}
    dropped = 0
    for sym, dets in detections_by_ticker.items():
        member = [d for d in dets
                  if is_member(intervals, sym, d.get("as_of_date") or "")]
        dropped += len(dets) - len(member)
        if member:
            kept[sym] = member
    return kept, dropped


def parse_folds(specs: list[str]) -> tuple[tuple[str, str, str], ...]:
    """Parse repeatable --fold specs of the form ``label:start:end``."""
    folds = []
    for spec in specs:
        parts = spec.split(":")
        if len(parts) != 3 or not all(parts):
            raise ValueError(f"--fold expects label:start:end, got '{spec}'")
        label, start, end = parts
        if end < start:
            raise ValueError(f"--fold '{spec}': end before start")
        folds.append((label, start, end))
    return tuple(folds)


def assign_fold(
    date_str: str | None,
    folds: tuple[tuple[str, str, str], ...] = FOLDS,
) -> str | None:
    """Fold label for a YYYY-MM-DD pair date; None outside all folds."""
    if not date_str:
        return None
    for label, start, end in folds:
        if start <= date_str <= end:
            return label
    return None


def trim_top(values: list[float], k: int) -> list[float]:
    """New list with the k largest values removed; never mutates input."""
    if k <= 0:
        return list(values)
    cutoff = sorted(values, reverse=True)[:k]
    remaining = list(values)
    for v in cutoff:
        remaining.remove(v)
    return remaining


def summarize_values(values: list[float]) -> dict | None:
    """n / mean / t / bootstrap CI / median / win%; None below 6 samples."""
    vals = [v for v in values if v is not None]
    if len(vals) < 6:
        return None
    return {
        "n": len(vals),
        "mean": round(st.fmean(vals), 3),
        "t": _t_stat(vals),
        "ci": _bootstrap_ci(vals),
        "median": round(st.median(vals), 3),
        "win": round(sum(1 for v in vals if v > 0) / len(vals) * 100, 1),
    }


def _leg_excess(chrono: list[dict], entry_idx: int, entry_price: float,
                pattern_stop: float | None, spy_ret, max_risk_pct: float,
                max_hold_bars: int) -> float | None:
    stop = max(pattern_stop or 0.0, entry_price * (1 - max_risk_pct / 100))
    ex = simulate_exit(chrono, entry_idx, stop, max_hold_bars)
    if ex is None:
        return None
    ret = (ex["exit_price"] / entry_price - 1) * 100
    sr = spy_ret(chrono[entry_idx]["date"], ex["exit_date"])
    return ret - sr if sr is not None else None


def evaluate_detection(
    chrono: list[dict], idx_map: dict[str, int], det: dict, spy_ret,
    tolerance_pct: float = TOLERANCE_PCT,
    max_extension_pct: float = MAX_EXTENSION_PCT,
    max_risk_pct: float = MAX_RISK_PCT,
    max_hold_bars: int = MAX_HOLD_BARS,
    window: int = PULLBACK_WINDOW,
    ma_period: int = PULLBACK_MA_PERIOD,
) -> dict | None:
    """Paired record for one breakout detection, or None when the detection
    is not a breakout / lacks a locatable breakout bar. Pure.

    Returns ``{"pair_date", "bo_exc", "pb_exc", "delta", "status"}`` where
    status is paired / bo_only / pb_only / none and delta = pb_exc - bo_exc
    only when both legs traded.
    """
    fo = det.get("forward_outcome") or {}
    pivot, pattern_stop = fo.get("pivot_price"), fo.get("stop_price")
    if fo.get("outcome_type") != "breakout" or not pivot:
        return None
    bo_idx = idx_map.get(fo.get("exit_date"))
    if bo_idx is None:
        return None

    bo_price = fo.get("exit_price") or chrono[bo_idx]["close"]
    extension_pct = (bo_price / pivot - 1) * 100
    bo_exc = (
        _leg_excess(chrono, bo_idx, bo_price, pattern_stop, spy_ret,
                    max_risk_pct, max_hold_bars)
        if extension_pct <= max_extension_pct
        else None
    )

    wait_stop = pattern_stop or pivot * (1 - max_risk_pct / 100)
    plan = plan_pullback_entry(
        chrono, bo_idx, pivot, wait_stop,
        tolerance_pct=tolerance_pct, window=window, ma_period=ma_period,
    )
    pb_exc = (
        _leg_excess(chrono, plan["entry_idx"], plan["entry_price"],
                    pattern_stop, spy_ret, max_risk_pct, max_hold_bars)
        if plan is not None
        else None
    )

    if bo_exc is not None and pb_exc is not None:
        status = "paired"
    elif bo_exc is not None:
        status = "bo_only"
    elif pb_exc is not None:
        status = "pb_only"
    else:
        status = "none"
    return {
        "pair_date": chrono[bo_idx]["date"],
        "bo_exc": bo_exc,
        "pb_exc": pb_exc,
        "delta": pb_exc - bo_exc if status == "paired" else None,
        "status": status,
    }


def _leg_and_delta_stats(records: list[dict]) -> dict:
    return {
        "bo_exc": summarize_values([r["bo_exc"] for r in records]),
        "pb_exc": summarize_values([r["pb_exc"] for r in records]),
        "deltas": summarize_values(
            [r["delta"] for r in records if r["delta"] is not None]
        ),
    }


def aggregate_records(
    records: list[dict],
    folds: tuple[tuple[str, str, str], ...] = FOLDS,
) -> dict:
    """Pooled, per-fold, and trimmed summaries. Pure."""
    deltas = [r["delta"] for r in records if r["delta"] is not None]
    fold_stats = {
        label: _leg_and_delta_stats(
            [r for r in records if assign_fold(r.get("pair_date"), folds) == label]
        )
        for label, _, _ in folds
    }
    trims = {
        f"drop_top_{k}": summarize_values(trim_top(deltas, k)) for k in TRIM_KS
    }
    counts = {
        status: sum(1 for r in records if r["status"] == status)
        for status in ("paired", "bo_only", "pb_only", "none")
    }
    return {
        "pooled": _leg_and_delta_stats(records),
        "folds": fold_stats,
        "trims": trims,
        "counts": counts,
    }


def _fmt(v) -> str:
    return f"{v}" if v is not None else "—"


def _stats_row(label: str, s: dict | None) -> str:
    if s is None:
        return f"| {label} | <6 | — | — | — | — | — |"
    return (f"| {label} | {s['n']} | {s['mean']} | {_fmt(s['t'])} | "
            f"{_fmt(s['ci'])} | {s['median']} | {s['win']}% |")


def build_report(agg: dict, meta: dict) -> str:
    lines = [
        "# Pullback OOS Experiment — pre-2016 replication of the MA20 pullback entry",
        "",
        f"Generated: {meta['generated_at']}  ",
        f"Detections source: {meta['backtest_jsons']}  ",
        f"Price data: {meta['price_csv']} (data_source={meta['data_source']})  ",
        "Frozen spec: backtests/pullback_oos/frozen_spec.md (declared before results)",
        "",
        "Benchmark: synthetic equal-weight index of the surviving CSV universe",
        "(csv_client 'SPY') — NOT tradable SPY. Universe is survivorship-biased;",
        "absolute excess numbers are optimistic ceilings and context only.",
        "Primary statistic: paired delta (pullback minus breakout, same detection).",
        "",
        "## Counts",
        "",
        f"- breakout detections evaluated: {meta['n_detections']}",
        f"- paired (both legs traded): {agg['counts']['paired']}",
        f"- breakout leg only (no pullback fill): {agg['counts']['bo_only']}",
        f"- pullback leg only (breakout >5% extended): {agg['counts']['pb_only']}",
        f"- neither leg: {agg['counts']['none']}",
        "",
        "## Pooled (excess vs synthetic benchmark, %)",
        "",
        "| Series | N | Mean | t | 95% CI | Median | Win% |",
        "|---|---|---|---|---|---|---|",
        _stats_row("breakout leg", agg["pooled"]["bo_exc"]),
        _stats_row("pullback leg", agg["pooled"]["pb_exc"]),
        _stats_row("paired Δ (pb − bo)", agg["pooled"]["deltas"]),
        "",
        "## Fold split (paired Δ)",
        "",
        "| Fold | N | Mean | t | 95% CI | Median | Win% |",
        "|---|---|---|---|---|---|---|",
    ]
    for label in agg["folds"]:
        lines.append(_stats_row(label, agg["folds"][label]["deltas"]))
    lines += [
        "",
        "## Outlier trims (paired Δ)",
        "",
        "| Trim | N | Mean | t | 95% CI | Median | Win% |",
        "|---|---|---|---|---|---|---|",
    ]
    for k in TRIM_KS:
        lines.append(_stats_row(f"drop top {k}", agg["trims"][f"drop_top_{k}"]))
    pooled_bo = agg["pooled"]["bo_exc"]
    pooled_pb = agg["pooled"]["pb_exc"]
    lines += [
        "",
        "## Cost stress",
        "",
        "Both legs are one round trip on the same name, so per-side costs",
        "cancel exactly in the paired Δ (0.0 pp impact at every level).",
        "Context: absolute per-leg mean excess minus round-trip cost:",
        "",
        "| bps/side | breakout mean | pullback mean |",
        "|---|---|---|",
    ]
    for bps in COST_BPS_PER_SIDE:
        drag = 2 * bps / 100  # round trip, in pp
        bo = round(pooled_bo["mean"] - drag, 3) if pooled_bo else None
        pb = round(pooled_pb["mean"] - drag, 3) if pooled_pb else None
        lines.append(f"| {bps} | {_fmt(bo)} | {_fmt(pb)} |")
    lines += [
        "",
        "## Robustness-bar notes",
        "",
        "- Cross-universe prong NOT runnable: no pre-2016 R2K price CSV exists.",
        "  The 2016-2026 S&P + R2K result is the cross-period counterpart.",
        "- Declared direction (frozen spec): paired Δ > 0, t ≥ 2, same sign in",
        "  both folds, surviving drop-top-5/10 trims.",
        "",
    ]
    return "\n".join(lines)


def run(args: argparse.Namespace) -> None:
    detections_by_ticker: dict[str, list[dict]] = {}
    data_source = "unknown"
    for path in args.backtest_jsons:
        with open(path) as f:
            payload = json.load(f)
        data_source = (
            (payload.get("metadata") or {}).get("api_stats") or {}
        ).get("data_source", data_source)
        for sym, dets in (payload.get("detections_by_ticker") or {}).items():
            detections_by_ticker.setdefault(sym, []).extend(dets)
    # CSVHistoricalClient reports "csv"; CSVClient reports "csv:<path>".
    if not str(data_source).startswith("csv"):
        print(f"ERROR: detections data_source is '{data_source}', expected 'csv' "
              "(silent yfinance fallback guard)", file=sys.stderr)
        sys.exit(1)

    intervals = load_membership(args.membership_csv) if args.membership_csv else None
    detections_by_ticker, dropped_non_member = filter_member_detections(
        detections_by_ticker, intervals
    )
    if intervals is not None:
        print(f"Membership gate: dropped {dropped_non_member} non-member detections")

    from csv_client import CSVClient  # noqa: PLC0415 — offline only by design

    client = CSVClient(args.price_csv)
    fetch_days = 5040 + 500
    spy_chrono, spy_idx = _to_chrono(
        client.get_historical_prices("SPY", days=fetch_days)["historical"]
    )
    print(f"Benchmark bars: {len(spy_chrono)} (synthetic equal-weight)")

    def spy_ret(entry_date: str, exit_date: str) -> float | None:
        si, sj = spy_idx.get(entry_date), spy_idx.get(exit_date)
        if si is None or sj is None or sj <= si:
            return None
        return (spy_chrono[sj]["close"] / spy_chrono[si]["close"] - 1) * 100

    records: list[dict] = []
    n_detections = 0
    for sym in sorted(detections_by_ticker):
        try:
            hist = client.get_historical_prices(sym, days=fetch_days)
        except Exception:  # noqa: BLE001 — skip bad tickers, keep the run alive
            continue
        chrono, idx_map = _to_chrono((hist or {}).get("historical") or [])
        for det in detections_by_ticker[sym]:
            rec = evaluate_detection(chrono, idx_map, det, spy_ret)
            if rec is None:
                continue
            n_detections += 1
            records.append({**rec, "symbol": sym})

    folds = parse_folds(args.fold) if args.fold else FOLDS
    agg = aggregate_records(records, folds=folds)
    meta = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "backtest_jsons": ", ".join(args.backtest_jsons),
        "price_csv": args.price_csv,
        "data_source": data_source,
        "n_detections": n_detections,
        "membership_filter": args.membership_csv or "none",
        "dropped_non_member": dropped_non_member,
    }
    report = build_report(agg, meta)
    print(report)

    os.makedirs(args.output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    md_path = os.path.join(args.output_dir, f"pullback_oos_{ts}.md")
    json_path = os.path.join(args.output_dir, f"pullback_oos_{ts}.json")
    with open(md_path, "w") as f:
        f.write(report)
    with open(json_path, "w") as f:
        json.dump({"metadata": meta, "aggregate": agg, "records": records}, f,
                  indent=1)
    print(f"\nMarkdown: {md_path}\nJSON: {json_path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("backtest_jsons", nargs="+",
                    help="pre-2016 vcp_backtest_*.json report(s)")
    ap.add_argument("--price-csv", required=True,
                    help="Offline OHLCV CSV (CSVClient; synthetic benchmark)")
    ap.add_argument("--fold", action="append",
                    help="Fold spec label:start:end (repeatable); default = "
                    "the 2006-2010 / 2011-2015 pair")
    ap.add_argument("--membership-csv",
                    help="PIT membership intervals CSV; drops detections whose "
                    "symbol was not an index member on as_of_date (pit_addendum.md)")
    ap.add_argument("--output-dir", default="backtests/pullback_oos")
    run(ap.parse_args())


if __name__ == "__main__":
    main()
