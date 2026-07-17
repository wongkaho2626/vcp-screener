"""Synthetic-trade tests for the detection-to-entry latency experiment.

Covers the pure annotation logic only; no file I/O. Shared stats helpers
(welch_t, fold_split, trim_top) are covered in test_breakout_gap_experiment.py.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from latency_experiment import annotate_latency


def make_trade(as_of, entry, excess=1.0):
    return {
        "symbol": "TEST",
        "as_of_date": as_of,
        "entry_date": entry,
        "excess_vs_spy_pct": excess,
    }


class AnnotateLatencyTest(unittest.TestCase):
    def test_computes_calendar_day_latency(self):
        out = annotate_latency([make_trade("2020-03-02", "2020-03-05")],
                               threshold_days=7)
        self.assertEqual(out[0]["latency_days"], 3)

    def test_boundary_exactly_at_threshold_is_fresh(self):
        out = annotate_latency([make_trade("2020-03-02", "2020-03-09")],
                               threshold_days=7)
        self.assertEqual(out[0]["latency_group"], "fresh")

    def test_above_threshold_is_stale(self):
        out = annotate_latency([make_trade("2020-03-02", "2020-03-10")],
                               threshold_days=7)
        self.assertEqual(out[0]["latency_group"], "stale")

    def test_same_day_entry_is_fresh(self):
        out = annotate_latency([make_trade("2020-03-02", "2020-03-02")],
                               threshold_days=7)
        self.assertEqual(out[0]["latency_days"], 0)
        self.assertEqual(out[0]["latency_group"], "fresh")

    def test_negative_latency_dropped_as_data_error(self):
        out = annotate_latency([make_trade("2020-03-05", "2020-03-02")],
                               threshold_days=7)
        self.assertEqual(out, [])

    def test_crosses_month_boundary(self):
        out = annotate_latency([make_trade("2020-02-25", "2020-03-06")],
                               threshold_days=7)
        self.assertEqual(out[0]["latency_days"], 10)
        self.assertEqual(out[0]["latency_group"], "stale")

    def test_inputs_not_mutated(self):
        trades = [make_trade("2020-03-02", "2020-03-05")]
        annotate_latency(trades, threshold_days=7)
        self.assertNotIn("latency_days", trades[0])
        self.assertNotIn("latency_group", trades[0])


if __name__ == "__main__":
    unittest.main()
