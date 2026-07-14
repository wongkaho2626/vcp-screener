#!/usr/bin/env python3
"""Frozen 6-1 GICS industry-momentum gate for support-qualified VCPs.

The source backtest must already enforce ``near strong support <= 3%``.  For
each VCP detection date, the gate computes every stock's adjusted-close return
from trading day t-126 to t-21, equal-weights those returns within the current
GICS Industry snapshot, ranks industries cross-sectionally, and keeps the
top 30%.  Thresholds are constants so the declared test cannot be tuned via
the CLI.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import os
import statistics
from bisect import bisect_right
from datetime import datetime
from pathlib import Path

from csv_client import CSVClient
from portfolio_backtest import Config, run_portfolio

START_LAG = 126
END_LAG = 21
TOP_FRACTION = 0.30
SEGMENTS = (
    ("early", "2016-01-01", "2020-12-31"),
    ("late", "2021-01-01", "2026-12-31"),
)


def trailing_return(
    bars: list[dict], as_of_date: str, start_lag: int = START_LAG,
    end_lag: int = END_LAG,
) -> float | None:
    """Return from t-start_lag to t-end_lag using no post-as-of bars.

    ``bars`` must be oldest-first.  If ``as_of_date`` is not a trading day,
    the latest completed session before it is t=0.
    """
    if start_lag <= end_lag or end_lag < 0:
        raise ValueError("lags must satisfy start_lag > end_lag >= 0")
    dates = [bar["date"] for bar in bars]
    return _trailing_return_with_dates(bars, dates, as_of_date, start_lag, end_lag)


def _trailing_return_with_dates(
    bars: list[dict], dates: list[str], as_of_date: str,
    start_lag: int = START_LAG, end_lag: int = END_LAG,
) -> float | None:
    """Fast path for repeated calculations using a prebuilt date index."""
    as_of = bisect_right(dates, as_of_date) - 1
    start, end = as_of - start_lag, as_of - end_lag
    if as_of < 0 or start < 0 or end < 0:
        return None
    start_close = float(bars[start].get("close") or 0)
    end_close = float(bars[end].get("close") or 0)
    if start_close <= 0 or end_close <= 0:
        return None
    value = end_close / start_close - 1
    return value if math.isfinite(value) else None


def rank_industries(industry_returns: dict[str, float]) -> dict[str, dict]:
    """Rank industries descending and include ties at the top-30% cutoff."""
    valid = {
        industry: float(value)
        for industry, value in industry_returns.items()
        if math.isfinite(float(value))
    }
    if not valid:
        return {}
    ordered_values = sorted(valid.values(), reverse=True)
    top_count = max(1, math.ceil(len(ordered_values) * TOP_FRACTION))
    cutoff = ordered_values[top_count - 1]
    distinct = sorted(set(ordered_values), reverse=True)
    return {
        industry: {
            "rank": distinct.index(value) + 1,
            "industry_return": value,
            "passes": value >= cutoff,
            "top_count": top_count,
            "industry_count": len(valid),
            "cutoff_return": cutoff,
        }
        for industry, value in valid.items()
    }


def industry_ranks_on_date(
    as_of_date: str, prices: dict[str, list[dict]], industries: dict[str, str],
    price_dates: dict[str, list[str]] | None = None,
) -> dict[str, dict]:
    """Compute equal-weight 6-1 returns and cross-sectional industry ranks."""
    grouped: dict[str, list[float]] = collections.defaultdict(list)
    for symbol, industry in industries.items():
        if not industry or industry == "Unknown":
            continue
        bars = prices.get(symbol) or []
        if price_dates is None:
            value = trailing_return(bars, as_of_date)
        else:
            value = _trailing_return_with_dates(
                bars, price_dates.get(symbol) or [], as_of_date,
            )
        if value is not None:
            grouped[industry].append(value)
    ranked = rank_industries({
        industry: statistics.fmean(values)
        for industry, values in grouped.items()
        if values
    })
    for industry, detail in ranked.items():
        detail["members"] = len(grouped[industry])
    return ranked


def filter_detections(
    detections: dict[str, list[dict]], prices: dict[str, list[dict]],
    industries: dict[str, str],
) -> tuple[dict[str, list[dict]], dict[str, int]]:
    """Keep detections in top-30% industries and attach causal gate details."""
    kept: dict[str, list[dict]] = {}
    audit: collections.Counter[str] = collections.Counter()
    cache: dict[str, dict[str, dict]] = {}
    price_dates = {
        symbol: [bar["date"] for bar in bars]
        for symbol, bars in prices.items()
    }
    for symbol, rows in detections.items():
        industry = industries.get(symbol)
        accepted = []
        for detection in rows:
            as_of_date = detection.get("as_of_date") or ""
            if not industry or industry == "Unknown":
                audit["missing_industry"] += 1
                continue
            if not as_of_date:
                audit["missing_as_of_date"] += 1
                continue
            if as_of_date not in cache:
                cache[as_of_date] = industry_ranks_on_date(
                    as_of_date, prices, industries, price_dates,
                )
            ranks = cache[as_of_date]
            detail = ranks.get(industry)
            if detail is None:
                audit["insufficient_history"] += 1
                continue
            if not detail["passes"]:
                audit["not_top_30pct"] += 1
                continue
            annotated = dict(detection)
            annotated["industry_momentum_gate"] = {
                "industry": industry,
                "as_of_date": as_of_date,
                "start_lag_sessions": START_LAG,
                "end_lag_sessions": END_LAG,
                "top_fraction": TOP_FRACTION,
                **detail,
            }
            accepted.append(annotated)
            audit["passed"] += 1
        if accepted:
            kept[symbol] = accepted
    return kept, dict(sorted(audit.items()))


def load_classifications(path: str, hierarchy_path: str) -> dict[str, str]:
    rows = json.loads(Path(path).read_text())
    hierarchy = json.loads(Path(hierarchy_path).read_text())
    return {
        str(row.get("symbol") or "").upper(): hierarchy.get(
            str(row.get("subSector") or ""), "Unknown",
        )
        for row in rows
        if row.get("symbol")
    }


def metrics(result: dict) -> dict:
    returns = [row["portfolio_return"] for row in result["equity_curve"]]
    sd = statistics.stdev(returns) if len(returns) > 1 else 0.0
    sharpe = statistics.fmean(returns) / sd * math.sqrt(252) if sd else 0.0
    trade_returns = [trade["net_return_pct"] / 100 for trade in result["trades"]]
    gains = sum(value for value in trade_returns if value > 0)
    losses = -sum(value for value in trade_returns if value < 0)
    return {
        **result["summary"],
        "sharpe": round(sharpe, 3),
        "profit_factor": round(gains / losses, 3) if losses else None,
    }


def subset(detections: dict[str, list[dict]], start: str, end: str) -> dict[str, list[dict]]:
    return {
        symbol: selected
        for symbol, rows in detections.items()
        if (selected := [row for row in rows if start <= (row.get("as_of_date") or "") <= end])
    }


def clip_prices(prices: dict[str, list[dict]], end: str) -> dict[str, list[dict]]:
    return {symbol: [bar for bar in bars if bar["date"] <= end] for symbol, bars in prices.items()}


def write_daily(path: str, curve: list[dict]) -> None:
    fields = [
        "date", "equity", "cash", "positions", "gross_exposure_pct",
        "portfolio_return", "spy_return", "excess_return",
        "exposure_matched_spy_return", "exposure_matched_excess_return",
    ]
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(curve)


def write_markdown(path: str, result: dict) -> None:
    lines = [
        "# GICS Industry Momentum × Strong-Support VCP Experiment", "",
        "## Frozen hypothesis", "",
        "Source detections already require distance to strong support <=3%. At each VCP ",
        "detection date, compute each stock's adjusted-close return from t-126 to t-21, ",
        "equal-weight within the current GICS Industry snapshot, and retain industries ",
        "in the top 30%. Cutoff ties are retained; no threshold sweep was performed.", "",
        "> Classification caveat: GICS Industry is derived from a current Sub-Industry ",
        "> snapshot, not point-in-time.", "",
        f'> Benchmark: {result["price_data_stats"].get("benchmark", "unknown")}.', "",
        "## Gate audit", "",
    ]
    lines += [f"- {key}: {value}" for key, value in result["gate_audit"].items()]
    lines += [
        "", "## Portfolio results", "",
        "| Period | Variant | Trades | Return | CAGR | Sharpe | MDD | PF |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    periods = [("full", result["full_metrics"])] + [
        (f'{name} ({rows["start"][:4]}-{rows["end"][:4]})', rows)
        for name, rows in result["segments"].items()
    ]
    for period, rows in periods:
        for variant in ("support_only", "industry_gate"):
            row = rows[variant]
            pf = "n/a" if row["profit_factor"] is None else f'{row["profit_factor"]:.2f}'
            lines.append(
                f'| {period} | {variant} | {row["trades"]} | '
                f'{row["total_return_pct"]:.2f}% | {row["cagr_pct"]:.2f}% | '
                f'{row["sharpe"]:.2f} | {row["max_drawdown_pct"]:.2f}% | {pf} |'
            )
    Path(path).write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument(
        "--classifications",
        default="scripts/data/sp500_constituents.json",
    )
    parser.add_argument(
        "--gics-hierarchy",
        default="scripts/data/gics_subindustry_to_industry.json",
    )
    parser.add_argument("--output-dir", default="backtests/industry_momentum_vcp")
    args = parser.parse_args()

    payload = json.loads(Path(args.backtest_json).read_text())
    filters = (((payload.get("metadata") or {}).get("tuning_params") or {})
               .get("support_resistance_filters") or {})
    if filters.get("near_support_pct") != 3.0 or filters.get("min_support_strength") != "strong":
        parser.error("source backtest must enforce near-support=3 and minimum strength=strong")

    client = CSVClient(args.price_csv)
    symbols = [row["symbol"] for row in client.get_constituents()] + ["SPY"]
    prices = {
        symbol: list(reversed(history["historical"]))
        for symbol in symbols
        if (history := client.get_historical_prices(symbol, days=100_000))
    }
    industries = load_classifications(args.classifications, args.gics_hierarchy)
    support_only = payload.get("detections_by_ticker") or {}
    gated, audit = filter_detections(support_only, prices, industries)

    cfg = Config()
    support_result = run_portfolio(support_only, prices, cfg)
    gated_result = run_portfolio(gated, prices, cfg)
    segments = {}
    for name, start, end in SEGMENTS:
        clipped = clip_prices(prices, end)
        segments[name] = {
            "start": start,
            "end": end,
            "support_only": metrics(run_portfolio(subset(support_only, start, end), clipped, cfg)),
            "industry_gate": metrics(run_portfolio(subset(gated, start, end), clipped, cfg)),
        }

    result = {
        "frozen_hypothesis": {
            "source_support_distance_pct": 3.0,
            "source_minimum_support_strength": "strong",
            "classification_field": "GICS Industry (derived from subSector)",
            "classification_point_in_time": False,
            "start_lag_sessions": START_LAG,
            "end_lag_sessions": END_LAG,
            "industry_aggregation": "equal_weight",
            "top_fraction": TOP_FRACTION,
            "cutoff_ties_retained": True,
            "threshold_sweep": False,
        },
        "config": cfg.__dict__,
        "price_data_stats": client.get_api_stats(),
        "gate_audit": audit,
        "full_metrics": {
            "support_only": metrics(support_result),
            "industry_gate": metrics(gated_result),
        },
        "segments": segments,
        "support_only": support_result,
        "industry_gate": gated_result,
    }

    os.makedirs(args.output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    root = os.path.join(args.output_dir, f"industry_momentum_vcp_{stamp}")
    Path(root + ".json").write_text(json.dumps(result, indent=2) + "\n")
    write_markdown(root + ".md", result)
    write_daily(root + "_support_only_daily.csv", support_result["equity_curve"])
    write_daily(root + "_industry_gate_daily.csv", gated_result["equity_curve"])

    filtered_payload = dict(payload)
    filtered_payload["detections_by_ticker"] = gated
    filtered_payload["industry_momentum_gate"] = result["frozen_hypothesis"]
    filtered_path = root + "_filtered_backtest.json"
    Path(filtered_path).write_text(json.dumps(filtered_payload, indent=2) + "\n")

    print(json.dumps({
        "gate_audit": audit,
        "support_only": result["full_metrics"]["support_only"],
        "industry_gate": result["full_metrics"]["industry_gate"],
    }, indent=2))
    print(root + ".json")
    print(root + ".md")
    print(filtered_path)


if __name__ == "__main__":
    main()
