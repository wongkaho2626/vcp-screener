#!/usr/bin/env python3
"""Audit public stock archives against PIT S&P 500 member-day requirements."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def normalize(symbol: str) -> str:
    return symbol.strip().upper().replace(".", "-")


def membership_spans(path: Path, start: str, end: str) -> dict[str, list[tuple[str, str]]]:
    spans: dict[str, list[tuple[str, str]]] = defaultdict(list)
    with path.open(newline="") as file:
        for row in csv.DictReader(file):
            left = max(row["start_date"], start)
            right = min(row["end_date"] or end, end)
            if left <= right:
                spans[normalize(row["ticker"])].append((left, right))
    return dict(spans)


def stock_members(archive: zipfile.ZipFile) -> dict[str, str]:
    return {
        normalize(Path(name).stem.removesuffix(".us")): name
        for name in archive.namelist()
        if name.startswith("Data/Stocks/") and name.endswith(".txt")
    }


def archive_dates(archive: zipfile.ZipFile, name: str, start: str, end: str) -> set[str]:
    dates = set()
    for line in archive.read(name).decode(errors="ignore").splitlines()[1:]:
        value = line.split(",", 1)[0]
        if start <= value <= end:
            dates.add(value)
    return dates


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_archive(archive_path: Path, spans: dict[str, list[tuple[str, str]]],
                  start: str, end: str) -> dict:
    with zipfile.ZipFile(archive_path) as archive:
        stocks = stock_members(archive)
        calendar_name = stocks.get("AAPL")
        if calendar_name is None:
            raise ValueError("archive has no AAPL series for the trading calendar")
        calendar = archive_dates(archive, calendar_name, start, end)
        total = covered = 0
        per_year: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        gaps = []
        for symbol, intervals in spans.items():
            have = (archive_dates(archive, stocks[symbol], start, end)
                    if symbol in stocks else set())
            expected = {day for day in calendar
                        if any(left <= day <= right for left, right in intervals)}
            count = len(expected & have)
            total += len(expected)
            covered += count
            for day in expected:
                per_year[day[:4]][0] += 1
                per_year[day[:4]][1] += int(day in have)
            if count < len(expected):
                gaps.append({"symbol": symbol, "expected": len(expected),
                             "covered": count, "missing": len(expected) - count})
        return {
            "archive_sha256": sha256(archive_path),
            "archive_stock_files": len(stocks),
            "universe_symbols": len(spans),
            "matched_symbols": len(set(spans) & set(stocks)),
            "calendar_symbol": "AAPL",
            "calendar_sessions": len(calendar),
            "member_days": total,
            "covered_member_days": covered,
            "coverage_pct": round(covered / total * 100, 2) if total else 0.0,
            "per_year": {year: round(done / expected * 100, 2)
                         for year, (expected, done) in sorted(per_year.items())},
            "largest_gaps": sorted(gaps, key=lambda row: (-row["missing"], row["symbol"]))[:50],
        }


def wiki_coverage(path: Path, spans: dict[str, list[tuple[str, str]]]) -> dict:
    tickers = {normalize(line.strip().strip("|").strip()) for line in path.read_text().splitlines()
               if line.strip()}
    tickers.discard("TICKER")
    matched = set(spans) & tickers
    return {"ticker_count": len(tickers), "universe_symbols": len(spans),
            "matched_symbols": len(matched),
            "symbol_coverage_pct": round(len(matched) / len(spans) * 100, 2)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stock-archive", type=Path, required=True)
    ap.add_argument("--wiki-tickers", type=Path, required=True)
    ap.add_argument("--membership-csv", type=Path,
                    default=Path("scripts/data/sp500_membership.csv"))
    ap.add_argument("--start", default="2000-01-01")
    ap.add_argument("--end", default="2005-12-31")
    ap.add_argument("--output-dir", type=Path,
                    default=Path("backtests/data_source_audit"))
    args = ap.parse_args()
    spans = membership_spans(args.membership_csv, args.start, args.end)
    archive = audit_archive(args.stock_archive, spans, args.start, args.end)
    wiki = wiki_coverage(args.wiki_tickers, spans)
    report = {"generated_at": datetime.now().isoformat(timespec="seconds"),
              "period": [args.start, args.end],
              "required_member_day_coverage_pct": 90,
              "huge_stock_market_archive": archive,
              "quandl_wiki_ticker_list": wiki,
              "accepted": archive["coverage_pct"] >= 90,
              "decision": ("eligible for deeper identifier/corporate-action audit"
                           if archive["coverage_pct"] >= 90 else
                           "reject: member-day coverage below 90%")}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "public_oos_coverage.json"
    md_path = args.output_dir / "public_oos_coverage.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n")
    years = archive["per_year"]
    lines = ["# Public Untouched-OOS Data Coverage Audit", "",
             f"Period: {args.start} through {args.end}", "",
             "## Result", "",
             f"- Huge Stock Market archive: {archive['matched_symbols']}/"
             f"{archive['universe_symbols']} symbols; **{archive['coverage_pct']:.2f}%** "
             "member-day coverage.",
             f"- Per-year coverage: {', '.join(f'{year} {value:.2f}%' for year, value in years.items())}.",
             f"- Quandl WIKI ticker list: {wiki['matched_symbols']}/"
             f"{wiki['universe_symbols']} symbols ({wiki['symbol_coverage_pct']:.2f}%).", "",
             "**Decision: REJECT.** The tested archive is below the prespecified 90% "
             "member-day threshold. It also supplies ticker-keyed adjusted OHLCV, not "
             "permanent identifiers or explicit delisting returns, so passing coverage "
             "would still require a separate identity/corporate-action audit.", "",
             f"Archive SHA-256: `{archive['archive_sha256']}`", ""]
    md_path.write_text("\n".join(lines))
    print(json.dumps({"archive": archive, "wiki": wiki,
                      "accepted": report["accepted"]}, indent=2))
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
