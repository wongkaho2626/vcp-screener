"""Synthetic tests for the contraction-tightening sequence experiment.

Covers the pure join/annotation logic only; no file I/O. Shared stats helpers
(welch_t, fold_split, trim_top) are covered in test_breakout_gap_experiment.py.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from contraction_experiment import annotate_tightening, build_detection_index


def make_detection(symbol, as_of, depths):
    return {
        "symbol": symbol,
        "as_of_date": as_of,
        "vcp_pattern": {
            "contractions": [{"label": f"T{i+1}", "depth_pct": d}
                             for i, d in enumerate(depths)],
        },
    }


def make_trade(symbol, as_of, excess=1.0):
    return {
        "symbol": symbol,
        "as_of_date": as_of,
        "entry_date": as_of,
        "excess_vs_spy_pct": excess,
    }


class BuildDetectionIndexTest(unittest.TestCase):
    def test_indexes_by_symbol_and_as_of(self):
        index = build_detection_index(
            {"AAA": [make_detection("AAA", "2020-03-02", [20.0, 8.0])]})
        self.assertIn(("AAA", "2020-03-02"), index)


class AnnotateTighteningTest(unittest.TestCase):
    def setUp(self):
        self.index = build_detection_index({
            "AAA": [make_detection("AAA", "2020-03-02", [20.0, 8.0])],   # 0.4
            "BBB": [make_detection("BBB", "2020-03-02", [10.0, 9.0])],   # 0.9
            "CCC": [make_detection("CCC", "2020-03-02", [15.0])],        # <2
            "DDD": [make_detection("DDD", "2020-03-02", [0.0, 5.0])],    # bad first
        })

    def test_computes_ratio_and_groups(self):
        out, skipped = annotate_tightening(
            [make_trade("AAA", "2020-03-02"), make_trade("BBB", "2020-03-02")],
            self.index, threshold=0.5)
        by_sym = {t["symbol"]: t for t in out}
        self.assertAlmostEqual(by_sym["AAA"]["tightening_ratio"], 0.4)
        self.assertEqual(by_sym["AAA"]["tighten_group"], "tight")
        self.assertAlmostEqual(by_sym["BBB"]["tightening_ratio"], 0.9)
        self.assertEqual(by_sym["BBB"]["tighten_group"], "loose")
        self.assertEqual(skipped, 0)

    def test_boundary_exactly_at_threshold_is_tight(self):
        index = build_detection_index(
            {"EEE": [make_detection("EEE", "2020-03-02", [10.0, 5.0])]})
        out, _ = annotate_tightening(
            [make_trade("EEE", "2020-03-02")], index, threshold=0.5)
        self.assertEqual(out[0]["tighten_group"], "tight")

    def test_skips_missing_join(self):
        out, skipped = annotate_tightening(
            [make_trade("ZZZ", "2020-03-02")], self.index, threshold=0.5)
        self.assertEqual(out, [])
        self.assertEqual(skipped, 1)

    def test_skips_fewer_than_two_contractions(self):
        out, skipped = annotate_tightening(
            [make_trade("CCC", "2020-03-02")], self.index, threshold=0.5)
        self.assertEqual(out, [])
        self.assertEqual(skipped, 1)

    def test_skips_nonpositive_first_depth(self):
        out, skipped = annotate_tightening(
            [make_trade("DDD", "2020-03-02")], self.index, threshold=0.5)
        self.assertEqual(out, [])
        self.assertEqual(skipped, 1)

    def test_inputs_not_mutated(self):
        trades = [make_trade("AAA", "2020-03-02")]
        annotate_tightening(trades, self.index, threshold=0.5)
        self.assertNotIn("tightening_ratio", trades[0])


if __name__ == "__main__":
    unittest.main()
