#!/usr/bin/env python3
"""Cache candidate SEC Form 4 documents listed by the coverage audit."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from sec_submissions import run_jobs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("candidates_csv")
    ap.add_argument("--output-dir", default="backtests/sec_pit_audit/form4_raw_documents")
    ap.add_argument("--user-agent", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--delay", type=float, default=.5)
    args = ap.parse_args()
    rows = list(csv.DictReader(Path(args.candidates_csv).open()))
    out = Path(args.output_dir)
    jobs = [(f"{row['symbol']}:{row['accession']}",
             row["url"].replace("/" + row["primary_document"],
                                "/" + row["primary_document"].split("/")[-1]),
             out / f"{row['symbol']}__{row['accession']}.xml") for row in rows]
    counts = run_jobs(jobs, args.user_agent, args.workers, args.delay)
    print(json.dumps({"candidate_documents": len(jobs), **counts}, indent=2))


if __name__ == "__main__":
    main()
