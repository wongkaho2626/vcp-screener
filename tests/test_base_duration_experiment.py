"""Synthetic tests for the base-duration (maturity) experiment.

Covers the pure join/annotation logic only; no file I/O. Shared stats helpers
are covered in test_breakout_gap_experiment.py.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from base_duration_experiment import annotate_duration, build_pattern_index


def make_detection(symbol, as_of, duration):
    return {
        "symbol": symbol,
        "as_of_date": as_of,
        "vcp_pattern": {"pattern_duration_days": duration},
    }


def make_trade(symbol, as_of, excess=1.0):
    return {
        "symbol": symbol,
        "as_of_date": as_of,
        "entry_date": as_of,
        "excess_vs_spy_pct": excess,
    }


class BuildPatternIndexTest(unittest.TestCase):
    def test_indexes_by_symbol_and_as_of(self):
        index = build_pattern_index(
            {"AAA": [make_detection("AAA", "2020-03-02", 42)]})
        self.assertEqual(index[("AAA", "2020-03-02")]["pattern_duration_days"], 42)


class AnnotateDurationTest(unittest.TestCase):
    def setUp(self):
        self.index = build_pattern_index({
            "AAA": [make_detection("AAA", "2020-03-02", 42)],
            "BBB": [make_detection("BBB", "2020-03-02", 20)],
            "CCC": [make_detection("CCC", "2020-03-02", 0)],
        })

    def test_groups_by_threshold(self):
        out, skipped = annotate_duration(
            [make_trade("AAA", "2020-03-02"), make_trade("BBB", "2020-03-02")],
            self.index, threshold_days=35)
        by_sym = {t["symbol"]: t for t in out}
        self.assertEqual(by_sym["AAA"]["duration_group"], "mature")
        self.assertEqual(by_sym["AAA"]["pattern_duration_days"], 42)
        self.assertEqual(by_sym["BBB"]["duration_group"], "short")
        self.assertEqual(skipped, 0)

    def test_boundary_exactly_at_threshold_is_mature(self):
        index = build_pattern_index(
            {"EEE": [make_detection("EEE", "2020-03-02", 35)]})
        out, _ = annotate_duration(
            [make_trade("EEE", "2020-03-02")], index, threshold_days=35)
        self.assertEqual(out[0]["duration_group"], "mature")

    def test_skips_missing_join(self):
        out, skipped = annotate_duration(
            [make_trade("ZZZ", "2020-03-02")], self.index, threshold_days=35)
        self.assertEqual(out, [])
        self.assertEqual(skipped, 1)

    def test_skips_nonpositive_duration(self):
        out, skipped = annotate_duration(
            [make_trade("CCC", "2020-03-02")], self.index, threshold_days=35)
        self.assertEqual(out, [])
        self.assertEqual(skipped, 1)

    def test_inputs_not_mutated(self):
        trades = [make_trade("AAA", "2020-03-02")]
        annotate_duration(trades, self.index, threshold_days=35)
        self.assertNotIn("duration_group", trades[0])


if __name__ == "__main__":
    unittest.main()
