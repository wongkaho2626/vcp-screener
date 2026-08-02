"""Focused deterministic tests for the daily MA60 runner."""

import csv
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from run_daily_ma60_strategy import (  # noqa: E402
    COLUMNS,
    QQQ_MARKER,
    _parse_qqq_bridge,
    build_latest_candidates,
    latest_completed_spy_date,
    merge_price_tail,
    select_next_orders,
)


def _bar(day: str, close: float) -> dict:
    return {
        "date": day, "open": close, "high": close, "low": close,
        "close": close, "adjClose": close, "volume": 1_000_000,
    }


def test_latest_session_is_excluded_before_new_york_close():
    dates = ["2026-07-30", "2026-07-31"]
    before = datetime(2026, 7, 31, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    after = datetime(2026, 7, 31, 16, 20, tzinfo=ZoneInfo("America/New_York"))
    assert latest_completed_spy_date(dates, before) == "2026-07-30"
    assert latest_completed_spy_date(dates, after) == "2026-07-31"


def test_qqq_bridge_parser_uses_marker_and_ignores_noisy_output():
    payload = {"risk_on_at_latest_open": True, "windows": []}
    output = "fetch noise\n" + QQQ_MARKER + json.dumps(payload) + "\n"
    assert _parse_qqq_bridge(output) == payload


def test_merge_replaces_recent_tail_atomically_and_writes_snapshot(tmp_path: Path):
    store = tmp_path / "prices.csv"
    with store.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        writer.writerow(["AAPL", "2026-07-29", 1, 1, 1, 1, 1, 1])
        writer.writerow(["AAPL", "2026-07-30", 2, 2, 2, 2, 2, 2])
        writer.writerow(["SPY", "2026-07-30", 3, 3, 3, 3, 3, 3])
    downloaded = {
        "AAPL": [["AAPL", "2026-07-30", 20, 20, 20, 20, 20, 20],
                 ["AAPL", "2026-07-31", 21, 21, 21, 21, 21, 21]],
        "SPY": [["SPY", "2026-07-31", 30, 30, 30, 30, 30, 30]],
    }
    result = merge_price_tail(
        store, downloaded, "2026-07-30", ["AAPL", "SPY"], tmp_path)
    with store.open(newline="") as handle:
        rows = list(csv.reader(handle))
    keys = [(row[0], row[1]) for row in rows[1:]]
    assert keys.count(("AAPL", "2026-07-30")) == 1
    assert ("AAPL", "2026-07-29") in keys
    assert result["latest_spy_date"] == "2026-07-31"
    assert (tmp_path / "latest_prices.csv").exists()
    assert (tmp_path / "snapshots" / "2026-07-31.csv").exists()


def test_latest_candidates_require_false_to_true_and_no_future_bar():
    # Use real consecutive ISO dates beyond January for enough observations.
    from datetime import date, timedelta
    dates = [(date(2025, 10, 1) + timedelta(days=index)).isoformat()
             for index in range(100)]
    spy = [_bar(day, 100) for day in dates]
    # Final jump makes the stock condition newly true on the last completed bar.
    stock_values = [100 - 0.01 * index for index in range(99)] + [120]
    stock = [_bar(day, value) for day, value in zip(dates, stock_values)]
    candidates, qualifying, missing = build_latest_candidates(
        {"SPY": spy, "AAA": stock}, ["AAA"], dates[-1])
    assert qualifying == 1
    assert missing == []
    assert [row["symbol"] for row in candidates] == ["AAA"]
    assert candidates[0]["signal_date"] == dates[-1]


def test_next_orders_obey_qqq_state_capacity_and_sector_cap():
    candidates = [
        {"symbol": "A", "divergence_pct": 3},
        {"symbol": "B", "divergence_pct": 2},
    ]
    positions = [
        {"symbol": "X"}, {"symbol": "Y"}, {"symbol": "Z"},
    ]
    sectors = {"A": "Tech", "B": "Finance", "X": "Tech", "Y": "Tech", "Z": "Tech"}
    out, _ = select_next_orders(
        candidates, positions, sectors,
        {"risk_on_after_next_open": True, "latest_date": "2026-07-31"},
        "2026-07-31")
    assert [row["symbol"] for row in out] == ["B"]
    blocked, reason = select_next_orders(
        candidates, [], sectors,
        {"risk_on_after_next_open": False, "latest_date": "2026-07-31"},
        "2026-07-31")
    assert blocked == []
    assert "OUT" in reason


def test_next_orders_are_blocked_when_qqq_breadth_is_stale():
    blocked, reason = select_next_orders(
        [{"symbol": "A", "divergence_pct": 3}], [], {"A": "Tech"},
        {"risk_on_after_next_open": True, "latest_date": "2026-07-30"},
        "2026-07-31")
    assert blocked == []
    assert "stale" in reason
