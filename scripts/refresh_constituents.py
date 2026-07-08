#!/usr/bin/env python3
"""
Refresh the bundled index-constituent snapshots the screener uses.

Yahoo Finance (yfinance) does not expose index membership, so the screener reads
static snapshots from ``data/<index>_constituents.json``. Membership drifts over
time — the S&P 500 changes a handful of names a year; the Russell 2000
reconstitutes wholesale every June — so refresh these periodically.

Usage
-----
    # Refresh the S&P 500 list (source: public GitHub datasets CSV)
    python3 refresh_constituents.py --index sp500

    # Refresh the Russell 2000 list (source: iShares IWM ETF holdings)
    python3 refresh_constituents.py --index russell2000

    # Refresh both
    python3 refresh_constituents.py --index both

Each writes ``data/<index>_constituents.json`` as a list of
``{symbol, name, sector, subSector}`` with symbols in Yahoo's class-share form
(e.g. ``BRK-B``). Network access to the relevant source domain is required at
runtime; no API key is needed.

Notes
-----
- **S&P 500** comes from ``github.com/datasets/s-and-p-500-companies`` and carries
  proper names and GICS sectors.
- **Russell 2000** comes from the iShares IWM ETF holdings file (IWM tracks the
  Russell 2000). It is an ETF-holdings proxy: this script keeps only equity
  lines and drops cash/derivative/placeholder rows. Names are populated; sector
  is filled from iShares' sector column when present, else "Unknown". If your
  environment can't reach ishares.com, keep the bundled snapshot or supply your
  own CSV via ``--russell-csv <path>``.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys

try:
    import requests
except ImportError:
    print("ERROR: requests required. Install with: pip install requests", file=sys.stderr)
    sys.exit(1)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_SCRIPT_DIR, "data")

_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9\-]{0,11}$")

_SP500_CSV_URL = (
    "https://raw.githubusercontent.com/datasets/"
    "s-and-p-500-companies/main/data/constituents.csv"
)
# iShares IWM (Russell 2000 ETF) holdings CSV. The numeric IDs are iShares'
# stable product identifiers for IWM; if iShares changes the layout, pass a
# locally downloaded CSV with --russell-csv instead.
_IWM_HOLDINGS_URL = (
    "https://www.ishares.com/us/products/239710/"
    "ishares-russell-2000-etf/1467271812596.ajax"
    "?fileType=csv&fileName=IWM_holdings&dataType=fund"
)


def _yahoo_symbol(sym: str) -> str:
    return sym.strip().upper().replace(".", "-")


def _write(index: str, rows: list[dict]) -> None:
    rows.sort(key=lambda x: x["symbol"])
    os.makedirs(_DATA_DIR, exist_ok=True)
    path = os.path.join(_DATA_DIR, f"{index}_constituents.json")
    with open(path, "w") as f:
        json.dump(rows, f, indent=1)
    print(f"  wrote {len(rows)} constituents -> {path}")


def refresh_sp500() -> None:
    print("Refreshing S&P 500 from GitHub datasets CSV...")
    resp = requests.get(_SP500_CSV_URL, timeout=30)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    seen, rows = set(), []
    for r in reader:
        sym = _yahoo_symbol(r.get("Symbol", ""))
        if not _TICKER_RE.match(sym) or sym in seen:
            continue
        seen.add(sym)
        rows.append(
            {
                "symbol": sym,
                "name": (r.get("Security") or sym).strip(),
                "sector": (r.get("GICS Sector") or "Unknown").strip(),
                "subSector": (r.get("GICS Sub-Industry") or "Unknown").strip(),
            }
        )
    _write("sp500", rows)


def refresh_russell2000(local_csv: str | None = None) -> None:
    if local_csv:
        print(f"Refreshing Russell 2000 from local CSV: {local_csv}")
        with open(local_csv) as f:
            text = f.read()
    else:
        print("Refreshing Russell 2000 from iShares IWM holdings...")
        resp = requests.get(
            _IWM_HOLDINGS_URL,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (vcp-screener refresh)"},
        )
        resp.raise_for_status()
        text = resp.text

    # iShares CSVs carry a preamble before the holdings header row that starts
    # with "Ticker". Find that header, then parse from there.
    lines = text.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if ln.lstrip('"').startswith("Ticker")),
        None,
    )
    if start is None:
        raise ValueError(
            "Could not find the holdings header ('Ticker,...') in the IWM CSV. "
            "The layout may have changed; download it manually and pass "
            "--russell-csv."
        )
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    seen, rows, skipped = set(), [], 0
    for r in reader:
        sym = _yahoo_symbol(r.get("Ticker", ""))
        asset_class = (r.get("Asset Class") or "").strip().lower()
        # Keep only equity holdings; drop cash, futures, and placeholder rows.
        if asset_class and asset_class != "equity":
            skipped += 1
            continue
        if not _TICKER_RE.match(sym) or sym in seen:
            skipped += 1
            continue
        seen.add(sym)
        rows.append(
            {
                "symbol": sym,
                "name": (r.get("Name") or sym).strip(),
                "sector": (r.get("Sector") or "Unknown").strip() or "Unknown",
                "subSector": "Unknown",
            }
        )
    if not rows:
        raise ValueError("No equity rows parsed from the IWM CSV — aborting.")
    print(f"  parsed {len(rows)} equities ({skipped} non-equity/invalid rows skipped)")
    _write("russell2000", rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="Refresh index constituent snapshots.")
    ap.add_argument(
        "--index",
        choices=["sp500", "russell2000", "both"],
        default="both",
        help="Which snapshot(s) to refresh (default: both).",
    )
    ap.add_argument(
        "--russell-csv",
        help="Path to a manually downloaded IWM holdings CSV (offline fallback).",
    )
    args = ap.parse_args()

    targets = ["sp500", "russell2000"] if args.index == "both" else [args.index]
    failures = 0
    for idx in targets:
        try:
            if idx == "sp500":
                refresh_sp500()
            else:
                refresh_russell2000(args.russell_csv)
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"ERROR refreshing {idx}: {e}", file=sys.stderr)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
