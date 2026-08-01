from __future__ import annotations

import csv
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from public_oos_data_audit import audit_archive, membership_spans, wiki_coverage


def test_public_archive_coverage_uses_membership_days(tmp_path):
    membership = tmp_path / "membership.csv"
    with membership.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["ticker", "start_date", "end_date"])
        writer.writerow(["AAPL", "2000-01-01", ""])
        writer.writerow(["OLD", "2000-01-02", "2000-01-03"])
    archive_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("Data/Stocks/aapl.us.txt",
                         "Date,Open,High,Low,Close,Volume,OpenInt\n"
                         "2000-01-01,1,1,1,1,1,0\n"
                         "2000-01-02,1,1,1,1,1,0\n"
                         "2000-01-03,1,1,1,1,1,0\n")
        archive.writestr("Data/Stocks/old.us.txt",
                         "Date,Open,High,Low,Close,Volume,OpenInt\n"
                         "2000-01-02,1,1,1,1,1,0\n")
    spans = membership_spans(membership, "2000-01-01", "2000-01-03")
    report = audit_archive(archive_path, spans, "2000-01-01", "2000-01-03")
    assert report["member_days"] == 5
    assert report["covered_member_days"] == 4
    assert report["coverage_pct"] == 80


def test_wiki_symbol_coverage_normalizes_share_classes(tmp_path):
    tickers = tmp_path / "wiki.csv"
    tickers.write_text("ticker\nAAPL\nBRK-B\n")
    spans = {"AAPL": [("2000-01-01", "2000-01-02")],
             "BRK-B": [("2000-01-01", "2000-01-02")],
             "OLD": [("2000-01-01", "2000-01-02")]}
    assert wiki_coverage(tickers, spans)["matched_symbols"] == 2
