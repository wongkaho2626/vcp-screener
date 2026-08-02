"""Deterministic causal tests for the stock-versus-SPY MA50 slope gate."""

import copy
import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from relative_ma50_slope_experiment import (  # noqa: E402
    annotate_signals,
    calculate_relative_ma50_slope,
    select_signals,
)


def _sessions(count=70, start=date(2024, 1, 2)):
    output = []
    current = start
    while len(output) < count:
        if current.weekday() < 5:
            output.append(current.isoformat())
        current += timedelta(days=1)
    return output


def _linear(start, step, count=70):
    return [start + step * index for index in range(count)]


def _bars(values, dates=None):
    dates = dates or _sessions(len(values))
    return [{"date": session, "adjClose": value, "close": 999_999}
            for session, value in zip(dates, values)]


class RelativeMa50SlopeTests(unittest.TestCase):
    def _calculate(self, stock_values, spy_values):
        return calculate_relative_ma50_slope(
            _bars(stock_values), _bars(spy_values), _sessions()[-1])

    def test_positive_stock_slope_while_spy_slope_falls_passes(self):
        result = self._calculate(_linear(100, 1), _linear(200, -1))
        self.assertTrue(result["positive_relative_ma_slope"])

    def test_both_rise_but_stock_slope_is_faster_passes(self):
        result = self._calculate(_linear(100, 1), _linear(100, .25))
        self.assertTrue(result["positive_relative_ma_slope"])

    def test_positive_stock_slope_slower_than_spy_fails(self):
        result = self._calculate(_linear(100, .25), _linear(100, 1))
        self.assertFalse(result["positive_relative_ma_slope"])

    def test_negative_stock_slope_fails_even_if_spy_falls_faster(self):
        result = self._calculate(_linear(200, -.25), _linear(200, -1))
        self.assertGreater(result["relative_ma_slope_pct"], 0)
        self.assertFalse(result["positive_relative_ma_slope"])

    def test_equal_stock_and_spy_slopes_fail_strict_comparison(self):
        values = _linear(100, 1)
        result = self._calculate(values, values)
        self.assertEqual(result["relative_ma_slope_pct"], 0)
        self.assertFalse(result["positive_relative_ma_slope"])

    def test_stock_close_below_its_rising_ma_fails(self):
        stock = _linear(100, 1)
        stock[-1] = 50
        result = self._calculate(stock, _linear(100, .25))
        self.assertGreater(result["stock_ma_slope_pct"], 0)
        self.assertFalse(result["positive_relative_ma_slope"])

    def test_insufficient_stock_history_is_unavailable(self):
        result = calculate_relative_ma50_slope(
            _bars(_linear(100, 1, 69), _sessions(69)),
            _bars(_linear(100, .25)), _sessions()[-1])
        self.assertIsNone(result)

    def test_insufficient_spy_history_is_unavailable(self):
        result = calculate_relative_ma50_slope(
            _bars(_linear(100, 1)),
            _bars(_linear(100, .25, 69), _sessions(69)), _sessions()[-1])
        self.assertIsNone(result)

    def test_insufficient_common_history_is_unavailable(self):
        dates = _sessions(71)
        stock = _bars(_linear(100, 1), dates[:70])
        spy = _bars(_linear(100, .25), dates[1:])
        self.assertIsNone(calculate_relative_ma50_slope(
            stock, spy, dates[-1]))

    def test_mismatched_calendars_use_only_actual_common_dates(self):
        dates = _sessions(72)
        stock_dates = [session for index, session in enumerate(dates)
                       if index != 10]
        result = calculate_relative_ma50_slope(
            _bars(_linear(100, 1, len(stock_dates)), stock_dates),
            _bars(_linear(100, .25, len(dates)), dates), dates[-1])
        self.assertEqual(result["relative_ma_signal_date"], dates[-1])
        self.assertTrue(result["positive_relative_ma_slope"])

    def test_weekend_as_of_uses_latest_common_session(self):
        dates = _sessions()
        last = date.fromisoformat(dates[-1])
        saturday = (last + timedelta(days=(5 - last.weekday()) % 7)).isoformat()
        result = calculate_relative_ma50_slope(
            _bars(_linear(100, 1)), _bars(_linear(100, .25)), saturday)
        self.assertEqual(result["relative_ma_signal_date"], dates[-1])

    def test_future_bars_are_not_accessed(self):
        dates = _sessions(71)
        stock = _bars(_linear(100, 1), dates[:70]) + [
            {"date": dates[-1], "adjClose": 1}]
        spy = _bars(_linear(100, .25), dates[:70]) + [
            {"date": dates[-1], "adjClose": 10_000}]
        with_future = calculate_relative_ma50_slope(stock, spy, dates[-2])
        without_future = calculate_relative_ma50_slope(
            stock[:-1], spy[:-1], dates[-2])
        self.assertEqual(with_future, without_future)

    def test_signal_does_not_use_fill_day_close(self):
        dates = _sessions(71)
        stock = _bars(_linear(100, 1), dates[:70]) + [
            {"date": dates[-1], "adjClose": 1}]
        spy = _bars(_linear(100, .25), dates[:70]) + [
            {"date": dates[-1], "adjClose": 10_000}]
        signal = {"symbol": "ABC", "signal_date": dates[-2],
                  "fill_date": dates[-1]}
        annotated, counts = annotate_signals(
            [signal], {"ABC": stock, "SPY": spy})
        self.assertTrue(annotated[0]["positive_relative_ma50_slope"])
        self.assertEqual(annotated[0]["relative_ma50_signal_date"], dates[-2])
        self.assertEqual(annotated[0]["fill_date"], dates[-1])
        self.assertEqual(counts["positive"], 1)

    def test_inputs_are_not_mutated(self):
        stock = list(reversed(_bars(_linear(100, 1))))
        spy = list(reversed(_bars(_linear(100, .25))))
        before = copy.deepcopy((stock, spy))
        calculate_relative_ma50_slope(stock, spy, _sessions()[-1])
        self.assertEqual((stock, spy), before)

    def test_disabled_gate_copies_all_baseline_signals(self):
        signals = [{"symbol": "A", "positive_relative_ma50_slope": True},
                   {"symbol": "B", "positive_relative_ma50_slope": False},
                   {"symbol": "C", "positive_relative_ma50_slope": None}]
        selected = select_signals(signals, "all")
        self.assertEqual(selected, signals)
        self.assertIsNot(selected[0], signals[0])


if __name__ == "__main__":
    unittest.main()
