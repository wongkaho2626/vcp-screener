"""Pure-logic tests for the frozen pivot-retest validation runner."""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from pivot_retest_experiment import filter_detections, trade_stats


def test_filter_detections_applies_segment_and_point_in_time_membership():
    detections = {
        "AAA": [
            {"as_of_date": "2021-06-01"},
            {"as_of_date": "2023-06-01"},
        ],
        "BBB": [{"as_of_date": "2023-06-01"}],
    }
    membership = {
        "AAA": [("2020-01-01", "9999-12-31")],
        "BBB": [("2018-01-01", "2022-12-31")],
    }

    kept, dropped = filter_detections(
        detections, membership, "2022-01-01", "2026-06-30",
    )

    assert kept == {"AAA": [{"as_of_date": "2023-06-01"}]}
    assert dropped == 1


def test_trade_stats_uses_net_trade_returns():
    stats = trade_stats([
        {"net_return_pct": 10}, {"net_return_pct": -5},
        {"net_return_pct": -5}, {"net_return_pct": 20},
    ])

    assert stats["trades"] == 4
    assert stats["profit_factor"] == pytest.approx(3.0)
    assert stats["expectancy_pct"] == pytest.approx(5.0)
    assert stats["win_rate"] == pytest.approx(.5)
    assert stats["payoff_ratio"] == pytest.approx(3.0)
