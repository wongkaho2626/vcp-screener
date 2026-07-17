"""Unit tests for peg_experiment.compute_peg / annotate_peg (pure functions).
Synthetic quarterly earnings events only — no network, no real data."""

import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from peg_experiment import annotate_peg, compute_peg


def make_events(eps_list, start_year=2018):
    """Quarterly events (Feb/May/Aug/Nov 15th), oldest first."""
    months = [2, 5, 8, 11]
    events = []
    for i, eps in enumerate(eps_list):
        year = start_year + i // 4
        month = months[i % 4]
        events.append(
            {"event_date": f"{year:04d}-{month:02d}-15", "reported_eps": float(eps)}
        )
    return events


class TestComputePeg:
    def test_clean_history_computes_pe_growth_and_peg(self):
        # prior TTM = 4 * 0.8 = 3.2, recent TTM = 4 * 1.0 = 4.0 → growth 25%
        # price 100 → PE 25 → PEG 1.0
        events = make_events([0.8] * 4 + [1.0] * 4)
        out = compute_peg(100.0, events, "2020-01-02")
        assert out["status"] == "ok"
        assert out["ttm_eps"] == 4.0
        assert round(out["growth_pct"], 6) == 25.0
        assert round(out["pe"], 6) == 25.0
        assert round(out["peg"], 6) == 1.0

    def test_events_after_asof_are_ignored(self):
        # A blowout quarter announced after as-of must not leak in (PIT).
        events = make_events([0.8] * 4 + [1.0] * 4 + [9.9])
        out = compute_peg(100.0, events, "2020-01-02")
        assert out["status"] == "ok"
        assert out["ttm_eps"] == 4.0

    def test_fewer_than_eight_quarters_is_insufficient(self):
        events = make_events([1.0] * 7)
        out = compute_peg(100.0, events, "2020-01-02")
        assert out["status"] == "insufficient_history"
        assert out["peg"] is None

    def test_gap_in_recent_quarters_is_stale(self):
        # 8 events exist but the newest 4 end long before as-of (missing
        # quarters must not silently widen the TTM window).
        events = make_events([1.0] * 8, start_year=2016)
        out = compute_peg(100.0, events, "2020-06-01")
        assert out["status"] == "stale_history"
        assert out["peg"] is None

    def test_nonpositive_ttm_has_no_peg(self):
        events = make_events([1.0] * 4 + [-2.0] * 4)
        out = compute_peg(100.0, events, "2020-01-02")
        assert out["status"] == "nonpositive_ttm"
        assert out["peg"] is None

    def test_nonpositive_growth_has_no_peg(self):
        # Decelerating earnings: TTM 3.2 vs prior 4.0 → growth < 0 → PEG undefined.
        events = make_events([1.0] * 4 + [0.8] * 4)
        out = compute_peg(100.0, events, "2020-01-02")
        assert out["status"] == "nonpositive_growth"
        assert out["peg"] is None
        assert round(out["growth_pct"], 6) == -20.0


class TestAnnotatePeg:
    def test_attaches_fields_without_mutating_input(self):
        events = {"AAA": make_events([0.8] * 4 + [1.0] * 4)}
        trades = [
            {"symbol": "AAA", "as_of_date": "2020-01-02", "entry_price": 100.0},
            {"symbol": "ZZZ", "as_of_date": "2020-01-02", "entry_price": 50.0},
        ]
        out = annotate_peg(trades, events)
        assert out[0]["peg"] == 1.0 and out[0]["peg_status"] == "ok"
        assert out[1]["peg"] is None and out[1]["peg_status"] == "no_earnings_data"
        assert "peg" not in trades[0]  # immutability
