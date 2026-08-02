"""Causality and strict-comparison tests for Trial 520."""

import copy
import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from ma50_slope_experiment import (  # noqa: E402
    annotate_signals,
    calculate_ma50_slope,
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


def _bars(values, dates=None):
    dates = dates or _sessions(len(values))
    return [{"date": session, "adjClose": value, "close": 999_999}
            for session, value in zip(dates, values)]


class Ma50SlopeTests(unittest.TestCase):
    def test_rising_ma_and_close_above_ma_passes(self):
        result = calculate_ma50_slope(_bars(list(range(100, 170))), _sessions()[-1])
        self.assertTrue(result["positive_ma_slope"])

    def test_flat_ma_fails_strict_slope(self):
        result = calculate_ma50_slope(_bars([100] * 70), _sessions()[-1])
        self.assertFalse(result["positive_ma_slope"])

    def test_falling_ma_fails(self):
        result = calculate_ma50_slope(_bars(list(range(170, 100, -1))), _sessions()[-1])
        self.assertFalse(result["positive_ma_slope"])

    def test_close_below_rising_ma_fails(self):
        values = list(range(100, 170))
        values[-1] = 50
        result = calculate_ma50_slope(_bars(values), _sessions()[-1])
        self.assertFalse(result["positive_ma_slope"])

    def test_equal_ma_values_fail_even_when_close_is_above(self):
        values = [100] * 70
        values[-2:] = [90, 110]
        result = calculate_ma50_slope(_bars(values), _sessions()[-1])
        self.assertEqual(result["ma_value"], result["ma_20_sessions_ago"])
        self.assertFalse(result["positive_ma_slope"])

    def test_69_observations_are_insufficient(self):
        self.assertIsNone(calculate_ma50_slope(
            _bars(list(range(100, 169))), _sessions(69)[-1]))

    def test_future_bar_is_not_accessed(self):
        dates = _sessions(71)
        values = list(range(100, 170))
        bars = _bars(values, dates[:70]) + [
            {"date": dates[-1], "adjClose": 1, "close": 1}]
        with_future = calculate_ma50_slope(bars, dates[-2])
        without_future = calculate_ma50_slope(bars[:-1], dates[-2])
        self.assertEqual(with_future, without_future)

    def test_weekend_as_of_uses_latest_completed_session(self):
        dates = _sessions()
        last = date.fromisoformat(dates[-1])
        saturday = (last + timedelta(days=(5 - last.weekday()) % 7)).isoformat()
        result = calculate_ma50_slope(_bars(list(range(100, 170))), saturday)
        self.assertEqual(result["ma_signal_date"], dates[-1])

    def test_inputs_are_not_mutated(self):
        bars = list(reversed(_bars(list(range(100, 170)))))
        before = copy.deepcopy(bars)
        calculate_ma50_slope(bars, _sessions()[-1])
        self.assertEqual(bars, before)

    def test_signal_close_does_not_use_fill_day_close(self):
        dates = _sessions(71)
        stock = _bars(list(range(100, 170)), dates[:70]) + [
            {"date": dates[-1], "adjClose": 1, "close": 1}]
        signal = {"symbol": "ABC", "signal_date": dates[-2],
                  "fill_date": dates[-1]}
        annotated, counts = annotate_signals([signal], {"ABC": stock})
        self.assertTrue(annotated[0]["positive_ma50_slope"])
        self.assertEqual(annotated[0]["ma50_signal_date"], dates[-2])
        self.assertEqual(annotated[0]["fill_date"], dates[-1])
        self.assertEqual(counts["positive"], 1)

    def test_disabled_gate_copies_every_baseline_signal(self):
        signals = [{"symbol": "A", "positive_ma50_slope": True},
                   {"symbol": "B", "positive_ma50_slope": False},
                   {"symbol": "C", "positive_ma50_slope": None}]
        selected = select_signals(signals, "all")
        self.assertEqual(selected, signals)
        self.assertIsNot(selected[0], signals[0])


if __name__ == "__main__":
    unittest.main()
