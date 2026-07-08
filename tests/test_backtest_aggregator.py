"""Unit tests for backtest_aggregator — pure aggregation over synthetic
detection dicts shaped like historical_scanner.scan_history output."""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from backtest_aggregator import (
    build_backtest_summary,
    group_by_rating_band,
    group_by_year,
    summarize_outcomes,
)


def make_detection(
    outcome="breakout",
    days=10,
    max_gain=12.0,
    max_loss=-3.0,
    as_of="2021-05-03",
    score=85.0,
):
    return {
        "as_of_date": as_of,
        "composite_score": score,
        "forward_outcome": {
            "outcome_type": outcome,
            "days_to_outcome": days,
            "max_gain_pct": max_gain,
            "max_loss_pct": max_loss,
        },
    }


class TestSummarizeOutcomes:
    def test_empty_list_yields_none_rates(self):
        stats = summarize_outcomes([])
        assert stats["total_detections"] == 0
        assert stats["resolved"] == 0
        assert stats["breakout_rate_pct"] is None

    def test_counts_and_rates(self):
        dets = [
            make_detection("breakout"),
            make_detection("breakout"),
            make_detection("stop_hit"),
            make_detection("timeout", days=None),
        ]
        stats = summarize_outcomes(dets)
        assert stats["total_detections"] == 4
        assert stats["resolved"] == 4
        assert stats["counts"]["breakout"] == 2
        assert stats["breakout_rate_pct"] == 50.0
        assert stats["stop_hit_rate_pct"] == 25.0
        assert stats["timeout_rate_pct"] == 25.0

    def test_insufficient_data_excluded_from_resolved(self):
        dets = [make_detection("breakout"), make_detection("insufficient_data", days=None)]
        stats = summarize_outcomes(dets)
        assert stats["resolved"] == 1
        assert stats["breakout_rate_pct"] == 100.0
        assert stats["counts"]["insufficient_data"] == 1

    def test_trajectory_averages(self):
        dets = [
            make_detection("breakout", days=5, max_gain=10.0),
            make_detection("breakout", days=15, max_gain=20.0),
            make_detection("stop_hit", days=8, max_loss=-10.0),
        ]
        stats = summarize_outcomes(dets)
        assert stats["avg_days_to_breakout"] == 10.0
        assert stats["avg_days_to_stop"] == 8.0
        assert stats["avg_max_gain_on_breakout_pct"] == 15.0
        assert stats["avg_max_loss_on_stop_pct"] == -10.0

    def test_missing_forward_outcome_tolerated(self):
        stats = summarize_outcomes([{"as_of_date": "2020-01-02"}])
        assert stats["total_detections"] == 1
        assert stats["resolved"] == 0

    def test_input_not_mutated(self):
        det = make_detection()
        snapshot = {**det, "forward_outcome": {**det["forward_outcome"]}}
        summarize_outcomes([det])
        assert det == snapshot


class TestGrouping:
    def test_group_by_year(self):
        dets = [
            make_detection(as_of="2019-03-01"),
            make_detection(as_of="2019-11-20"),
            make_detection(as_of="2024-06-15"),
        ]
        groups = group_by_year(dets)
        assert sorted(groups) == ["2019", "2024"]
        assert len(groups["2019"]) == 2

    def test_group_by_year_missing_date(self):
        groups = group_by_year([{"composite_score": 70.0}])
        assert list(groups) == ["unknown"]

    def test_group_by_rating_band(self):
        dets = [
            make_detection(score=95.0),
            make_detection(score=85.0),
            make_detection(score=72.0),
            make_detection(score=40.0),
        ]
        groups = group_by_rating_band(dets)
        assert len(groups["Textbook VCP (90+)"]) == 1
        assert len(groups["Strong VCP (80-89)"]) == 1
        assert len(groups["Good VCP (70-79)"]) == 1
        assert len(groups["Weak (<60)"]) == 1


class TestBuildBacktestSummary:
    def test_full_summary_shape(self):
        per_ticker = {
            "AAPL": [make_detection("breakout", as_of="2018-02-05", score=91.0)],
            "MSFT": [make_detection("stop_hit", as_of="2020-09-10", score=65.0)],
            "XOM": [],
        }
        summary = build_backtest_summary(per_ticker)
        assert summary["tickers_scanned"] == 3
        assert summary["tickers_with_detections"] == 2
        assert summary["overall"]["total_detections"] == 2
        assert set(summary["by_year"]) == {"2018", "2020"}
        assert "Textbook VCP (90+)" in summary["by_rating_band"]
        assert summary["by_ticker"]["XOM"]["total_detections"] == 0

    def test_empty_universe(self):
        summary = build_backtest_summary({})
        assert summary["tickers_scanned"] == 0
        assert summary["overall"]["total_detections"] == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
