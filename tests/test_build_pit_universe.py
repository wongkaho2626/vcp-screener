"""Unit tests for build_pit_universe pure logic (synthetic rows only).

Covers: membership-window trimming with buffers, the scale-break corruption
screen, and the bars-inside-membership floor.
"""

import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from build_pit_universe import (
    allowed_ranges,
    bars_inside_membership,
    find_scale_break,
    in_ranges,
)

MEM = {"AAA": [("2008-06-01", "2012-06-01")],
       "BBB": [("1996-01-02", "9999-12-31")]}


def row(date, adj):
    return ["T", date, adj, adj, adj, adj, adj, 100]


class TestAllowedRanges:
    def test_buffers_applied(self):
        rngs = allowed_ranges("AAA", MEM, "2006-01-01", "2015-12-31")
        assert rngs == [("2006-06-02", "2012-10-09")]  # -730d / +130d

    def test_open_ended_membership_clipped_to_window_end(self):
        rngs = allowed_ranges("BBB", MEM, "2006-01-01", "2015-12-31")
        assert rngs[0][1] == "2017-05-10"  # 2016-12-31 + 130d

    def test_no_overlap_returns_empty(self):
        assert allowed_ranges("AAA", MEM, "2013-01-01", "2015-12-31") == []

    def test_in_ranges(self):
        rngs = [("2010-01-01", "2010-12-31")]
        assert in_ranges("2010-06-15", rngs)
        assert not in_ranges("2011-01-01", rngs)


class TestScaleBreakScreen:
    def test_flags_10x_jump(self):
        rows = [row("2010-01-04", 10.0), row("2010-01-05", 10.5),
                row("2010-01-06", 105.0)]
        assert find_scale_break(rows) == "scale-break@2010-01-06"

    def test_allows_crisis_bounce_under_threshold(self):
        rows = [row("2009-03-09", 4.0), row("2009-03-10", 8.0)]  # +100% < 150%
        assert find_scale_break(rows) is None

    def test_flags_nonpositive(self):
        rows = [row("2010-01-04", 10.0), row("2010-01-05", 0.0)]
        assert find_scale_break(rows) == "nonpositive"


class TestBarsInsideMembership:
    def test_counts_only_membership_days(self):
        rows = [row("2007-06-01", 1), row("2009-06-01", 1), row("2013-06-01", 1)]
        n = bars_inside_membership("AAA", rows, MEM, "2006-01-01", "2015-12-31")
        assert n == 1  # only 2009-06-01 falls inside 2008-2012 membership
