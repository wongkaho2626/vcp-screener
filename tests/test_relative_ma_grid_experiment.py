"""Focused tests for the prespecified relative-MA period grid."""

import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from relative_ma_grid_experiment import (  # noqa: E402
    MA_PERIODS,
    _cohort_mean_excess,
    annotate_signals,
    select_grid_candidates,
    select_positive,
)


def _sessions(count, start=date(2024, 1, 2)):
    output = []
    current = start
    while len(output) < count:
        if current.weekday() < 5:
            output.append(current.isoformat())
        current += timedelta(days=1)
    return output


def _bars(count, step):
    return [{"date": session, "adjClose": 100 + step * index}
            for index, session in enumerate(_sessions(count))]


class RelativeMaGridTests(unittest.TestCase):
    def test_grid_is_exactly_ten_through_two_hundred_by_ten(self):
        self.assertEqual(MA_PERIODS, tuple(range(10, 201, 10)))
        self.assertEqual(len(MA_PERIODS), 20)

    def test_ma10_uses_fixed_twenty_session_slope_window(self):
        dates = _sessions(30)
        signals = [{"symbol": "ABC", "signal_date": dates[-1],
                    "fill_date": "2024-02-14"}]
        annotated, counts = annotate_signals(
            signals, {"ABC": _bars(30, 1), "SPY": _bars(30, .25)}, 10)
        self.assertEqual(annotated[0]["relative_ma_period"], 10)
        self.assertEqual(annotated[0]["relative_ma_slope_sessions"], 20)
        self.assertTrue(annotated[0]["positive_relative_ma_slope"])
        self.assertEqual(counts["positive"], 1)

    def test_ma200_requires_two_hundred_twenty_common_sessions(self):
        dates = _sessions(219)
        signals = [{"symbol": "ABC", "signal_date": dates[-1],
                    "fill_date": "2024-12-01"}]
        annotated, counts = annotate_signals(
            signals, {"ABC": _bars(219, 1), "SPY": _bars(219, .25)}, 200)
        self.assertIsNone(annotated[0]["positive_relative_ma_slope"])
        self.assertEqual(counts["insufficient_ticker_history"], 1)

    def test_positive_selector_excludes_fail_and_missing(self):
        rows = [{"positive_relative_ma_slope": True},
                {"positive_relative_ma_slope": False},
                {"positive_relative_ma_slope": None}]
        selected = select_positive(rows)
        self.assertEqual(selected, [rows[0]])
        self.assertIsNot(selected[0], rows[0])

    def test_cohort_difference_uses_matched_baseline_trades(self):
        signals = [
            {"symbol": "A", "signal_date": "d0", "fill_date": "d1",
             "positive_relative_ma_slope": True},
            {"symbol": "B", "signal_date": "d0", "fill_date": "d1",
             "positive_relative_ma_slope": False},
        ]
        trades = [
            {"symbol": "A", "signal_date": "d0", "entry_date": "d1",
             "net_excess_vs_spy_pct": 3},
            {"symbol": "B", "signal_date": "d0", "entry_date": "d1",
             "net_excess_vs_spy_pct": -2},
        ]
        result = _cohort_mean_excess(trades, signals)
        self.assertEqual(result["qualifying_minus_rejected_mean_excess_pct_points"], 5)

    def test_selection_requires_qualified_and_breaks_ties_shorter(self):
        cells = [
            {"ma_period": 40, "qualified": True, "trades": 20,
             "exposure_matched_excess_cagr_lift_pct_points": 1.5},
            {"ma_period": 20, "qualified": True, "trades": 20,
             "exposure_matched_excess_cagr_lift_pct_points": 1.5},
            {"ma_period": 10, "qualified": False, "trades": 30,
             "exposure_matched_excess_cagr_lift_pct_points": 9.0},
        ]
        qualified, selected, diagnostic = select_grid_candidates(cells)
        self.assertEqual([row["ma_period"] for row in qualified], [20, 40])
        self.assertEqual(selected, 20)
        self.assertEqual(diagnostic["ma_period"], 10)

    def test_no_qualified_cell_keeps_selection_empty(self):
        cells = [{"ma_period": 10, "qualified": False, "trades": 25,
                  "exposure_matched_excess_cagr_lift_pct_points": .5}]
        qualified, selected, diagnostic = select_grid_candidates(cells)
        self.assertEqual(qualified, [])
        self.assertIsNone(selected)
        self.assertEqual(diagnostic["ma_period"], 10)


if __name__ == "__main__":
    unittest.main()
