"""Synthetic-trade tests for the VCP signal-crowding experiment.

Covers the pure crowding-annotation logic only; no file I/O. The shared stats
helpers (welch_t, fold_split, trim_top) are covered in
test_breakout_gap_experiment.py and are reused, not retested.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from crowding_experiment import annotate_crowding


def make_trade(as_of, excess=1.0, symbol="TEST"):
    return {
        "symbol": symbol,
        "as_of_date": as_of,
        "entry_date": as_of,  # entry offset is irrelevant to crowding
        "excess_vs_spy_pct": excess,
    }


class AnnotateCrowdingTest(unittest.TestCase):
    def test_counts_other_trades_in_trailing_window(self):
        trades = [make_trade("2020-03-02"), make_trade("2020-03-05"),
                  make_trade("2020-03-10")]
        out = annotate_crowding(trades, window_days=10, min_prior=2)
        by_date = {t["as_of_date"]: t for t in out}
        self.assertEqual(by_date["2020-03-02"]["n_prior"], 0)
        self.assertEqual(by_date["2020-03-05"]["n_prior"], 1)
        self.assertEqual(by_date["2020-03-10"]["n_prior"], 2)

    def test_excludes_self_but_counts_same_day_others(self):
        trades = [make_trade("2020-03-02", symbol="A"),
                  make_trade("2020-03-02", symbol="B")]
        out = annotate_crowding(trades, window_days=10, min_prior=2)
        self.assertEqual([t["n_prior"] for t in out], [1, 1])

    def test_window_boundary_inclusive_at_exactly_window_days(self):
        trades = [make_trade("2020-03-01"), make_trade("2020-03-11")]
        out = annotate_crowding(trades, window_days=10, min_prior=2)
        self.assertEqual(out[1]["n_prior"], 1)  # 10 days back, included

    def test_window_boundary_excludes_older_than_window(self):
        trades = [make_trade("2020-03-01"), make_trade("2020-03-12")]
        out = annotate_crowding(trades, window_days=10, min_prior=2)
        self.assertEqual(out[1]["n_prior"], 0)  # 11 days back, excluded

    def test_only_trailing_never_future(self):
        trades = [make_trade("2020-03-05"), make_trade("2020-03-06")]
        out = annotate_crowding(trades, window_days=10, min_prior=2)
        self.assertEqual(out[0]["n_prior"], 0)  # 03-06 is the future

    def test_group_threshold_boundary(self):
        trades = [make_trade("2020-03-02"), make_trade("2020-03-03"),
                  make_trade("2020-03-04")]
        out = annotate_crowding(trades, window_days=10, min_prior=2)
        by_date = {t["as_of_date"]: t for t in out}
        self.assertEqual(by_date["2020-03-04"]["crowd_group"], "crowded")  # n=2
        self.assertEqual(by_date["2020-03-03"]["crowd_group"], "quiet")    # n=1

    def test_inputs_not_mutated(self):
        trades = [make_trade("2020-03-02")]
        annotate_crowding(trades, window_days=10, min_prior=2)
        self.assertNotIn("n_prior", trades[0])
        self.assertNotIn("crowd_group", trades[0])

    def test_unsorted_input_handled(self):
        trades = [make_trade("2020-03-10"), make_trade("2020-03-02"),
                  make_trade("2020-03-05")]
        out = annotate_crowding(trades, window_days=10, min_prior=2)
        by_date = {t["as_of_date"]: t for t in out}
        self.assertEqual(by_date["2020-03-10"]["n_prior"], 2)


if __name__ == "__main__":
    unittest.main()
