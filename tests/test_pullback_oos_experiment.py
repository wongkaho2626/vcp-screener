"""Unit tests for pullback_oos_experiment pure logic (synthetic bars only).

Covers: fold assignment boundaries, trim immutability, paired-record
construction (both legs, extension skip, non-breakout skip), and the
no-lookahead contract (truncating bars after the exits changes nothing).
"""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from pullback_oos_experiment import (
    aggregate_records,
    assign_fold,
    evaluate_detection,
    filter_member_detections,
    summarize_values,
    trim_top,
)


def make_bars(closes, lows=None):
    lows = lows or closes
    return [
        {"date": f"d{i:03d}", "open": c, "high": c, "low": lo, "close": c,
         "volume": 1000}
        for i, (c, lo) in enumerate(zip(closes, lows))
    ]


def make_detection(exit_date="d002", exit_price=101.0, pivot=100.0, stop=92.0,
                   outcome="breakout"):
    return {
        "forward_outcome": {
            "outcome_type": outcome,
            "exit_date": exit_date,
            "exit_price": exit_price,
            "pivot_price": pivot,
            "stop_price": stop,
        }
    }


def zero_spy(entry_date, exit_date):
    return 0.0


HAPPY_CLOSES = [95, 96, 101, 104, 105, 106, 108, 110, 111]
HAPPY_LOWS = [94, 95, 100, 103, 102, 105, 107, 109, 110]


def happy_record(bars=None):
    bars = bars if bars is not None else make_bars(HAPPY_CLOSES, HAPPY_LOWS)
    idx_map = {b["date"]: i for i, b in enumerate(bars)}
    return evaluate_detection(
        bars, idx_map, make_detection(), zero_spy,
        ma_period=2, window=15, max_hold_bars=3,
    )


class TestAssignFold:
    def test_boundaries(self):
        assert assign_fold("2006-01-01") == "2006-2010"
        assert assign_fold("2010-12-31") == "2006-2010"
        assert assign_fold("2011-01-01") == "2011-2015"
        assert assign_fold("2015-12-31") == "2011-2015"

    def test_outside_range_is_none(self):
        assert assign_fold("2005-12-30") is None
        assert assign_fold("2016-01-04") is None
        assert assign_fold(None) is None


class TestTrimTop:
    def test_drops_k_largest(self):
        vals = [5.0, -2.0, 9.0, 1.0, 3.0]
        assert sorted(trim_top(vals, 2)) == [-2.0, 1.0, 3.0]

    def test_does_not_mutate_input(self):
        vals = [5.0, -2.0, 9.0]
        _ = trim_top(vals, 1)
        assert vals == [5.0, -2.0, 9.0]

    def test_k_zero_returns_copy(self):
        vals = [1.0, 2.0]
        out = trim_top(vals, 0)
        assert out == vals and out is not vals


