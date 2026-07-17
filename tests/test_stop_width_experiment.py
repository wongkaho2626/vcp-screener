"""Synthetic-trade tests for the initial stop-width experiment.

Covers the pure annotation logic only; no file I/O. Shared stats helpers
(welch_t, fold_split, trim_top) are covered in test_breakout_gap_experiment.py.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from stop_width_experiment import annotate_stop_width


def make_trade(entry, stop, excess=1.0, exit_reason="timeout"):
    return {
        "symbol": "TEST",
        "entry_date": "2020-03-02",
        "entry_price": entry,
        "stop_price": stop,
        "excess_vs_spy_pct": excess,
        "exit_reason": exit_reason,
    }


class AnnotateStopWidthTest(unittest.TestCase):
    def test_computes_risk_pct(self):
        out = annotate_stop_width([make_trade(100.0, 94.0)], threshold_pct=6.0)
        self.assertAlmostEqual(out[0]["risk_pct"], 6.0)

    def test_boundary_exactly_at_threshold_is_tight(self):
        out = annotate_stop_width([make_trade(100.0, 94.0)], threshold_pct=6.0)
        self.assertEqual(out[0]["width_group"], "tight")

    def test_above_threshold_is_wide(self):
        out = annotate_stop_width([make_trade(100.0, 93.9)], threshold_pct=6.0)
        self.assertEqual(out[0]["width_group"], "wide")

    def test_tighter_stop_is_tight(self):
        out = annotate_stop_width([make_trade(100.0, 97.0)], threshold_pct=6.0)
        self.assertEqual(out[0]["width_group"], "tight")
        self.assertAlmostEqual(out[0]["risk_pct"], 3.0)

    def test_skips_nonpositive_or_inverted_prices(self):
        bad = [make_trade(0.0, -1.0), make_trade(100.0, 101.0)]
        out = annotate_stop_width(bad, threshold_pct=6.0)
        self.assertEqual(out, [])

    def test_inputs_not_mutated(self):
        trades = [make_trade(100.0, 94.0)]
        annotate_stop_width(trades, threshold_pct=6.0)
        self.assertNotIn("risk_pct", trades[0])
        self.assertNotIn("width_group", trades[0])


if __name__ == "__main__":
    unittest.main()
