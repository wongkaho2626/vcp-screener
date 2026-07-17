"""Synthetic-bars tests for the breakout-day opening-gap experiment.

Covers the pure decision/statistics functions only; no CSV or network I/O.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from breakout_gap_experiment import (
    classify_trades,
    fold_split,
    gap_pct_for_entry,
    trim_top,
    welch_t,
)


def make_bars(spec, start_day=2):
    """spec: list of (open, close) tuples mapped onto consecutive Jan 2020 dates."""
    bars = []
    for i, (open_, close) in enumerate(spec):
        bars.append({
            "date": f"2020-01-{start_day + i:02d}",
            "open": float(open_),
            "high": float(max(open_, close)),
            "low": float(min(open_, close)),
            "close": float(close),
            "volume": 1_000_000,
        })
    return bars


def make_trade(entry_date, excess, symbol="TEST"):
    return {"symbol": symbol, "entry_date": entry_date, "excess_vs_spy_pct": excess}


class GapPctTest(unittest.TestCase):
    def test_computes_gap_vs_prior_close(self):
        bars = make_bars([(10.0, 10.0), (10.2, 10.5)])  # 01-02 close 10, 01-03 open 10.2
        self.assertAlmostEqual(gap_pct_for_entry(bars, "2020-01-03"), 2.0)

    def test_negative_gap(self):
        bars = make_bars([(10.0, 10.0), (9.9, 10.1)])
        self.assertAlmostEqual(gap_pct_for_entry(bars, "2020-01-03"), -1.0)

    def test_none_when_entry_bar_missing(self):
        bars = make_bars([(10.0, 10.0)])
        self.assertIsNone(gap_pct_for_entry(bars, "2020-01-03"))

    def test_none_when_no_prior_bar(self):
        bars = make_bars([(10.0, 10.0)])
        self.assertIsNone(gap_pct_for_entry(bars, "2020-01-02"))

    def test_no_lookahead_truncating_future_bars_changes_nothing(self):
        bars = make_bars([(10.0, 10.0), (10.2, 10.5), (11.0, 12.0), (13.0, 14.0)])
        full = gap_pct_for_entry(bars, "2020-01-03")
        truncated = gap_pct_for_entry(bars[:2], "2020-01-03")
        self.assertEqual(full, truncated)

    def test_uses_last_bar_strictly_before_entry_when_days_skip(self):
        bars = make_bars([(10.0, 10.0), (10.2, 10.5)])
        bars[1]["date"] = "2020-01-06"  # weekend skip
        self.assertAlmostEqual(gap_pct_for_entry(bars, "2020-01-06"), 2.0)


class ClassifyTradesTest(unittest.TestCase):
    def test_splits_by_threshold_without_mutating_inputs(self):
        prices = {"AAA": make_bars([(10.0, 10.0), (10.2, 10.5)]),
                  "BBB": make_bars([(20.0, 20.0), (20.05, 21.0)])}
        trades = [make_trade("2020-01-03", 5.0, "AAA"),
                  make_trade("2020-01-03", -2.0, "BBB")]
        classified, skipped = classify_trades(trades, prices, threshold_pct=1.0)
        self.assertEqual(skipped, 0)
        self.assertEqual([t["gap_group"] for t in classified], ["gap", "no_gap"])
        self.assertNotIn("gap_group", trades[0])  # originals untouched

    def test_boundary_exactly_at_threshold_is_gap(self):
        prices = {"AAA": make_bars([(10.0, 10.0), (10.1, 10.5)])}
        classified, _ = classify_trades(
            [make_trade("2020-01-03", 1.0, "AAA")], prices, threshold_pct=1.0)
        self.assertEqual(classified[0]["gap_group"], "gap")

    def test_skips_trades_with_missing_price_data(self):
        classified, skipped = classify_trades(
            [make_trade("2020-01-03", 1.0, "ZZZ")], {}, threshold_pct=1.0)
        self.assertEqual(classified, [])
        self.assertEqual(skipped, 1)


class StatsTest(unittest.TestCase):
    def test_welch_t_zero_for_identical_groups(self):
        t, df = welch_t([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        self.assertAlmostEqual(t, 0.0)
        self.assertGreater(df, 0)

    def test_welch_t_sign_follows_first_group(self):
        t, _ = welch_t([5.0, 6.0, 7.0], [1.0, 2.0, 3.0])
        self.assertGreater(t, 0)

    def test_welch_t_handles_tiny_groups(self):
        t, df = welch_t([1.0], [1.0, 2.0])
        self.assertTrue(t is None and df is None)

    def test_fold_split_by_entry_date(self):
        trades = [make_trade("2019-05-01", 1.0), make_trade("2021-01-04", 2.0)]
        early, late = fold_split(trades, boundary="2021-01-01")
        self.assertEqual(len(early), 1)
        self.assertEqual(len(late), 1)
        self.assertEqual(early[0]["entry_date"], "2019-05-01")

    def test_trim_top_drops_highest_excess(self):
        trades = [make_trade("2020-01-03", v) for v in (9.0, 1.0, 5.0, -3.0)]
        trimmed = trim_top(trades, 2)
        self.assertEqual(sorted(t["excess_vs_spy_pct"] for t in trimmed), [-3.0, 1.0])
        self.assertEqual(len(trades), 4)  # input not mutated


if __name__ == "__main__":
    unittest.main()