class TestEvaluateDetection:
    def test_happy_path_pairs_both_legs(self):
        rec = happy_record()
        assert rec["status"] == "paired"
        assert rec["pair_date"] == "d002"
        # breakout: entry d002 @101, 3-bar timeout at d005 close 106
        assert rec["bo_exc"] == pytest.approx((106 / 101 - 1) * 100, abs=1e-6)
        # pullback: MA2 touch-and-hold at d004 @105, timeout at d007 close 110
        assert rec["pb_exc"] == pytest.approx((110 / 105 - 1) * 100, abs=1e-6)
        assert rec["delta"] == pytest.approx(
            (110 / 105 - 1) * 100 - (106 / 101 - 1) * 100, abs=1e-6
        )

    def test_extension_skip_leaves_pullback_only(self):
        bars = make_bars(HAPPY_CLOSES, HAPPY_LOWS)
        idx_map = {b["date"]: i for i, b in enumerate(bars)}
        det = make_detection(exit_price=106.0)  # 6% > 5% max extension
        rec = evaluate_detection(bars, idx_map, det, zero_spy,
                                 ma_period=2, window=15, max_hold_bars=3)
        assert rec["status"] == "pb_only"
        assert rec["bo_exc"] is None
        assert rec["delta"] is None
        assert rec["pb_exc"] is not None

    def test_non_breakout_outcome_returns_none(self):
        bars = make_bars(HAPPY_CLOSES, HAPPY_LOWS)
        idx_map = {b["date"]: i for i, b in enumerate(bars)}
        det = make_detection(outcome="stop_hit")
        assert evaluate_detection(bars, idx_map, det, zero_spy,
                                  ma_period=2, window=15, max_hold_bars=3) is None

    def test_missing_breakout_date_returns_none(self):
        bars = make_bars(HAPPY_CLOSES, HAPPY_LOWS)
        idx_map = {b["date"]: i for i, b in enumerate(bars)}
        det = make_detection(exit_date="d999")
        assert evaluate_detection(bars, idx_map, det, zero_spy,
                                  ma_period=2, window=15, max_hold_bars=3) is None

    def test_no_lookahead_truncation_invariance(self):
        # Both exits land by d007; bars after that must not matter.
        full = happy_record()
        truncated = happy_record(make_bars(HAPPY_CLOSES[:8], HAPPY_LOWS[:8]))
        assert truncated == full

    def test_spy_excess_subtracted(self):
        bars = make_bars(HAPPY_CLOSES, HAPPY_LOWS)
        idx_map = {b["date"]: i for i, b in enumerate(bars)}
        rec = evaluate_detection(bars, idx_map, make_detection(),
                                 lambda e, x: 1.0,
                                 ma_period=2, window=15, max_hold_bars=3)
        assert rec["bo_exc"] == pytest.approx((106 / 101 - 1) * 100 - 1.0, abs=1e-6)


class TestFilterMemberDetections:
    INTERVALS = {"AAA": [("2006-01-01", "2010-06-30")],
                 "BBB": [("2004-01-01", "9999-12-31")]}

    def test_drops_detections_outside_membership(self):
        dets = {
            "AAA": [{"as_of_date": "2009-05-01"}, {"as_of_date": "2011-01-05"}],
            "BBB": [{"as_of_date": "2012-03-01"}],
            "CCC": [{"as_of_date": "2010-01-01"}],
        }
        kept, dropped = filter_member_detections(dets, self.INTERVALS)
        assert [d["as_of_date"] for d in kept["AAA"]] == ["2009-05-01"]
        assert len(kept["BBB"]) == 1
        assert "CCC" not in kept
        assert dropped == 2

    def test_does_not_mutate_input(self):
        dets = {"AAA": [{"as_of_date": "2011-01-05"}]}
        filter_member_detections(dets, self.INTERVALS)
        assert dets == {"AAA": [{"as_of_date": "2011-01-05"}]}

    def test_none_intervals_passthrough(self):
        dets = {"CCC": [{"as_of_date": "2010-01-01"}]}
        kept, dropped = filter_member_detections(dets, None)
        assert kept == dets and dropped == 0


class TestSummarizeAndAggregate:
    def test_summarize_small_sample_is_none(self):
        assert summarize_values([1.0] * 5) is None

    def test_summarize_basic_fields(self):
        s = summarize_values([1.0, 2.0, 3.0, -1.0, 2.0, 5.0])
        assert s["n"] == 6
        assert s["mean"] == pytest.approx(2.0)
        assert s["win"] == pytest.approx(5 / 6 * 100, abs=0.1)

    def test_aggregate_folds_by_pair_date(self):
        records = [
            {"pair_date": "2007-05-01", "status": "paired",
             "bo_exc": 1.0, "pb_exc": 2.0, "delta": 1.0},
            {"pair_date": "2012-05-01", "status": "paired",
             "bo_exc": 1.0, "pb_exc": 0.0, "delta": -1.0},
        ] * 6
        agg = aggregate_records(records)
        assert agg["pooled"]["deltas"]["n"] == 12
        assert agg["folds"]["2006-2010"]["deltas"]["n"] == 6
        assert agg["folds"]["2006-2010"]["deltas"]["mean"] == pytest.approx(1.0)
        assert agg["folds"]["2011-2015"]["deltas"]["mean"] == pytest.approx(-1.0)
