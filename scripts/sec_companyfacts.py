#!/usr/bin/env python3
"""Fetch and extract strictly as-filed SEC Company Facts growth observations."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

EPS_TAGS = ("EarningsPerShareDiluted",)
REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues", "SalesRevenueNet",
)
GROSS_PROFIT_TAGS = ("GrossProfit",)
OPERATING_INCOME_TAGS = ("OperatingIncomeLoss",)
CASH_FLOW_TAGS = ("NetCashProvidedByUsedInOperatingActivities",)
NET_INCOME_TAGS = ("NetIncomeLoss", "ProfitLoss")


def ticker_cik_map(payload: dict) -> dict[str, str]:
    return {
        row["ticker"].upper().replace(".", "-"): str(row["cik_str"]).zfill(10)
        for row in payload.values()
    }


def _duration(row: dict) -> int | None:
    try:
        return (date.fromisoformat(row["end"]) - date.fromisoformat(row["start"])).days
    except (KeyError, TypeError, ValueError):
        return None


def _units_for_tag(companyfacts: dict, tag: str) -> list[dict]:
    fact = (companyfacts.get("facts") or {}).get("us-gaap", {}).get(tag) or {}
    units = fact.get("units") or {}
    rows = []
    for values in units.values():
        rows.extend(values)
    return rows


def comparable_values(
    rows: list[dict], accession: str, form: str,
) -> tuple[float, float] | None:
    """Current/prior comparable values presented within one accession."""
    have = [row for row in rows if row.get("accn") == accession]
    if form == "10-Q":
        have = [row for row in have if (_duration(row) or 0) in range(70, 111)]
    elif form == "10-K":
        have = [row for row in have if (_duration(row) or 0) in range(330, 401)]
    else:
        return None
    if len(have) < 2:
        return None
    current = max(have, key=lambda row: row.get("end") or "")
    try:
        current_end = date.fromisoformat(current["end"])
        current_value = float(current["val"])
    except (KeyError, TypeError, ValueError):
        return None
    candidates = []
    for row in have:
        if row is current:
            continue
        try:
            gap = (current_end - date.fromisoformat(row["end"])).days
            value = float(row["val"])
        except (KeyError, TypeError, ValueError):
            continue
        if 330 <= gap <= 400:
            candidates.append((abs(gap - 365), value))
    if not candidates:
        return None
    prior = min(candidates)[1]
    return current_value, prior


def comparable_growth(rows: list[dict], accession: str, form: str) -> float | None:
    """YoY growth using current/prior comparable facts from one accession."""
    values = comparable_values(rows, accession, form)
    if values is None:
        return None
    current_value, prior = values
    if prior <= 0 or current_value <= 0:
        return None
    return current_value / prior - 1


def as_filed_growth_events(companyfacts: dict) -> list[dict]:
    """Return filings with same-accession EPS and revenue YoY comparisons."""
    eps_rows = []
    for tag in EPS_TAGS:
        eps_rows.extend(_units_for_tag(companyfacts, tag))
    eps_by_accession: dict[str, list[dict]] = {}
    filings = set()
    for row in eps_rows:
        form, filed, accession = row.get("form"), row.get("filed"), row.get("accn")
        if form in ("10-Q", "10-K") and filed and accession:
            filings.add((filed, accession, form))
            eps_by_accession.setdefault(accession, []).append(row)
    revenue_by_tag_accession: dict[str, dict[str, list[dict]]] = {}
    for tag in REVENUE_TAGS:
        by_accession: dict[str, list[dict]] = {}
        for row in _units_for_tag(companyfacts, tag):
            accession = row.get("accn")
            if accession:
                by_accession.setdefault(accession, []).append(row)
        revenue_by_tag_accession[tag] = by_accession
    margin_by_tag_accession: dict[str, dict[str, list[dict]]] = {}
    for tag in (*GROSS_PROFIT_TAGS, *OPERATING_INCOME_TAGS,
                *CASH_FLOW_TAGS, *NET_INCOME_TAGS):
        by_accession = {}
        for row in _units_for_tag(companyfacts, tag):
            accession = row.get("accn")
            if accession:
                by_accession.setdefault(accession, []).append(row)
        margin_by_tag_accession[tag] = by_accession
    events = []
    for filed, accession, form in sorted(filings):
        eps_growth = comparable_growth(eps_by_accession[accession], accession, form)
        if eps_growth is None:
            continue
        revenue_growth = revenue_tag = revenue_values = None
        for tag in REVENUE_TAGS:
            values = comparable_values(
                revenue_by_tag_accession[tag].get(accession, []), accession, form
            )
            if values is not None and values[0] > 0 and values[1] > 0:
                revenue_values = values
                revenue_growth, revenue_tag = values[0] / values[1] - 1, tag
                break
        if revenue_growth is None:
            continue
        event = {
            "filed": filed, "accession": accession, "form": form,
            "eps_growth": eps_growth, "revenue_growth": revenue_growth,
            "revenue_tag": revenue_tag,
        }
        for prefix, tags in (
            ("gross", GROSS_PROFIT_TAGS),
            ("operating", OPERATING_INCOME_TAGS),
        ):
            for tag in tags:
                values = comparable_values(
                    margin_by_tag_accession[tag].get(accession, []), accession, form,
                )
                if values is None:
                    continue
                current_margin = values[0] / revenue_values[0]
                prior_margin = values[1] / revenue_values[1]
                event[f"{prefix}_margin"] = current_margin
                event[f"{prefix}_margin_delta"] = current_margin - prior_margin
                event[f"{prefix}_margin_tag"] = tag
                break
        if form == "10-K":
            cash_values = income_values = None
            for tag in CASH_FLOW_TAGS:
                cash_values = comparable_values(
                    margin_by_tag_accession[tag].get(accession, []), accession, form,
                )
                if cash_values is not None:
                    event["cash_flow_tag"] = tag
                    break
            for tag in NET_INCOME_TAGS:
                income_values = comparable_values(
                    margin_by_tag_accession[tag].get(accession, []), accession, form,
                )
                if income_values is not None:
                    event["net_income_tag"] = tag
                    break
            if cash_values is not None and income_values is not None and income_values[0] > 0:
                event["cash_conversion"] = cash_values[0] / income_values[0]
                event["operating_cash_flow"] = cash_values[0]
                event["net_income"] = income_values[0]
        events.append(event)
    return events


def latest_event_before(events: list[dict], signal_date: str) -> dict | None:
    """Strict inequality makes a filing usable no earlier than its next day."""
    eligible = [event for event in events if event["filed"] < signal_date]
    return max(eligible, key=lambda event: event["filed"]) if eligible else None


def fetch_companyfacts(cik: str, output: Path, user_agent: str) -> str:
    if output.exists():
        return "cached"
    request = urllib.request.Request(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
        headers={"User-Agent": user_agent},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(output)
    return "fetched"


def _fetch_one(symbol: str, cik: str, output: Path, user_agent: str,
               delay: float) -> tuple[str, str, str | None]:
    try:
        status = fetch_companyfacts(cik, output, user_agent)
        if status == "fetched":
            time.sleep(max(delay, 0))
        return symbol, status, None
    except Exception as exc:  # noqa: BLE001
        return symbol, "failed", str(exc)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tickers-json", required=True)
    ap.add_argument("--symbols-file", required=True)
    ap.add_argument("--output-dir", default="backtests/sec_pit_audit/companyfacts")
    ap.add_argument("--user-agent", required=True)
    ap.add_argument("--delay", type=float, default=.12)
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args()
    mapping = ticker_cik_map(json.loads(Path(args.tickers_json).read_text()))
    symbols = [line.strip().upper() for line in Path(args.symbols_file).read_text().splitlines()
               if line.strip() and not line.startswith("#")]
    out = Path(args.output_dir)
    fetched = cached = missing = failed = 0
    jobs = []
    for symbol in symbols:
        cik = mapping.get(symbol.replace(".", "-"))
        if not cik:
            missing += 1
            continue
        jobs.append((symbol, cik, out / f"{symbol}.json"))
    with ThreadPoolExecutor(max_workers=max(args.workers, 1)) as executor:
        futures = [executor.submit(_fetch_one, symbol, cik, output,
                                   args.user_agent, args.delay)
                   for symbol, cik, output in jobs]
        for future in as_completed(futures):
            symbol, status, error = future.result()
            if status == "fetched":
                fetched += 1
            elif status == "cached":
                cached += 1
            else:
                failed += 1
                print(f"WARN {symbol}: {error}")
    print(json.dumps({"symbols": len(symbols), "fetched": fetched, "cached": cached,
                      "unmapped": missing, "failed": failed}, indent=2))


if __name__ == "__main__":
    main()
