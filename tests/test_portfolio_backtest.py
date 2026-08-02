"""Focused tests for conservative portfolio execution and constraints."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from portfolio_backtest import (
    Config,
    _adv_dollars,
    _candidate_signals,
    _find_causal_breakout,
    _plan_consecutive_breakout_closes,
    _plan_first_down_close,
    _plan_pivot_reclaim,
    _plan_post_breakout_inside_day,
    _plan_stopout_pivot_reentry,
    _plan_closing_low_pullback,
    _plan_closing_low_lifecycle,
    _plan_closing_low_reversal,
    _plan_controlled_pullback_recovery,
    _plan_pivot_open_limit,
    _plan_contraction_limit,
    _plan_pivot_retest,
    _plan_rebreak_after_pullback,
    run_portfolio,
)


class PortfolioBacktestTests(unittest.TestCase):
    def test_causal_breakout_stops_at_first_close_above_frozen_pivot(self):
        bars = [
            {"date": f"d{i:02}", "open": c, "high": c + 1, "low": c - 1,
             "close": c, "volume": 1_000_000}
            for i, c in enumerate((95, 97, 99, 101, 105))
        ]
        self.assertEqual(_find_causal_breakout(bars, 0, 100, 90), 3)

    def test_causal_breakout_invalidates_on_prebreakout_close_below_stop(self):
        bars = [
            {"date": f"d{i:02}", "open": c, "high": c + 1, "low": c - 1,
             "close": c, "volume": 1_000_000}
            for i, c in enumerate((95, 89, 101))
        ]
        self.assertIsNone(_find_causal_breakout(bars, 0, 100, 90))

    def test_causal_breakout_rejects_detection_bar_already_below_stop(self):
        bars = [
            {"date": "d00", "close": 89},
            {"date": "d01", "close": 101},
        ]
        assert _find_causal_breakout(bars, 0, 100, 90) is None

    def test_two_close_breakout_signals_on_second_consecutive_close(self):
        bars = [
            {"date": f"d{i:02}", "open": c, "high": c + 1, "low": c - 1,
             "close": c, "volume": 1_000_000}
            for i, c in enumerate((95, 99, 101, 102, 103))
        ]
        self.assertEqual(
            _plan_consecutive_breakout_closes(bars, 0, 100, 90), 3,
        )

    def test_two_close_breakout_rejects_failed_immediate_confirmation(self):
        bars = [
            {"date": f"d{i:02}", "open": c, "high": c + 1, "low": c - 1,
             "close": c, "volume": 1_000_000}
            for i, c in enumerate((95, 101, 99, 102, 103))
        ]
        self.assertIsNone(
            _plan_consecutive_breakout_closes(bars, 0, 100, 90),
        )

    def test_consecutive_breakout_requires_positive_close_count(self):
        with self.assertRaises(ValueError):
            _plan_consecutive_breakout_closes([], 0, 100, 90, required_closes=0)

    def test_first_down_close_uses_first_post_breakout_pause(self):
        bars = [
            {"date": f"d{i:02}", "close": c}
            for i, c in enumerate((101, 103, 105, 104, 106))
        ]
        assert _plan_first_down_close(bars, 0, 90) == 3

    def test_first_down_close_invalidates_before_later_pause(self):
        bars = [
            {"date": f"d{i:02}", "close": c}
            for i, c in enumerate((101, 103, 89, 88))
        ]
        assert _plan_first_down_close(bars, 0, 90) is None

    def test_first_down_close_pivot_hold_rejects_first_deep_pause(self):
        bars = [
            {"date": f"d{i:02}", "close": c}
            for i, c in enumerate((101, 103, 99, 102, 101))
        ]
        assert _plan_first_down_close(bars, 0, 90, pivot=100) is None

    def test_first_down_close_pivot_hold_accepts_shallow_pause(self):
        bars = [
            {"date": f"d{i:02}", "close": c}
            for i, c in enumerate((101, 104, 102, 105))
        ]
        assert _plan_first_down_close(bars, 0, 90, pivot=100) == 2

    def test_pivot_reclaim_waits_for_recovery_close(self):
        bars = [
            {"date": f"d{i:02}", "close": c}
            for i, c in enumerate((101, 103, 99, 98, 102, 104))
        ]
        assert _plan_pivot_reclaim(bars, 0, 100, 90) == 4

    def test_pivot_reclaim_rejects_stop_break_before_recovery(self):
        bars = [
            {"date": f"d{i:02}", "close": c}
            for i, c in enumerate((101, 99, 89, 102))
        ]
        assert _plan_pivot_reclaim(bars, 0, 100, 90) is None

    def test_pivot_reclaim_does_not_retry_after_expired_reclaim_window(self):
        bars = [
            {"date": f"d{i:02}", "close": c}
            for i, c in enumerate((101, 99, 98, 97, 102))
        ]
        assert _plan_pivot_reclaim(
            bars, 0, 100, 90, reclaim_window=2,
        ) is None

    def test_inside_day_signals_only_when_close_holds_pivot(self):
        bars = [
            {"date": "d00", "high": 105, "low": 99, "close": 103},
            {"date": "d01", "high": 104, "low": 100, "close": 102},
        ]
        assert _plan_post_breakout_inside_day(bars, 0, 100, 90) == 1
        assert _plan_post_breakout_inside_day(
            [bars[0], {**bars[1], "close": 99}], 0, 100, 90,
        ) is None

    def test_inside_day_is_strict_and_respects_wait_window(self):
        bars = [
            {"date": "d00", "high": 105, "low": 99, "close": 103},
            {"date": "d01", "high": 105, "low": 100, "close": 102},
            {"date": "d02", "high": 104, "low": 101, "close": 103},
        ]
        assert _plan_post_breakout_inside_day(
            bars, 0, 100, 90, window=1,
        ) is None

    def test_stopout_reentry_can_signal_on_stopout_close_for_next_open(self):
        bars = [
            {"date": "d00", "close": 99},
            {"date": "d01", "close": 101},
            {"date": "d02", "close": 102},
        ]
        assert _plan_stopout_pivot_reentry(bars, 1, 100) == 1

    def test_stopout_reentry_requires_a_following_fill_session(self):
        bars = [{"date": "d00", "close": 101}]
        assert _plan_stopout_pivot_reentry(bars, 0, 100) is None

    def test_closing_low_pullback_signals_on_first_new_five_day_low(self):
        bars = [
            {"date": f"d{i:02}", "close": close}
            for i, close in enumerate((100, 101, 102, 103, 104, 105, 99, 98))
        ]
        assert _plan_closing_low_pullback(
            bars, 5, 90, lookback=5, window=60,
        ) == 6

    def test_closing_low_pullback_invalidates_before_later_signal(self):
        bars = [
            {"date": f"d{i:02}", "close": close}
            for i, close in enumerate((100, 101, 102, 103, 104, 105, 89, 88))
        ]
        assert _plan_closing_low_pullback(bars, 5, 90) is None

    def test_closing_low_lifecycle_emits_spaced_attempts_until_stop_break(self):
        history = [
            {"date": f"d{i:02}", "close": close}
            for i, close in enumerate((
                100, 101, 102, 103, 104, 105, 99, 100, 101, 102,
                98, 99, 100, 101, 102, 97, 96, 89, 95,
            ))
        ]
        assert _plan_closing_low_lifecycle(
            history, 5, 90, lookback=5, cooldown=5, max_attempts=3,
        ) == [6, 15]

    def test_closing_low_lifecycle_caps_attempt_count(self):
        history = [
            {"date": f"d{i:02}", "close": close}
            for i, close in enumerate((
                100, 101, 102, 103, 104, 105, 99, 100, 101, 102,
                98, 99, 100, 101, 102, 97, 98, 99, 100, 101, 96,
            ))
        ]
        assert _plan_closing_low_lifecycle(
            history, 5, 90, lookback=5, cooldown=5, max_attempts=2,
        ) == [6, 15]

    def test_closing_low_reversal_waits_for_close_above_low_bar_high(self):
        bars = [
            {"date": f"d{i:02}", "high": high, "close": close}
            for i, (high, close) in enumerate((
                (101, 100), (102, 101), (103, 102), (104, 103),
                (105, 104), (106, 105), (101, 99), (101, 100),
                (103, 102), (104, 103),
            ))
        ]
        assert _plan_closing_low_reversal(bars, 5, 90) == 8

    def test_closing_low_reversal_respects_confirmation_window(self):
        bars = [
            {"date": f"d{i:02}", "high": close + 1, "close": close}
            for i, close in enumerate((100, 101, 102, 103, 104, 105, 99, 100, 102))
        ]
        assert _plan_closing_low_reversal(
            bars, 5, 90, confirm_window=1,
        ) is None

    def test_controlled_pullback_recovery_requires_depth_and_next_day_recovery(self):
        bars = [
            {"date": f"d{i:02}", "high": high, "close": close, "volume": volume}
            for i, (high, close, volume) in enumerate((
                (101, 100, 100), (102, 101, 100), (103, 102, 100),
                (104, 103, 100), (98, 97, 90), (103, 99, 110),
                (104, 100, 100),
            ))
        ]
        assert _plan_controlled_pullback_recovery(
            bars, 2, 100, 90, lookback=3, max_depth_pct=4,
            confirmation="prior_high", volume_expansion=True,
        ) == 5
        assert _plan_controlled_pullback_recovery(
            bars, 2, 100, 90, lookback=3, max_depth_pct=2,
            confirmation="prior_high", volume_expansion=True,
        ) is None

    def test_controlled_pullback_recovery_cancels_on_stop_close(self):
        bars = [
            {"date": f"d{i:02}", "high": close + 1, "close": close, "volume": 100}
            for i, close in enumerate((100, 101, 102, 89, 99, 101))
        ]
        assert _plan_controlled_pullback_recovery(
            bars, 2, 100, 90, lookback=3, max_depth_pct=8,
        ) is None

    def test_pivot_open_limit_fills_first_open_between_stop_and_pivot(self):
        bars = [
            {"date": "d00", "open": 103, "close": 102},
            {"date": "d01", "open": 101, "close": 101},
            {"date": "d02", "open": 99, "close": 100},
        ]
        assert _plan_pivot_open_limit(bars, 0, 100, 90) == 1

    def test_pivot_open_limit_cancels_on_open_at_or_below_stop(self):
        bars = [
            {"date": "d00", "open": 103, "close": 102},
            {"date": "d01", "open": 89, "close": 95},
            {"date": "d02", "open": 99, "close": 100},
        ]
        assert _plan_pivot_open_limit(bars, 0, 100, 90) is None

    def test_contraction_limit_fills_gap_down_at_open_or_intraday_at_limit(self):
        bars = [
            {"date": "d00", "open": 102, "low": 101, "close": 102},
            {"date": "d01", "open": 99, "low": 98, "close": 99},
            {"date": "d02", "open": 96, "low": 95, "close": 96},
        ]
        # Frozen level is 97.50; d01 does not touch and d02 gaps below it.
        assert _plan_contraction_limit(bars, 0, 100, 90) == (1, 96)
        intraday = [bars[0], {"date": "d01", "open": 99, "low": 97, "close": 98}]
        assert _plan_contraction_limit(intraday, 0, 100, 90) == (0, 97.5)

    def test_contraction_limit_cancels_gap_through_stop(self):
        bars = [
            {"date": "d00", "open": 102, "low": 101, "close": 102},
            {"date": "d01", "open": 89, "low": 88, "close": 95},
        ]
        assert _plan_contraction_limit(bars, 0, 100, 90) is None

    def test_portfolio_uses_frozen_raw_limit_fill_not_session_open(self):
        bars = [
            {"date": "d00", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1_000_000},
            {"date": "d01", "open": 100, "high": 101, "low": 97, "close": 100, "volume": 1_000_000},
            {"date": "d02", "open": 101, "high": 102, "low": 100, "close": 101, "volume": 1_000_000},
        ]
        signal = {
            "symbol": "AAA", "sector": "Tech", "signal_date": "d00",
            "fill_date": "d01", "fill_idx": 1, "edge_rank": 82.5,
            "pattern_stop": 90, "pivot": 100, "raw_entry_price": 97.5,
        }
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars}, Config(commission_bps=0, slippage_bps=0),
            )
        assert out["trades"][0]["entry_price"] == 97.5

    def test_pivot_retest_requires_touch_and_close_hold_after_breakout(self):
        bars = [
            {"date": f"d{i:02}", "open": c, "high": h, "low": lo,
             "close": c, "volume": 1_000_000}
            for i, (c, h, lo) in enumerate((
                (95, 96, 94), (101, 102, 100.5), (103, 104, 101),
                (99, 101, 98), (100.5, 102, 99.5), (110, 111, 109),
            ))
        ]
        # d03 touches but closes below pivot; d04 is the first valid hold.
        self.assertEqual(_plan_pivot_retest(bars, 1, 100, 90), 4)

    def test_pivot_retest_invalidates_on_close_below_pattern_stop(self):
        bars = [
            {"date": f"d{i:02}", "open": c, "high": c + 1, "low": c - 1,
             "close": c, "volume": 1_000_000}
            for i, c in enumerate((101, 103, 89, 101))
        ]
        self.assertIsNone(_plan_pivot_retest(bars, 0, 100, 90))

    def test_bullish_retest_rejects_weak_first_touch(self):
        bars = [
            {"date": "d00", "open": 101, "high": 102, "low": 100.5, "close": 101},
            {"date": "d01", "open": 101, "high": 102, "low": 99, "close": 100.5},
            {"date": "d02", "open": 100, "high": 103, "low": 99, "close": 102},
        ]
        assert _plan_pivot_retest(
            bars, 0, 100, 90, mode="bullish_retest",
        ) is None

    def test_strong_close_retest_uses_candle_location(self):
        weak = [
            {"date": "d00", "high": 103, "low": 101, "close": 102},
            {"date": "d01", "high": 110, "low": 99, "close": 101},
        ]
        strong = [weak[0], {**weak[1], "close": 108}]
        assert _plan_pivot_retest(
            weak, 0, 100, 90, mode="strong_close_clv60",
        ) is None
        assert _plan_pivot_retest(
            strong, 0, 100, 90, mode="strong_close_clv60",
        ) == 1

    def test_retest_high_confirmation_waits_for_later_confirming_close(self):
        bars = [
            {"date": "d00", "high": 103, "low": 101, "close": 102},
            {"date": "d01", "high": 105, "low": 99, "close": 101},
            {"date": "d02", "high": 105, "low": 100, "close": 104},
            {"date": "d03", "high": 107, "low": 103, "close": 106},
        ]
        assert _plan_pivot_retest(
            bars, 0, 100, 90, mode="retest_high_confirm3",
        ) == 3

    def test_pivot_retest_candidate_does_not_consult_forward_outcome(self):
        closes = [95, 96, 101, 103, 100.5, 102]
        lows = [94, 95, 100, 101, 99.5, 101]
        bars = [
            {"date": f"d{i:02}", "open": c, "high": c + 1, "low": lo,
             "close": c, "volume": 1_000_000}
            for i, (c, lo) in enumerate(zip(closes, lows))
        ]
        detection = {
            "as_of_date": "d01", "sector": "Tech",
            "vcp_pattern": {
                "pivot_price": 100,
                "contractions": [{"low_price": 90}],
            },
            "forward_outcome": {"outcome_type": "stop_hit", "exit_date": "d99"},
        }
        with patch("portfolio_backtest.compute_edge_rank", return_value={
            ("AAA", "d01"): {"edge_rank": 82.5},
        }):
            signals = _candidate_signals(
                {"AAA": [detection]}, {"AAA": bars}, Config(),
                entry_rule="pivot_retest",
            )
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["signal_date"], "d04")
        self.assertEqual(signals[0]["fill_date"], "d05")

    def test_detection_entry_fills_next_open_without_forward_outcome(self):
        bars = [
            {"date": f"d{i:02}", "open": 100 + i, "high": 101 + i,
             "low": 99 + i, "close": 100 + i, "volume": 1_000_000}
            for i in range(4)
        ]
        detection = {
            "as_of_date": "d01", "sector": "Tech",
            "vcp_pattern": {
                "pivot_price": 105,
                "contractions": [{"low_price": 95}],
            },
            "forward_outcome": {"outcome_type": "stop_hit", "exit_date": "d02"},
        }
        with patch("portfolio_backtest.compute_edge_rank", return_value={
            ("AAA", "d01"): {"edge_rank": 82.5},
        }):
            signals = _candidate_signals(
                {"AAA": [detection]}, {"AAA": bars}, Config(),
                entry_rule="detection_entry",
            )
        assert len(signals) == 1
        assert signals[0]["signal_date"] == "d01"
        assert signals[0]["fill_date"] == "d02"

    def test_detection_entry_rejects_pattern_invalid_on_asof_close(self):
        bars = [
            {"date": "d00", "open": 89, "high": 90, "low": 88,
             "close": 89, "volume": 1_000_000},
            {"date": "d01", "open": 101, "high": 102, "low": 100,
             "close": 101, "volume": 1_000_000},
        ]
        detection = {
            "as_of_date": "d00", "sector": "Tech",
            "vcp_pattern": {
                "pivot_price": 100,
                "contractions": [{"low_price": 90}],
            },
        }
        with patch("portfolio_backtest.compute_edge_rank", return_value={
            ("AAA", "d00"): {"edge_rank": 82.5},
        }):
            signals = _candidate_signals(
                {"AAA": [detection]}, {"AAA": bars}, Config(),
                entry_rule="detection_entry",
            )
        assert signals == []

    def test_two_close_breakout_fills_after_confirmation_without_outcome_label(self):
        bars = [
            {"date": f"d{i:02}", "open": c, "high": c + 1,
             "low": c - 1, "close": c, "volume": 1_000_000}
            for i, c in enumerate((95, 99, 101, 102, 103))
        ]
        detection = {
            "as_of_date": "d00", "sector": "Tech",
            "vcp_pattern": {
                "pivot_price": 100,
                "contractions": [{"low_price": 90}],
            },
            "forward_outcome": {"outcome_type": "stop_hit", "exit_date": "d02"},
        }
        with patch("portfolio_backtest.compute_edge_rank", return_value={
            ("AAA", "d00"): {"edge_rank": 82.5},
        }):
            signals = _candidate_signals(
                {"AAA": [detection]}, {"AAA": bars}, Config(),
                entry_rule="two_close_breakout",
            )
        assert len(signals) == 1
        assert signals[0]["signal_date"] == "d03"
        assert signals[0]["fill_date"] == "d04"

    def test_first_down_close_fills_next_open_without_outcome_label(self):
        bars = [
            {"date": f"d{i:02}", "open": c, "high": c + 1,
             "low": c - 1, "close": c, "volume": 1_000_000}
            for i, c in enumerate((95, 101, 103, 102, 104))
        ]
        detection = {
            "as_of_date": "d00", "sector": "Tech",
            "vcp_pattern": {
                "pivot_price": 100,
                "contractions": [{"low_price": 90}],
            },
            "forward_outcome": {"outcome_type": "stop_hit", "exit_date": "d03"},
        }
        with patch("portfolio_backtest.compute_edge_rank", return_value={
            ("AAA", "d00"): {"edge_rank": 82.5},
        }):
            signals = _candidate_signals(
                {"AAA": [detection]}, {"AAA": bars}, Config(),
                entry_rule="first_down_close",
            )
        assert len(signals) == 1
        assert signals[0]["signal_date"] == "d03"
        assert signals[0]["fill_date"] == "d04"

    def test_down_close_pivot_hold_is_causal_and_fills_next_open(self):
        bars = [
            {"date": f"d{i:02}", "open": c, "high": c + 1,
             "low": c - 1, "close": c, "volume": 1_000_000}
            for i, c in enumerate((95, 101, 104, 102, 105))
        ]
        detection = {
            "as_of_date": "d00", "sector": "Tech",
            "vcp_pattern": {
                "pivot_price": 100,
                "contractions": [{"low_price": 90}],
            },
            "forward_outcome": {"outcome_type": "stop_hit", "exit_date": "d03"},
        }
        with patch("portfolio_backtest.compute_edge_rank", return_value={
            ("AAA", "d00"): {"edge_rank": 82.5},
        }):
            signals = _candidate_signals(
                {"AAA": [detection]}, {"AAA": bars}, Config(),
                entry_rule="down_close_pivot_hold",
            )
        assert len(signals) == 1
        assert signals[0]["signal_date"] == "d03"
        assert signals[0]["fill_date"] == "d04"

    def test_pivot_reclaim_ignores_forward_outcome_and_fills_next_open(self):
        bars = [
            {"date": f"d{i:02}", "open": c, "high": c + 1,
             "low": c - 1, "close": c, "volume": 1_000_000}
            for i, c in enumerate((95, 101, 99, 98, 102, 103))
        ]
        detection = {
            "as_of_date": "d00", "sector": "Tech",
            "vcp_pattern": {
                "pivot_price": 100,
                "contractions": [{"low_price": 90}],
            },
            "forward_outcome": {"outcome_type": "stop_hit", "exit_date": "d02"},
        }
        with patch("portfolio_backtest.compute_edge_rank", return_value={
            ("AAA", "d00"): {"edge_rank": 82.5},
        }):
            signals = _candidate_signals(
                {"AAA": [detection]}, {"AAA": bars}, Config(),
                entry_rule="pivot_reclaim",
            )
        assert len(signals) == 1
        assert signals[0]["signal_date"] == "d04"
        assert signals[0]["fill_date"] == "d05"

    def test_inside_day_entry_ignores_outcome_and_fills_next_open(self):
        bars = [
            {"date": "d00", "open": 95, "high": 96, "low": 94, "close": 95, "volume": 1_000_000},
            {"date": "d01", "open": 101, "high": 105, "low": 99, "close": 103, "volume": 1_000_000},
            {"date": "d02", "open": 102, "high": 104, "low": 100, "close": 102, "volume": 1_000_000},
            {"date": "d03", "open": 103, "high": 106, "low": 101, "close": 105, "volume": 1_000_000},
        ]
        detection = {
            "as_of_date": "d00", "sector": "Tech",
            "vcp_pattern": {"pivot_price": 100, "contractions": [{"low_price": 90}]},
            "forward_outcome": {"outcome_type": "stop_hit", "exit_date": "d02"},
        }
        with patch("portfolio_backtest.compute_edge_rank", return_value={
            ("AAA", "d00"): {"edge_rank": 82.5},
        }):
            signals = _candidate_signals(
                {"AAA": [detection]}, {"AAA": bars}, Config(),
                entry_rule="inside_day_breakout",
            )
        assert len(signals) == 1
        assert signals[0]["signal_date"] == "d02"
        assert signals[0]["fill_date"] == "d03"

    def test_five_day_low_entry_ignores_outcome_and_fills_next_open(self):
        closes = (100, 101, 102, 103, 104, 105, 99, 100)
        bars = [
            {"date": f"d{i:02}", "open": close, "high": close + 1,
             "low": close - 1, "close": close, "volume": 1_000_000}
            for i, close in enumerate(closes)
        ]
        detection = {
            "as_of_date": "d05", "sector": "Tech",
            "vcp_pattern": {"pivot_price": 110, "contractions": [{"low_price": 90}]},
            "forward_outcome": {"outcome_type": "stop_hit", "exit_date": "d06"},
        }
        with patch("portfolio_backtest.compute_edge_rank", return_value={
            ("AAA", "d05"): {"edge_rank": 82.5},
        }):
            signals = _candidate_signals(
                {"AAA": [detection]}, {"AAA": bars}, Config(),
                entry_rule="five_day_low_pullback",
            )
        assert len(signals) == 1
        assert signals[0]["signal_date"] == "d06"
        assert signals[0]["fill_date"] == "d07"

    def test_five_day_low_reversal_fills_after_close_confirmation(self):
        closes = (100, 101, 102, 103, 104, 105, 99, 100, 102, 103)
        bars = [
            {"date": f"d{i:02}", "open": close, "high": close + 1,
             "low": close - 1, "close": close, "volume": 1_000_000}
            for i, close in enumerate(closes)
        ]
        detection = {
            "as_of_date": "d05", "sector": "Tech",
            "vcp_pattern": {"pivot_price": 110, "contractions": [{"low_price": 90}]},
            "forward_outcome": {"outcome_type": "stop_hit", "exit_date": "d06"},
        }
        with patch("portfolio_backtest.compute_edge_rank", return_value={
            ("AAA", "d05"): {"edge_rank": 82.5},
        }):
            signals = _candidate_signals(
                {"AAA": [detection]}, {"AAA": bars}, Config(),
                entry_rule="five_day_low_reversal",
            )
        assert len(signals) == 1
        assert signals[0]["signal_date"] == "d08"
        assert signals[0]["fill_date"] == "d09"

    def test_pivot_open_limit_uses_only_prior_close_and_opening_print(self):
        bars = [
            {"date": "d00", "open": 103, "high": 104, "low": 102, "close": 102, "volume": 1_000_000},
            {"date": "d01", "open": 99, "high": 120, "low": 80, "close": 85, "volume": 1_000_000},
        ]
        detection = {
            "as_of_date": "d00", "sector": "Tech",
            "vcp_pattern": {"pivot_price": 100, "contractions": [{"low_price": 90}]},
            "forward_outcome": {"outcome_type": "stop_hit", "exit_date": "d01"},
        }
        with patch("portfolio_backtest.compute_edge_rank", return_value={
            ("AAA", "d00"): {"edge_rank": 82.5},
        }):
            signals = _candidate_signals(
                {"AAA": [detection]}, {"AAA": bars}, Config(),
                entry_rule="pivot_open_limit",
            )
        assert len(signals) == 1
        assert signals[0]["signal_date"] == "d00"
        assert signals[0]["fill_date"] == "d01"

    def test_rebreak_waits_for_close_above_frozen_prior_high(self):
        bars = [{"date": f"d{i:02}", "open": c, "high": h, "low": lo,
                 "close": c, "volume": 1_000_000}
                for i, (c, h, lo) in enumerate([
                    *[(90, 91, 89)] * 19, (100, 102, 99), (101, 103, 100),
                    (100, 101, 90), (102, 103, 101), (104, 104.5, 103)])]
        # idx 21 is MA20 touch-and-hold; frozen prior high is 103.  A close
        # equal to 102 does not trigger; idx 23 closes above it.
        self.assertEqual(_plan_rebreak_after_pullback(bars, 19, 92), 23)

    def test_rebreak_invalidates_on_close_below_pattern_stop(self):
        closes = [90] * 19 + [100, 101, 100, 91, 105]
        bars = [{"date": f"d{i:02}", "open": c, "high": c + 1, "low": c - 1,
                 "close": c, "volume": 1_000_000} for i, c in enumerate(closes)]
        self.assertIsNone(_plan_rebreak_after_pullback(bars, 19, 92))

    def test_rebreak_respects_wait_window(self):
        closes = [90] * 19 + [100, 101, 100, 99, 105]
        bars = [{"date": f"d{i:02}", "open": c, "high": c + 1, "low": c - 1,
                 "close": c, "volume": 1_000_000} for i, c in enumerate(closes)]
        self.assertIsNone(_plan_rebreak_after_pullback(bars, 19, 92, rebreak_window=1))

    def test_trailing_adv_excludes_fill_day(self):
        bars = [{"close": 10, "volume": v} for v in (100, 200, 10_000)]
        self.assertEqual(_adv_dollars(bars, 2), 1500)

    def test_daily_marking_stop_gap_and_costs(self):
        bars = [
            {"date": f"d{i:02}", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1_000_000}
            for i in range(25)
        ]
        bars[23] = {"date": "d23", "open": 90, "high": 91, "low": 89, "close": 90, "volume": 1_000_000}
        signal = {"symbol": "AAA", "sector": "Tech", "signal_date": "d20", "fill_date": "d21",
                  "fill_idx": 21, "edge_rank": 82.5, "pattern_stop": 92}
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio({}, {"AAA": bars}, Config(initial_cash=100_000, commission_bps=5, slippage_bps=5))
        trade = out["trades"][0]
        self.assertEqual(trade["entry_price"], 100.1)  # next-bar open plus 10 bps
        self.assertEqual(trade["exit_price"], 89.91)  # gap below stop plus sell costs
        self.assertEqual(trade["exit_reason"], "stop")
        self.assertEqual(out["equity_curve"][0]["positions"], 1)
        self.assertLess(out["summary"]["max_drawdown_pct"], 0)

    def test_next_open_at_or_below_frozen_stop_cancels_entry(self):
        bars = [
            {"date": "d00", "open": 100, "high": 101, "low": 99, "close": 100,
             "volume": 1_000_000},
            {"date": "d01", "open": 91, "high": 94, "low": 90, "close": 93,
             "volume": 1_000_000},
        ]
        signal = {"symbol": "AAA", "sector": "Tech", "signal_date": "d00",
                  "fill_date": "d01", "fill_idx": 1, "edge_rank": 82.5,
                  "pattern_stop": 92}
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio({}, {"AAA": bars}, Config())
        self.assertEqual(out["trades"], [])
        self.assertEqual(out["summary"]["rejected"], {"open_at_or_below_stop": 1})

    def test_break_even_stop_activates_only_after_confirming_close(self):
        bars = [
            {"date": "d00", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1_000_000},
            {"date": "d01", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1_000_000},
            # The same bar trades below entry, then closes at +1R. It must not
            # be stopped retroactively by a stop armed at this close.
            {"date": "d02", "open": 101, "high": 109, "low": 99, "close": 108, "volume": 1_000_000},
            {"date": "d03", "open": 101, "high": 102, "low": 99, "close": 100, "volume": 1_000_000},
        ]
        signal = {"symbol": "AAA", "sector": "Tech", "signal_date": "d00",
                  "fill_date": "d01", "fill_idx": 1, "edge_rank": 82.5,
                  "pattern_stop": 92}
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars}, Config(commission_bps=0, slippage_bps=0),
                exit_rule="breakeven_r", exit_params={"trigger_r": 1.0},
            )
        trade = out["trades"][0]
        assert trade["exit_date"] == "d03"
        assert trade["exit_price"] == 100
        assert trade["exit_reason"] == "breakeven_stop"
        assert trade["breakeven_armed_date"] == "d02"

    def test_trailing_stop_ratchet_is_not_retroactive_to_same_day_low(self):
        bars = [
            {"date": "d00", "open": 100, "high": 101, "low": 99,
             "close": 100, "volume": 1_000_000},
            {"date": "d01", "open": 100, "high": 101, "low": 99,
             "close": 100, "volume": 1_000_000},
            # Close raises tomorrow's stop to 101.20, but today's earlier low
            # cannot trigger that newly confirmed level.
            {"date": "d02", "open": 101, "high": 111, "low": 95,
             "close": 110, "volume": 1_000_000},
            {"date": "d03", "open": 105, "high": 106, "low": 100,
             "close": 101, "volume": 1_000_000},
        ]
        signal = {
            "symbol": "AAA", "sector": "Tech", "signal_date": "d00",
            "fill_date": "d01", "fill_idx": 1, "edge_rank": 82.5,
            "pattern_stop": 92,
        }
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars}, Config(commission_bps=0, slippage_bps=0),
                exit_rule="trailing_stop", exit_params={"trailing_pct": 8},
            )
        trade = out["trades"][0]
        assert trade["exit_date"] == "d03"
        assert trade["exit_price"] == 101.2
        assert trade["exit_reason"] == "trailing_stop"

    def test_trailing_stop_removes_timeout(self):
        bars = [
            {"date": f"d{i:02}", "open": 100, "high": 101, "low": 99,
             "close": 100, "volume": 1_000_000}
            for i in range(8)
        ]
        signal = {
            "symbol": "AAA", "sector": "Tech", "signal_date": "d00",
            "fill_date": "d01", "fill_idx": 1, "edge_rank": 82.5,
            "pattern_stop": 92,
        }
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars},
                Config(max_hold_bars=2, commission_bps=0, slippage_bps=0),
                exit_rule="trailing_stop", exit_params={"trailing_pct": 8},
            )
        assert out["trades"][0]["exit_reason"] == "end_of_data"
        assert out["trades"][0]["exit_date"] == "d07"

    def test_trailing_stop_rejects_invalid_percentage(self):
        with self.assertRaises(ValueError):
            run_portfolio(
                {}, {}, Config(), exit_rule="trailing_stop",
                exit_params={"trailing_pct": 0},
            )

    def test_three_r_arm_switches_from_hard_stop_to_wide_trail_next_day(self):
        bars = [
            {"date": "d00", "open": 100, "high": 101, "low": 99,
             "close": 100, "volume": 1_000_000},
            # Entry at 100, R=8, and the entry close reaches +3R at 124.
            {"date": "d01", "open": 100, "high": 125, "low": 99,
             "close": 124, "volume": 1_000_000},
            # Armed trail is 124 * .76 = 94.24 and is active today.
            {"date": "d02", "open": 100, "high": 101, "low": 94,
             "close": 95, "volume": 1_000_000},
        ]
        signal = {
            "symbol": "AAA", "sector": "Tech", "signal_date": "d00",
            "fill_date": "d01", "fill_idx": 1, "edge_rank": 82.5,
            "pattern_stop": 92,
        }
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars}, Config(commission_bps=0, slippage_bps=0),
                exit_rule="armed_trailing_stop",
                exit_params={"trigger_r": 3, "trailing_pct": 24},
            )
        trade = out["trades"][0]
        assert trade["trailing_armed_date"] == "d01"
        assert trade["exit_date"] == "d02"
        assert trade["exit_price"] == 94.24
        assert trade["exit_reason"] == "armed_trailing_stop"

    def test_three_r_trail_keeps_hard_stop_and_has_no_timeout_before_arm(self):
        bars = [
            {"date": f"d{i:02}", "open": 100, "high": 105, "low": 93,
             "close": 105, "volume": 1_000_000}
            for i in range(8)
        ]
        signal = {
            "symbol": "AAA", "sector": "Tech", "signal_date": "d00",
            "fill_date": "d01", "fill_idx": 1, "edge_rank": 82.5,
            "pattern_stop": 92,
        }
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars},
                Config(max_hold_bars=2, commission_bps=0, slippage_bps=0),
                exit_rule="armed_trailing_stop",
                exit_params={"trigger_r": 3, "trailing_pct": 24},
            )
        trade = out["trades"][0]
        assert trade["exit_reason"] == "end_of_data"
        assert "trailing_armed_date" not in trade

    def test_holding_window_exit_uses_first_outside_session_open(self):
        bars = [
            {"date": date, "open": open_, "high": 110, "low": low,
             "close": 105, "volume": 1_000_000}
            for date, open_, low in (
                ("2024-01-02", 100, 99),
                ("2024-01-03", 101, 99),
                ("2024-01-04", 102, 99),
                # Outside the inclusive window; even though the low also
                # breaches the hard stop, the opening liquidation comes first.
                ("2024-01-05", 103, 80),
            )
        ]
        signal = {
            "symbol": "AAA", "sector": "Tech", "signal_date": "2024-01-02",
            "fill_date": "2024-01-03", "fill_idx": 1, "edge_rank": 82.5,
            "pattern_stop": 92,
        }
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars}, Config(commission_bps=0, slippage_bps=0),
                exit_rule="armed_trailing_stop",
                exit_params={
                    "trigger_r": 3, "trailing_pct": 24,
                    "holding_windows": (("2024-01-02", "2024-01-04"),),
                },
            )
        trade = out["trades"][0]
        assert trade["exit_date"] == "2024-01-05"
        assert trade["exit_price"] == 103
        assert trade["exit_reason"] == "period_exit"

    def test_open_ended_holding_window_does_not_force_exit(self):
        bars = [
            {"date": date, "open": 100, "high": 106, "low": 93,
             "close": 105, "volume": 1_000_000}
            for date in ("2025-04-07", "2025-04-08", "2025-04-09")
        ]
        signal = {
            "symbol": "AAA", "sector": "Tech", "signal_date": "2025-04-07",
            "fill_date": "2025-04-08", "fill_idx": 1, "edge_rank": 82.5,
            "pattern_stop": 92,
        }
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars}, Config(commission_bps=0, slippage_bps=0),
                exit_rule="armed_trailing_stop",
                exit_params={
                    "trigger_r": 3, "trailing_pct": 24,
                    "holding_windows": (("2025-04-07", None),),
                },
            )
        assert out["trades"][0]["exit_reason"] == "end_of_data"

    def test_qqq_synchronized_exit_uses_finite_end_open(self):
        bars = [
            {"date": date, "open": open_, "high": 110, "low": 99,
             "close": 105, "volume": 1_000_000}
            for date, open_ in (
                ("2024-12-17", 100),
                ("2024-12-18", 101),
                ("2024-12-19", 102),
                ("2024-12-20", 103),
            )
        ]
        signal = {
            "symbol": "AAA", "sector": "Tech", "signal_date": "2024-12-17",
            "fill_date": "2024-12-18", "fill_idx": 1, "edge_rank": 82.5,
            "pattern_stop": 92,
        }
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars}, Config(commission_bps=0, slippage_bps=0),
                exit_rule="armed_trailing_stop",
                exit_params={
                    "trigger_r": 3, "trailing_pct": 24,
                    "holding_windows": (("2023-10-30", "2024-12-19"),),
                    "holding_window_exit_timing": "window_end_open",
                },
            )
        trade = out["trades"][0]
        assert trade["exit_date"] == "2024-12-19"
        assert trade["exit_price"] == 102
        assert trade["exit_reason"] == "period_exit"

    def test_holding_window_exit_timing_rejects_unknown_mode(self):
        with self.assertRaisesRegex(ValueError, "holding_window_exit_timing"):
            run_portfolio(
                {}, {}, Config(), exit_rule="armed_trailing_stop",
                exit_params={
                    "trigger_r": 3, "trailing_pct": 24,
                    "holding_window_exit_timing": "same_close",
                },
            )

    def test_holding_windows_reject_invalid_dates(self):
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            run_portfolio(
                {}, {}, Config(), exit_rule="armed_trailing_stop",
                exit_params={
                    "trigger_r": 3, "trailing_pct": 24,
                    "holding_windows": (("not-a-date", None),),
                },
            )

    def test_three_r_trail_rejects_invalid_parameters(self):
        with self.assertRaises(ValueError):
            run_portfolio(
                {}, {}, Config(), exit_rule="armed_trailing_stop",
                exit_params={"trigger_r": 0, "trailing_pct": 24},
            )

    def test_explicit_simulation_start_preserves_pre_signal_cash_dates(self):
        bars = [
            {"date": f"d{i:02}", "open": 100, "high": 101, "low": 99,
             "close": 100, "volume": 1_000_000}
            for i in range(5)
        ]
        signal = {
            "symbol": "AAA", "sector": "Tech", "signal_date": "d02",
            "fill_date": "d03", "fill_idx": 3, "edge_rank": 82.5,
            "pattern_stop": 92,
        }
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars}, Config(commission_bps=0, slippage_bps=0),
                simulation_start_date="d00",
            )
        assert out["equity_curve"][0]["date"] == "d00"
        assert out["equity_curve"][0]["positions"] == 0

    def test_pivot_failure_close_exits_at_following_open(self):
        bars = [
            {"date": "d00", "open": 101, "high": 102, "low": 100, "close": 101, "volume": 1_000_000},
            {"date": "d01", "open": 102, "high": 103, "low": 101, "close": 102, "volume": 1_000_000},
            {"date": "d02", "open": 101, "high": 102, "low": 98, "close": 99, "volume": 1_000_000},
            {"date": "d03", "open": 98, "high": 99, "low": 96, "close": 97, "volume": 1_000_000},
        ]
        signal = {"symbol": "AAA", "sector": "Tech", "signal_date": "d00",
                  "fill_date": "d01", "fill_idx": 1, "edge_rank": 82.5,
                  "pattern_stop": 92, "pivot": 100}
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars}, Config(commission_bps=0, slippage_bps=0),
                exit_rule="pivot_failure",
            )
        trade = out["trades"][0]
        assert trade["pivot_failure_signal_date"] == "d02"
        assert trade["exit_date"] == "d03"
        assert trade["exit_price"] == 98
        assert trade["exit_reason"] == "pivot_failure"

    def test_stop_reentry_is_limited_to_one_second_attempt(self):
        bars = [
            {"date": "d00", "open": 101, "high": 102, "low": 100, "close": 101, "volume": 1_000_000},
            {"date": "d01", "open": 102, "high": 103, "low": 101, "close": 102, "volume": 1_000_000},
            {"date": "d02", "open": 93, "high": 102, "low": 92, "close": 101, "volume": 1_000_000},
            {"date": "d03", "open": 102, "high": 103, "low": 101, "close": 102, "volume": 1_000_000},
            {"date": "d04", "open": 93, "high": 102, "low": 92, "close": 101, "volume": 1_000_000},
            {"date": "d05", "open": 102, "high": 103, "low": 101, "close": 102, "volume": 1_000_000},
        ]
        signal = {
            "symbol": "AAA", "sector": "Tech", "signal_date": "d00",
            "fill_date": "d01", "fill_idx": 1, "edge_rank": 82.5,
            "pattern_stop": 92, "pivot": 100, "attempt": 1,
        }
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars}, Config(commission_bps=0, slippage_bps=0),
                entry_rule="down_close_stop_reentry",
                entry_params={"reentry_window": 20},
            )
        assert out["summary"]["signals"] == 2
        assert [trade["attempt"] for trade in out["trades"]] == [1, 2]
        assert [trade["entry_date"] for trade in out["trades"]] == ["d01", "d03"]
        assert [trade["exit_reason"] for trade in out["trades"]] == ["stop", "stop"]

    def test_distribution_cluster_exits_at_open_after_third_event(self):
        bars = [
            {"date": "d00", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 100},
            {"date": "d01", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 100},
            {"date": "d02", "open": 100, "high": 101, "low": 98, "close": 99, "volume": 110},
            {"date": "d03", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 100},
            {"date": "d04", "open": 100, "high": 101, "low": 98, "close": 99, "volume": 120},
            {"date": "d05", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 100},
            {"date": "d06", "open": 100, "high": 101, "low": 98, "close": 99, "volume": 130},
            {"date": "d07", "open": 98, "high": 99, "low": 97, "close": 98, "volume": 100},
        ]
        signal = {
            "symbol": "AAA", "sector": "Tech", "signal_date": "d00",
            "fill_date": "d01", "fill_idx": 1, "edge_rank": 82.5,
            "pattern_stop": 90, "pivot": 100,
        }
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars}, Config(commission_bps=0, slippage_bps=0),
                exit_rule="distribution_cluster",
                exit_params={"event_count": 3, "event_window": 15},
            )
        trade = out["trades"][0]
        assert trade["distribution_exit_signal_date"] == "d06"
        assert trade["exit_date"] == "d07"
        assert trade["exit_price"] == 98
        assert trade["exit_reason"] == "distribution_cluster"

    def test_distribution_exit_rejects_nonpositive_parameters(self):
        bars = [
            {"date": "d00", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 100},
            {"date": "d01", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 100},
            {"date": "d02", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 100},
        ]
        signal = {
            "symbol": "AAA", "sector": "Tech", "signal_date": "d00",
            "fill_date": "d01", "fill_idx": 1, "edge_rank": 82.5,
            "pattern_stop": 90, "pivot": 100,
        }
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            with self.assertRaises(ValueError):
                run_portfolio(
                    {}, {"AAA": bars}, Config(),
                    exit_rule="distribution_cluster",
                    exit_params={"event_count": 0, "event_window": 15},
                )

    def test_loss_distribution_waits_until_position_is_below_entry(self):
        bars = [
            {"date": "d00", "open": 100, "high": 101, "low": 95, "close": 100, "volume": 100},
            {"date": "d01", "open": 100, "high": 102, "low": 95, "close": 101, "volume": 100},
            {"date": "d02", "open": 103, "high": 104, "low": 95, "close": 102, "volume": 110},
            {"date": "d03", "open": 104, "high": 105, "low": 95, "close": 103, "volume": 100},
            {"date": "d04", "open": 102, "high": 103, "low": 95, "close": 102, "volume": 120},
            {"date": "d05", "open": 103, "high": 104, "low": 95, "close": 103, "volume": 100},
            # Third event remains profitable: do not exit.
            {"date": "d06", "open": 102, "high": 103, "low": 95, "close": 102, "volume": 130},
            {"date": "d07", "open": 101, "high": 102, "low": 94, "close": 99, "volume": 140},
            {"date": "d08", "open": 98, "high": 99, "low": 94, "close": 98, "volume": 100},
        ]
        signal = {
            "symbol": "AAA", "sector": "Tech", "signal_date": "d00",
            "fill_date": "d01", "fill_idx": 1, "edge_rank": 82.5,
            "pattern_stop": 90, "pivot": 100,
        }
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars}, Config(commission_bps=0, slippage_bps=0),
                exit_rule="loss_distribution_cluster",
                exit_params={"event_count": 3, "event_window": 15},
            )
        trade = out["trades"][0]
        assert trade["distribution_exit_signal_date"] == "d07"
        assert trade["exit_date"] == "d08"
        assert trade["exit_reason"] == "loss_distribution_cluster"

    def test_followthrough_exit_uses_next_open_after_fifth_close(self):
        bars = [
            {"date": f"d{i:02}", "open": open_, "high": 102, "low": 95,
             "close": close, "volume": 1000}
            for i, (open_, close) in enumerate((
                (100, 100), (100, 100), (100, 101), (100, 100),
                (100, 101), (100, 101), (99, 99),
            ))
        ]
        signal = {
            "symbol": "AAA", "sector": "Tech", "signal_date": "d00",
            "fill_date": "d01", "fill_idx": 1, "edge_rank": 82.5,
            "pattern_stop": 90, "pivot": 100,
        }
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars}, Config(commission_bps=0, slippage_bps=0),
                exit_rule="followthrough_sma",
                exit_params={"early_days": 5, "min_gain_pct": 2,
                             "arm_gain_pct": 8, "sma_period": 10},
            )
        trade = out["trades"][0]
        assert trade["managed_exit_signal_date"] == "d05"
        assert trade["exit_date"] == "d06"
        assert trade["exit_reason"] == "no_followthrough"

    def test_followthrough_sma_break_only_after_prior_close_arms_it(self):
        bars = [
            {"date": f"d{i:02}", "open": open_, "high": close + 1, "low": 95,
             "close": close, "volume": 1000}
            for i, (open_, close) in enumerate((
                (100, 100), (100, 100), (108, 109), (103, 102), (101, 101),
            ))
        ]
        signal = {
            "symbol": "AAA", "sector": "Tech", "signal_date": "d00",
            "fill_date": "d01", "fill_idx": 1, "edge_rank": 82.5,
            "pattern_stop": 90, "pivot": 100,
        }
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars}, Config(commission_bps=0, slippage_bps=0),
                exit_rule="followthrough_sma",
                exit_params={"early_days": 10, "min_gain_pct": 2,
                             "arm_gain_pct": 8, "sma_period": 3},
            )
        trade = out["trades"][0]
        assert trade["managed_exit_armed_date"] == "d02"
        assert trade["managed_exit_signal_date"] == "d03"
        assert trade["exit_date"] == "d04"
        assert trade["exit_reason"] == "sma3_break"

    def test_model_decay_exits_at_precomputed_next_open(self):
        bars = [
            {"date": f"d{i:02}", "open": 100 + i, "high": 102 + i,
             "low": 95, "close": 101 + i, "volume": 1000}
            for i in range(5)
        ]
        signal = {
            "symbol": "AAA", "sector": "Tech", "signal_date": "d00",
            "fill_date": "d01", "fill_idx": 1, "edge_rank": 82.5,
            "pattern_stop": 90, "pivot": 100, "model_exit_idx": 3,
        }
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars}, Config(commission_bps=0, slippage_bps=0),
                exit_rule="model_decay",
            )
        assert out["trades"][0]["exit_date"] == "d03"
        assert out["trades"][0]["exit_reason"] == "model_decay"

    def test_fixed_time_exit_uses_same_precomputed_next_open_path(self):
        bars = [
            {"date": f"d{i:02}", "open": 100 + i, "high": 102 + i,
             "low": 95, "close": 101 + i, "volume": 1000}
            for i in range(5)
        ]
        signal = {"symbol":"AAA","sector":"Tech","signal_date":"d00",
                  "fill_date":"d01","fill_idx":1,"edge_rank":82.5,
                  "pattern_stop":90,"pivot":100,"model_exit_idx":3}
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio({}, {"AAA":bars}, Config(commission_bps=0, slippage_bps=0), exit_rule="fixed_time")
        assert out["trades"][0]["exit_reason"] == "fixed_time"
        assert out["trades"][0]["exit_date"] == "d03"

    def test_opening_limit_entry_can_stop_later_on_entry_day(self):
        bars = [
            {"date": "d00", "open": 100, "high": 101, "low": 99,
             "close": 100, "volume": 1_000_000},
            {"date": "d01", "open": 98, "high": 100, "low": 89,
             "close": 91, "volume": 1_000_000},
            {"date": "d02", "open": 92, "high": 93, "low": 91,
             "close": 92, "volume": 1_000_000},
        ]
        signal = {"symbol": "AAA", "sector": "Tech", "signal_date": "d00",
                  "fill_date": "d01", "fill_idx": 1, "edge_rank": 82.5,
                  "pattern_stop": 90, "pivot": 100, "raw_entry_price": 98,
                  "entry_day_stop": True, "model_exit_idx": 2}
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio(
                {}, {"AAA": bars},
                Config(commission_bps=0, slippage_bps=0),
                exit_rule="fixed_time",
            )
        trade = out["trades"][0]
        assert trade["entry_date"] == "d01"
        assert trade["exit_date"] == "d01"
        assert trade["exit_reason"] == "entry_day_stop"
        assert trade["exit_price"] == 90.16

    def test_position_and_sector_caps(self):
        bars = [{"date": f"d{i:02}", "open": 10, "high": 11, "low": 9.5, "close": 10, "volume": 10_000_000}
                for i in range(24)]
        signals = [{"symbol": s, "sector": "Tech", "signal_date": "d20", "fill_date": "d21",
                    "fill_idx": 21, "edge_rank": e, "pattern_stop": 8}
                   for s, e in (("AAA", 80), ("BBB", 70), ("CCC", 60))]
        with patch("portfolio_backtest._candidate_signals", return_value=signals):
            cfg = Config(initial_cash=10_000, max_positions=2, max_position_pct=20, max_sector_pct=25,
                         commission_bps=0, slippage_bps=0)
            out = run_portfolio({}, {s: bars for s in ("AAA", "BBB", "CCC")}, cfg)
        entered = [t["symbol"] for t in out["trades"]]
        self.assertEqual(entered, ["AAA", "BBB"])
        self.assertEqual(out["summary"]["rejected"]["duplicate_or_position_limit"], 1)
        self.assertLessEqual(sum(t["shares"] * t["entry_price"] for t in out["trades"]), 2500)

    def test_missing_symbol_date_uses_last_close(self):
        aaa = [
            {"date": "d20", "open": 10, "high": 10, "low": 10, "close": 10, "volume": 1_000_000},
            {"date": "d21", "open": 10, "high": 12, "low": 10, "close": 12, "volume": 1_000_000},
        ]
        spy = [
            {"date": d, "open": 100, "high": 100, "low": 100, "close": 100, "volume": 0}
            for d in ("d20", "d21", "d22")
        ]
        signal = {"symbol": "AAA", "sector": "Tech", "signal_date": "d20", "fill_date": "d21",
                  "fill_idx": 1, "edge_rank": 82.5, "pattern_stop": 8}
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio({}, {"AAA": aaa, "SPY": spy}, Config(commission_bps=0, slippage_bps=0))
        self.assertEqual(out["equity_curve"][-1]["equity"], out["equity_curve"][-2]["equity"])
        self.assertIn("excess_return", out["equity_curve"][-1])
        # Day-one benchmark exposure is zero; the following day's benchmark
        # return is scaled by the prior close's portfolio exposure.
        self.assertEqual(out["equity_curve"][0]["exposure_matched_spy_return"], 0.0)
        self.assertGreater(out["equity_curve"][0]["gross_exposure_pct"], 0)
        self.assertIn("exposure_matched_excess_return", out["equity_curve"][-1])


if __name__ == "__main__":
    unittest.main()
