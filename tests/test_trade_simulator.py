"""Unit tests for trade_simulator pure functions (entry cap, stop floor,
exit walk) and membership interval lookups. Synthetic data only."""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from membership import is_member, load_membership, union_members
from trade_simulator import compute_trade_stats, plan_trade, simulate_exit


def make_breakout_detection(entry=105.0, pivot=103.0, stop=96.5):
    return {
        "as_of_date": "2021-05-03",
        "composite_score": 72.0,
        "forward_outcome": {
            "outcome_type": "breakout",
            "exit_date": "2021-05-10",
            "exit_price": entry,
            "pivot_price": pivot,
            "stop_price": stop,
        },
    }


def make_bars(closes, start_day=1):
    """Oldest-first bars with sequential dates."""
    return [
        {"date": f"2021-05-{start_day + i:02d}", "close": c} for i, c in enumerate(closes)
    ]


class TestPlanTrade:
    def test_breakout_within_extension_becomes_trade(self):
        plan = plan_trade(make_breakout_detection(entry=105.0, pivot=103.0), 5.0, 8.0)
        assert plan["action"] == "trade"
        assert plan["entry_price"] == 105.0

    def test_extended_entry_skipped(self):
        # 110 vs pivot 100 = +10% extension > 5% cap
        plan = plan_trade(make_breakout_detection(entry=110.0, pivot=100.0), 5.0, 8.0)
        assert plan == {"action": "skip", "reason": "extended"}

    def test_stop_floored_at_max_risk(self):
        # Pattern stop 80 is 20% below entry 100; floor must lift it to 92.
        plan = plan_trade(make_breakout_detection(entry=100.0, pivot=99.0, stop=80.0), 5.0, 8.0)
        assert plan["stop_price"] == pytest.approx(92.0)

    def test_pattern_stop_kept_when_tighter_than_floor(self):
        plan = plan_trade(make_breakout_detection(entry=100.0, pivot=99.0, stop=95.0), 5.0, 8.0)
        assert plan["stop_price"] == pytest.approx(95.0)

    def test_stop_hit_detection_is_no_fill(self):
        det = make_breakout_detection()
        det["forward_outcome"]["outcome_type"] = "stop_hit"
        assert plan_trade(det, 5.0, 8.0) == {"action": "skip", "reason": "no_fill"}

    def test_missing_pivot_skipped(self):
        det = make_breakout_detection()
        det["forward_outcome"]["pivot_price"] = None
        assert plan_trade(det, 5.0, 8.0) == {"action": "skip", "reason": "missing_fields"}


class TestSimulateExit:
    def test_stop_exit_on_first_close_below_stop(self):
        bars = make_bars([100, 101, 91, 95, 96])
        result = simulate_exit(bars, 0, stop_price=92.0, max_hold_bars=60)
        assert result["exit_reason"] == "stop"
        assert result["exit_price"] == 91
        assert result["hold_bars"] == 2

    def test_timeout_exit_after_max_hold(self):
        bars = make_bars([100] + [105] * 10)
        result = simulate_exit(bars, 0, stop_price=92.0, max_hold_bars=5)
        assert result["exit_reason"] == "timeout"
        assert result["hold_bars"] == 5

    def test_open_exit_when_history_ends(self):
        bars = make_bars([100, 104, 106])
        result = simulate_exit(bars, 0, stop_price=92.0, max_hold_bars=60)
        assert result["exit_reason"] == "open"
        assert result["exit_price"] == 106

    def test_no_forward_bars_returns_none(self):
        bars = make_bars([100])
        assert simulate_exit(bars, 0, stop_price=92.0, max_hold_bars=60) is None


class TestComputeTradeStats:
    def test_excess_is_primary(self):
        trades = [
            {"ret_pct": 10.0, "excess_vs_spy_pct": 6.0, "hold_bars": 10, "exit_reason": "timeout"},
            {"ret_pct": -4.0, "excess_vs_spy_pct": -6.0, "hold_bars": 5, "exit_reason": "stop"},
        ]
        stats = compute_trade_stats(trades, {"no_fill": 1})
        assert stats["n_trades"] == 2
        assert stats["primary_mean_excess_vs_spy_pct"] == 0.0
        assert stats["win_rate_pct"] == 50.0
        assert stats["exit_reasons"]["stop"] == 1

    def test_empty_trades(self):
        stats = compute_trade_stats([], {})
        assert stats["n_trades"] == 0
        assert stats["primary_mean_excess_vs_spy_pct"] is None


class TestMembership:
    @pytest.fixture
    def csv_path(self, tmp_path):
        p = tmp_path / "membership.csv"
        p.write_text(
            "ticker,start_date,end_date\n"
            "FAKE,2015-01-02,2019-06-30\n"
            "FAKE,2022-01-03,\n"
            "GONE.X,2010-05-01,2016-09-30\n"
        )
        return str(p)

    def test_member_inside_interval(self, csv_path):
        intervals = load_membership(csv_path)
        assert is_member(intervals, "FAKE", "2018-01-01")
        assert not is_member(intervals, "FAKE", "2020-06-01")
        assert is_member(intervals, "FAKE", "2024-01-01")  # open-ended rejoin

    def test_symbol_normalized_to_yahoo_form(self, csv_path):
        intervals = load_membership(csv_path)
        assert is_member(intervals, "GONE-X", "2015-01-01")

    def test_union_members_overlap(self, csv_path):
        intervals = load_membership(csv_path)
        assert union_members(intervals, "2016-07-08", "2026-07-08") == ["FAKE", "GONE-X"]
        assert union_members(intervals, "2020-01-01", "2021-01-01") == []

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_membership("/nonexistent/membership.csv")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
