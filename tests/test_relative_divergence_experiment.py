"""Deterministic tests for the causal stock/SPY divergence experiment."""

import copy
import os
import sys
import unittest
from datetime import date, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from relative_divergence_experiment import (  # noqa: E402
    annotate_signals,
    calculate_relative_divergence,
    select_signals,
)
from portfolio_backtest import Config, run_portfolio  # noqa: E402


def _sessions(count=21, start=date(2024, 1, 2)):
    output = []
    current = start
    while len(output) < count:
        if current.weekday() < 5:
            output.append(current.isoformat())
        current += timedelta(days=1)
    return output


def _bars(start_price, end_price, dates=None):
    dates = dates or _sessions()
    denominator = max(1, len(dates) - 1)
    return [
        {
            "date": session,
            "adjClose": start_price + (end_price - start_price) * index / denominator,
            "close": 999_999,  # adjusted close must take precedence
        }
        for index, session in enumerate(dates)
    ]


class RelativeDivergenceCalculationTests(unittest.TestCase):
    def _calculate(self, stock_end, spy_end):
        return calculate_relative_divergence(
            _bars(100, stock_end), _bars(100, spy_end), _sessions()[-1], 20)

    def test_positive_stock_while_spy_falls_is_true(self):
        self.assertTrue(self._calculate(108, 97)["positive_divergence"])

    def test_stock_outperforms_rising_spy_is_true(self):
        self.assertTrue(self._calculate(108, 104)["positive_divergence"])

    def test_positive_stock_that_lags_spy_is_false(self):
        self.assertFalse(self._calculate(103, 107)["positive_divergence"])

    def test_declining_stock_that_beats_spy_is_false(self):
        self.assertFalse(self._calculate(98, 94)["positive_divergence"])

    def test_flat_stock_is_strictly_false(self):
        self.assertFalse(self._calculate(100, 95)["positive_divergence"])

    def test_equal_returns_are_strictly_false(self):
        self.assertFalse(self._calculate(108, 108)["positive_divergence"])

    def test_insufficient_ticker_history_is_unavailable(self):
        result = calculate_relative_divergence(
            _bars(100, 108, _sessions(20)), _bars(100, 104), _sessions()[-1], 20)
        self.assertIsNone(result)

    def test_insufficient_spy_history_is_unavailable(self):
        result = calculate_relative_divergence(
            _bars(100, 108), _bars(100, 104, _sessions(20)), _sessions()[-1], 20)
        self.assertIsNone(result)

    def test_missing_ticker_session_uses_actual_common_dates(self):
        dates = _sessions(22)
        stock_dates = [session for index, session in enumerate(dates) if index != 10]
        result = calculate_relative_divergence(
            _bars(100, 108, stock_dates), _bars(100, 104, dates), dates[-1], 20)
        self.assertEqual(result["lookback_start_date"], dates[0])
        self.assertEqual(result["divergence_signal_date"], dates[-1])

    def test_mismatched_calendars_never_mix_return_endpoints(self):
        dates = _sessions(23)
        stock_dates = dates[:-1]
        spy_dates = dates[1:]
        result = calculate_relative_divergence(
            _bars(100, 108, stock_dates), _bars(100, 104, spy_dates), dates[-1], 20)
        self.assertEqual(result["lookback_start_date"], dates[1])
        self.assertEqual(result["divergence_signal_date"], dates[-2])

    def test_weekend_as_of_uses_last_common_session(self):
        dates = _sessions()
        saturday = (date.fromisoformat(dates[-1]) + timedelta(
            days=(5 - date.fromisoformat(dates[-1]).weekday()) % 7)).isoformat()
        result = calculate_relative_divergence(
            _bars(100, 108), _bars(100, 104), saturday, 20)
        self.assertEqual(result["divergence_signal_date"], dates[-1])

    def test_future_bars_are_not_accessed(self):
        dates = _sessions(22)
        as_of = dates[-2]
        stock = _bars(100, 108, dates[:-1]) + [{"date": dates[-1], "adjClose": 1}]
        spy = _bars(100, 104, dates[:-1]) + [{"date": dates[-1], "adjClose": 1_000}]
        with_future = calculate_relative_divergence(stock, spy, as_of, 20)
        without_future = calculate_relative_divergence(stock[:-1], spy[:-1], as_of, 20)
        self.assertEqual(with_future, without_future)

    def test_entry_day_close_cannot_change_prior_signal(self):
        dates = _sessions(22)
        signal = {
            "symbol": "ABC", "signal_date": dates[-2], "fill_date": dates[-1],
        }
        stock = _bars(100, 108, dates[:-1]) + [{"date": dates[-1], "adjClose": 1}]
        spy = _bars(100, 104, dates[:-1]) + [{"date": dates[-1], "adjClose": 1_000}]
        annotated, _ = annotate_signals([signal], {"ABC": stock, "SPY": spy})
        self.assertTrue(annotated[0]["positive_rs_divergence"])
        self.assertEqual(annotated[0]["divergence_signal_date"], dates[-2])
        self.assertEqual(annotated[0]["fill_date"], dates[-1])

    def test_inputs_are_not_mutated(self):
        stock = list(reversed(_bars(100, 108)))
        spy = list(reversed(_bars(100, 104)))
        before = copy.deepcopy((stock, spy))
        calculate_relative_divergence(stock, spy, _sessions()[-1], 20)
        self.assertEqual((stock, spy), before)

    def test_disabled_gate_reproduces_baseline_signal_set_exactly(self):
        signals = [
            {"symbol": "PASS", "positive_rs_divergence": True, "edge_rank": 90},
            {"symbol": "FAIL", "positive_rs_divergence": False, "edge_rank": 80},
            {"symbol": "MISS", "positive_rs_divergence": None, "edge_rank": 70},
        ]
        selected = select_signals(signals, "all")
        self.assertEqual(selected, signals)
        self.assertIsNot(selected[0], signals[0])

    def test_disabled_gate_reproduces_portfolio_result_exactly(self):
        dates = _sessions(8)
        stock = [
            {"date": session, "open": 100 + index, "high": 102 + index,
             "low": 99 + index, "close": 101 + index, "adjClose": 101 + index,
             "volume": 1_000_000}
            for index, session in enumerate(dates)
        ]
        spy = [
            {"date": session, "open": 400 + index, "high": 402 + index,
             "low": 399 + index, "close": 401 + index, "adjClose": 401 + index,
             "volume": 10_000_000}
            for index, session in enumerate(dates)
        ]
        signals = [{
            "symbol": "ABC", "sector": "Industrials",
            "signal_date": dates[1], "fill_date": dates[2], "fill_idx": 2,
            "edge_rank": 80, "pattern_stop": 90, "pivot": 100,
            "positive_rs_divergence": None,
        }]
        prices = {"ABC": stock, "SPY": spy}
        with patch("portfolio_backtest._candidate_signals", return_value=signals):
            baseline = run_portfolio({}, prices, Config())
        with patch("portfolio_backtest._candidate_signals",
                   return_value=select_signals(signals, "all")):
            disabled_gate = run_portfolio({}, prices, Config())
        self.assertEqual(disabled_gate, baseline)

    def test_two_percentage_point_threshold_is_strict(self):
        result = calculate_relative_divergence(
            _bars(100, 108), _bars(100, 106), _sessions()[-1], 20,
            threshold_pct=2,
        )
        self.assertFalse(result["positive_divergence"])


if __name__ == "__main__":
    unittest.main()
