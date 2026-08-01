#!/usr/bin/env python3
"""Cache SEC submissions indexes, including paginated historical files."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from sec_companyfacts import ticker_cik_map


def fetch(url: str, output: Path, user_agent: str) -> str:
    if output.exists():
        return "cached"
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(output)
    return "fetched"


def fetch_one(name: str, url: str, output: Path, user_agent: str,
              delay: float) -> tuple[str, str, str | None]:
    try:
        status = fetch(url, output, user_agent)
        if status == "fetched":
            time.sleep(max(delay, 0))
        return name, status, None
    except Exception as exc:  # noqa: BLE001
        return name, "failed", str(exc)


def run_jobs(jobs: list[tuple[str, str, Path]], user_agent: str,
             workers: int, delay: float) -> dict:
    counts = {"fetched": 0, "cached": 0, "failed": 0}
    with ThreadPoolExecutor(max_workers=max(workers, 1)) as executor:
        futures = [executor.submit(fetch_one, name, url, output, user_agent, delay)
                   for name, url, output in jobs]
        for future in as_completed(futures):
            name, status, error = future.result()
            counts[status] += 1
            if error:
                print(f"WARN {name}: {error}")
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tickers-json", required=True)
    ap.add_argument("--symbols-file", required=True)
    ap.add_argument("--output-dir", default="backtests/sec_pit_audit/submissions")
    ap.add_argument("--user-agent", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--delay", type=float, default=.5)
    args = ap.parse_args()
    mapping = ticker_cik_map(json.loads(Path(args.tickers_json).read_text()))
    symbols = [line.strip().upper() for line in Path(args.symbols_file).read_text().splitlines()
               if line.strip() and not line.startswith("#")]
    out = Path(args.output_dir)
    mains = []
    unmapped = 0
    for symbol in symbols:
        cik = mapping.get(symbol.replace(".", "-"))
        if cik is None:
            unmapped += 1
            continue
        mains.append((symbol, f"https://data.sec.gov/submissions/CIK{cik}.json",
                      out / f"{symbol}.json"))
    main_counts = run_jobs(mains, args.user_agent, args.workers, args.delay)
    history_jobs = []
    invalid_main = 0
    for symbol, _, path in mains:
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            invalid_main += 1
            continue
        for row in (payload.get("filings") or {}).get("files") or []:
            name = row.get("name")
            if not name:
                continue
            history_jobs.append((f"{symbol}:{name}",
                                 f"https://data.sec.gov/submissions/{name}",
                                 out / "history" / f"{symbol}__{name}"))
    history_counts = run_jobs(history_jobs, args.user_agent, args.workers, args.delay)
    print(json.dumps({"symbols": len(symbols), "unmapped": unmapped,
                      "invalid_main": invalid_main, "main": main_counts,
                      "history_files": len(history_jobs), "history": history_counts}, indent=2))


if __name__ == "__main__":
    main()
