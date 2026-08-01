#!/usr/bin/env python3
"""Audit only repository-local 2006+ data and freeze its evidence boundary."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


CHRONOLOGY = {
    "discovery_train": ["2016-07-01", "2018-06-30"],
    "embargo": ["2018-07-01", "2018-12-31"],
    "validation": ["2019-01-01", "2021-12-31"],
    "best_available_frozen_oos": ["2022-01-01", "2026-03-31"],
}

CONTAMINATION = [
    {
        "period": "2006-01-01..2015-12-31",
        "status": "closed prior OOS; raw price CSV absent from current repository",
        "evidence": "backtests/pullback_oos/verification_report.md",
    },
    {
        "period": "2016-07-01..2018-06-30",
        "status": "heavily reused discovery/train",
        "evidence": "backtests/adjusted_v2/research_status_2026-08-01.md",
    },
    {
        "period": "2019-01-01..2021-12-31",
        "status": "reused validation/internal holdout",
        "evidence": "backtests/adjusted_v2/research_status_2026-08-01.md",
    },
    {
        "period": "2022-01-01..2026-03-31",
        "status": "opened exploratory replay; not untouched",
        "evidence": "backtests/exploratory_existing_data_replay/results/verification_report.md",
    },
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_price_csv(path: Path) -> dict:
    """Stream a long OHLCV CSV and validate its adjusted execution scale."""
    rows = duplicates = nonpositive = invalid_ohlc = invalid_rows = 0
    spy_rows = out_of_order = 0
    symbols: set[str] = set()
    first_date = last_date = ""
    prior_key: tuple[str, str] | None = None
    factor_min: float | None = None
    factor_max: float | None = None
    invalid_by_symbol: dict[str, int] = {}
    invalid_examples: list[dict] = []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"Ticker", "Date", "Open", "High", "Low", "Close",
                    "Adj Close", "Volume"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"{path}: missing required OHLCV columns")
        for row in reader:
            rows += 1
            symbol = (row.get("Ticker") or "").strip().upper()
            date = (row.get("Date") or "").strip()
            if not symbol or not date:
                invalid_rows += 1
                continue
            symbols.add(symbol)
            spy_rows += int(symbol == "SPY")
            first_date = date if not first_date or date < first_date else first_date
            last_date = date if date > last_date else last_date
            key = (symbol, date)
            if key == prior_key:
                duplicates += 1
            if prior_key and (symbol < prior_key[0]
                              or (symbol == prior_key[0] and date < prior_key[1])):
                out_of_order += 1
            prior_key = key
            try:
                open_, high, low, close, adjusted = (
                    float(row[name]) for name in
                    ("Open", "High", "Low", "Close", "Adj Close")
                )
                volume = float(row["Volume"])
            except (TypeError, ValueError):
                invalid_rows += 1
                continue
            if min(open_, high, low, close, adjusted) <= 0 or volume < 0:
                nonpositive += 1
                continue
            factor = adjusted / close
            factor_min = factor if factor_min is None else min(factor_min, factor)
            factor_max = factor if factor_max is None else max(factor_max, factor)
            adj_open, adj_high, adj_low = open_ * factor, high * factor, low * factor
            tolerance = max(1e-8, adj_high * 1e-8)
            if (adj_low > min(adj_open, adjusted) + tolerance
                    or adj_high + tolerance < max(adj_open, adjusted)
                    or adj_low > adj_high + tolerance):
                invalid_ohlc += 1
                invalid_by_symbol[symbol] = invalid_by_symbol.get(symbol, 0) + 1
                if len(invalid_examples) < 10:
                    invalid_examples.append({"symbol": symbol, "date": date,
                                             "open": open_, "high": high,
                                             "low": low, "close": close})
    return {
        "path": str(path), "sha256": _sha256(path), "rows": rows,
        "symbols_including_spy": len(symbols),
        "stock_symbols": len(symbols - {"SPY"}),
        "first_date": first_date, "last_date": last_date,
        "benchmark_present": spy_rows > 0, "spy_rows": spy_rows,
        "duplicate_adjacent_ticker_dates": duplicates,
        "out_of_order_rows": out_of_order,
        "invalid_rows": invalid_rows, "nonpositive_rows": nonpositive,
        "invalid_adjusted_ohlc_rows": invalid_ohlc,
        "invalid_adjusted_ohlc_by_symbol": invalid_by_symbol,
        "invalid_adjusted_ohlc_examples": invalid_examples,
        "adjustment_factor_min": factor_min,
        "adjustment_factor_max": factor_max,
        "execution_transform": "O/H/L scaled by Adj Close / Close; close=Adj Close; high/low normalized to contain open and close",
    }


def audit_membership(path: Path, price_symbols: set[str]) -> dict:
    intervals = 0
    symbols: set[str] = set()
    ended_symbols: set[str] = set()
    first_start = last_start = ""
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            symbol = (row.get("ticker") or "").strip().upper().replace(".", "-")
            start = (row.get("start_date") or "").strip()
            end = (row.get("end_date") or "").strip()
            if not symbol or not start:
                continue
            intervals += 1
            symbols.add(symbol)
            if end:
                ended_symbols.add(symbol)
            first_start = start if not first_start or start < first_start else first_start
            last_start = start if start > last_start else last_start
    return {
        "path": str(path), "sha256": _sha256(path), "intervals": intervals,
        "symbols": len(symbols), "first_start": first_start,
        "last_start": last_start, "symbols_with_ended_interval": len(ended_symbols),
        "priced_symbols_with_ended_interval": len(ended_symbols & price_symbols),
        "note": "ended membership interval is evidence of historical membership, not proof of delisting",
    }


def _price_symbols(path: Path) -> set[str]:
    with path.open(newline="") as handle:
        return {(row.get("Ticker") or "").strip().upper()
                for row in csv.DictReader(handle) if row.get("Ticker")}


def render_markdown(report: dict) -> str:
    lines = ["# Existing 2006+ Data Inventory and Evidence Boundary", "",
             "This audit uses repository-local files only. It performs no external",
             "lookup and does not inspect or request 2000–2005 data.", "",
             "## Executable price inputs", "",
             "| Input | Rows | Stocks | Dates | SPY | Adjusted OHLC flaws |",
             "|---|---:|---:|---|---|---:|"]
    for item in report["price_inputs"]:
        lines.append(f"| `{item['path']}` | {item['rows']:,} | {item['stock_symbols']} | "
                     f"{item['first_date']}..{item['last_date']} | "
                     f"{'yes' if item['benchmark_present'] else 'no'} | "
                     f"{item['invalid_adjusted_ohlc_rows']} |")
    membership = report["membership"]
    lines += ["", "## Membership and survivorship", "",
              f"- Historical membership: {membership['symbols']} symbols / "
              f"{membership['intervals']} intervals.",
              f"- Priced symbols with at least one ended membership interval: "
              f"{membership['priced_symbols_with_ended_interval']}.",
              "- 2006–2015 raw prices are absent; its prior 69.74% reconstruction "
              "exists only as coverage/report evidence and cannot run a new rule.",
              "- 2016–2026 coverage is 91.31% in the current execution file; "
              "2016–2018 yearly coverage remains below 90%, so unresolved "
              "survivorship must be disclosed and conservatively capped.", "",
              "## Source-bar integrity", "",
              "The source CSV contains 33 impossible OHLC envelopes: 30 HAR 2014",
              "lookback bars plus one each for EVHC (2015), ANDV (2018 embargo)",
              "and UA (2021 validation). The shared detector/portfolio loader",
              "repairs these outcome-free after adjustment by expanding high/low",
              "to contain open, close and the original range. No symbol is selected",
              "or removed based on a strategy outcome.", "",
              "## Contamination registry", ""]
    for item in report["contamination_registry"]:
        lines.append(f"- {item['period']}: **{item['status']}** "
                     f"(`{item['evidence']}`).")
    lines += ["", "## Frozen best-available chronology", ""]
    for key, value in report["chronology"].items():
        lines.append(f"- {key}: {value[0]} through {value[1]}")
    lines += ["", "No period is genuinely untouched. The 2022–2026Q1 segment may be",
              "used only as a pre-frozen best-available OOS for a genuinely new rule;",
              "it must carry the no-genuine-OOS/contamination limitation and must not",
              "be used to tune that rule.", "", "## Decision", "",
              "The executable research universe begins with 2014 lookback bars and",
              "supports signals from 2016 onward. Missing 2000–2005 data is out of",
              "scope and is not a blocker. Completion still requires >=20% net OOS",
              "CAGR, >=30 independent OOS trades, fixed portfolio controls, causal",
              "next-session execution, and transparent raw/final scoring.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--membership-csv", default="scripts/data/sp500_membership.csv")
    parser.add_argument("--price-csv", action="append", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()
    price_paths = [Path(value) for value in args.price_csv]
    price_inputs = [audit_price_csv(path) for path in price_paths]
    primary_symbols = _price_symbols(price_paths[0]) - {"SPY"}
    report = {
        "scope": "repository-local data from 2006 onward; no 2000-2005 search",
        "price_inputs": price_inputs,
        "membership": audit_membership(Path(args.membership_csv), primary_symbols),
        "known_coverage": {
            "2006_2015_prior_reconstruction_pct": 69.74,
            "2006_2015_raw_price_available": False,
            "2016_2026_current_execution_pct": 91.31,
        },
        "contamination_registry": CONTAMINATION,
        "chronology": CHRONOLOGY,
        "genuine_untouched_period_available": False,
        "applicable_score_cap_policy": {
            "unresolved_survivorship": 20,
            "no_genuine_untouched_oos_or_wfa": 55,
            "apply_lowest_applicable_cap": True,
        },
    }
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    output_md.write_text(render_markdown(report))
    print(json.dumps({"price_inputs": price_inputs,
                      "membership": report["membership"],
                      "chronology": CHRONOLOGY}, indent=2))


if __name__ == "__main__":
    main()
