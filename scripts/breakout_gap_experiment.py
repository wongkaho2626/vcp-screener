#!/usr/bin/env python3
"""Prespecified test of breakout-day opening-gap conditioning.

Frozen spec (backtests/breakout_gap/frozen_spec.md, declared 2026-07-17): trades
whose entry-day open gaps up >= +1.0% vs the prior session close form the "gap"
group; the metric is per-trade excess vs SPY from the input trade log; the test is
a Welch two-sample t on group means. The open is known before the same-day close
fill, so the feature is causal; no forward data is consulted. Thresholds 0.5% and
2.0% are reported as robustness checks only and are never adopted.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
from datetime import datetime

from csv_client import CSVClient

FROZEN_THRESHOLD_PCT = 1.0
SENSITIVITY_THRESHOLDS = (0.5, 2.0)
FOLD_BOUNDARY = "2021-01-01"


def gap_pct_for_entry(bars: list[dict], entry_date: str) -> float | None:
    """Opening gap of entry_date vs the last close strictly before it, in percent.

    ``bars`` is ascending by date. Returns None when either bar is missing.
    """
    entry_bar = None
    prior_bar = None
    for bar in bars:
        date = bar["date"]
        if date < entry_date:
            prior_bar = bar
        elif date == entry_date:
            entry_bar = bar
        else:
            break
    if entry_bar is None or prior_bar is None or not prior_bar["close"]:
        return None
    return (entry_bar["open"] / prior_bar["close"] - 1.0) * 100.0


def classify_trades(
    trades: list[dict], prices: dict[str, list[dict]], threshold_pct: float,
) -> tuple[list[dict], int]:
    """Return (new trade dicts annotated with gap_pct/gap_group, skipped count)."""
    classified = []
    skipped = 0
    for trade in trades:
        bars = prices.get(trade["symbol"], [])
        gap = gap_pct_for_entry(bars, trade["entry_date"])
        if gap is None:
            skipped += 1
            continue
        group = "gap" if gap >= threshold_pct else "no_gap"
        classified.append({**trade, "gap_pct": round(gap, 3), "gap_group": group})
    return classified, skipped


def welch_t(a: list[float], b: list[float]) -> tuple[float | None, float | None]:
    """Welch two-sample t statistic and degrees of freedom for mean(a) - mean(b)."""
    if len(a) < 2 or len(b) < 2:
        return None, None
    va, vb = statistics.variance(a), statistics.variance(b)
    sa, sb = va / len(a), vb / len(b)
    denom = math.sqrt(sa + sb)
    if denom == 0:
        return 0.0, float(len(a) + len(b) - 2)
    t = (statistics.fmean(a) - statistics.fmean(b)) / denom
    df_num = (sa + sb) ** 2
    df_den = sa**2 / (len(a) - 1) + sb**2 / (len(b) - 1)
    df = df_num / df_den if df_den else float(len(a) + len(b) - 2)
    return t, df


def two_sided_p(t: float | None, df: float | None) -> float | None:
    """Two-sided p-value; exact Student t via scipy when available, else normal."""
    if t is None:
        return None
    try:
        from scipy import stats  # anaconda python carries scipy

        return float(2 * stats.t.sf(abs(t), df))
    except ImportError:
        return math.erfc(abs(t) / math.sqrt(2))


def fold_split(trades: list[dict], boundary: str) -> tuple[list[dict], list[dict]]:
    early = [t for t in trades if t["entry_date"] < boundary]
    late = [t for t in trades if t["entry_date"] >= boundary]
    return early, late


def trim_top(trades: list[dict], n: int) -> list[dict]:
    """New list without the n highest-excess trades."""
    ranked = sorted(trades, key=lambda t: t["excess_vs_spy_pct"], reverse=True)
    return ranked[n:]


def group_excess(trades: list[dict], group: str) -> list[float]:
    return [t["excess_vs_spy_pct"] for t in trades if t["gap_group"] == group]


def analyze(trades: list[dict]) -> dict:
    """Group means, difference, and Welch t for one classified trade set."""
    gap = group_excess(trades, "gap")
    no_gap = group_excess(trades, "no_gap")
    t, df = welch_t(gap, no_gap)
    return {
        "n_gap": len(gap),
        "n_no_gap": len(no_gap),
        "mean_gap": round(statistics.fmean(gap), 3) if gap else None,
        "mean_no_gap": round(statistics.fmean(no_gap), 3) if no_gap else None,
        "diff": (
            round(statistics.fmean(gap) - statistics.fmean(no_gap), 3)
            if gap and no_gap else None
        ),
        "welch_t": round(t, 3) if t is not None else None,
        "df": round(df, 1) if df is not None else None,
        "p_two_sided": (
            round(two_sided_p(t, df), 4) if t is not None else None
        ),
    }


def run_experiment(trades: list[dict], prices: dict[str, list[dict]]) -> dict:
    classified, skipped = classify_trades(trades, prices, FROZEN_THRESHOLD_PCT)
    early, late = fold_split(classified, FOLD_BOUNDARY)
    result = {
        "frozen_threshold_pct": FROZEN_THRESHOLD_PCT,
        "n_input_trades": len(trades),
        "n_classified": len(classified),
        "n_skipped_missing_data": skipped,
        "pooled": analyze(classified),
        "folds": {
            f"2016-2020 (<{FOLD_BOUNDARY})": analyze(early),
            f"2021-2026 (>={FOLD_BOUNDARY})": analyze(late),
        },
        "outlier_trims": {
            "drop_top_5": analyze(trim_top(classified, 5)),
            "drop_top_10": analyze(trim_top(classified, 10)),
        },
        "sensitivity_not_adopted": {},
        "cross_universe": "R2K OHLCV not available offline; prong not run",
    }
    for thr in SENSITIVITY_THRESHOLDS:
        alt, _ = classify_trades(trades, prices, thr)
        result["sensitivity_not_adopted"][f"threshold_{thr}pct"] = analyze(alt)
    return result


def _load_prices(client: CSVClient, symbols: set[str]) -> dict[str, list[dict]]:
    prices = {}
    for symbol in sorted(symbols):
        data = client.get_historical_prices(symbol, days=10_000)
        if data:
            prices[symbol] = sorted(data["historical"], key=lambda b: b["date"])
    return prices


def _fill_alignment_check(trades: list[dict], prices: dict) -> dict:
    """Confirm entry_price matches the entry-day close (close-based fills)."""
    checked = mismatched = 0
    for trade in trades:
        bars = prices.get(trade["symbol"], [])
        entry_bar = next(
            (b for b in bars if b["date"] == trade["entry_date"]), None)
        if entry_bar is None:
            continue
        checked += 1
        if abs(entry_bar["close"] - trade["entry_price"]) / trade["entry_price"] > 0.01:
            mismatched += 1
    return {"checked": checked, "mismatched_gt_1pct": mismatched}


def _fmt_row(label: str, stats: dict) -> str:
    return (
        f"| {label} | {stats['n_gap']} | {stats['n_no_gap']} | "
        f"{stats['mean_gap']} | {stats['mean_no_gap']} | {stats['diff']} | "
        f"{stats['welch_t']} | {stats['p_two_sided']} |"
    )


def _write_markdown(path: str, result: dict, meta: dict) -> None:
    lines = [
        "# Breakout-Day Opening Gap Experiment",
        "",
        f"Generated: {meta['generated_at']}  ",
        f"Trades JSON: `{meta['trades_json']}`  ",
        f"Data source: `{meta['data_source']}`  ",
        f"Fill alignment check: {meta['fill_alignment']}  ",
        f"Frozen spec: `backtests/breakout_gap/frozen_spec.md` "
        f"(threshold {result['frozen_threshold_pct']}%; declared before results)",
        "",
        f"Input trades {result['n_input_trades']}, classified "
        f"{result['n_classified']}, skipped {result['n_skipped_missing_data']} "
        "(missing price bars).",
        "",
        "| Slice | n gap | n no-gap | mean gap | mean no-gap | diff (pp) | Welch t | p |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        _fmt_row("Pooled (frozen 1.0%)", result["pooled"]),
    ]
    for name, stats in result["folds"].items():
        lines.append(_fmt_row(f"Fold {name}", stats))
    for name, stats in result["outlier_trims"].items():
        lines.append(_fmt_row(name, stats))
    for name, stats in result["sensitivity_not_adopted"].items():
        lines.append(_fmt_row(f"{name} (robustness only)", stats))
    lines += [
        "",
        f"Cross-universe: {result['cross_universe']}.",
        "",
        "Metric: per-trade excess vs SPY over the trade's own holding dates, from",
        "the input trade log. Groups share the fill/cost model, so the difference",
        "is cost-invariant. Universe is survivorship-biased current constituents;",
        "all numbers are optimistic ceilings. Sensitivity rows are robustness",
        "checks, not a search; no variation is adopted.",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trades_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--output-dir", default="backtests/breakout_gap")
    args = parser.parse_args()

    with open(args.trades_json) as f:
        payload = json.load(f)
    trades = payload["trades"]

    client = CSVClient(args.price_csv)
    api_stats = client.get_api_stats()
    if not api_stats["data_source"].startswith("csv"):
        raise SystemExit(
            f"refusing to run: data_source={api_stats['data_source']!r} is not csv")

    prices = _load_prices(client, {t["symbol"] for t in trades})
    result = run_experiment(trades, prices)
    meta = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "trades_json": args.trades_json,
        "data_source": api_stats["data_source"],
        "fill_alignment": _fill_alignment_check(trades, prices),
    }

    os.makedirs(args.output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_path = os.path.join(args.output_dir, f"breakout_gap_{stamp}.json")
    md_path = os.path.join(args.output_dir, f"breakout_gap_{stamp}.md")
    with open(json_path, "w") as f:
        json.dump({"metadata": meta, "result": result}, f, indent=1)
    _write_markdown(md_path, result, meta)
    print(f"wrote {json_path}\nwrote {md_path}")
    print(json.dumps(result["pooled"], indent=1))


if __name__ == "__main__":
    main()
