"""Unit tests for exit_stress_experiments pure walkers (strict two-leg exit
and asymmetric cull/ride walk). Synthetic bars; small MA periods."""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from exit_stress_experiments import momentum_walk, strict_exit


def make_bars(closes):
    return [{"date": f"d{i:03d}", "close": c} for i, c in enumerate(closes)]


class TestStrictExit:
    """stop full-exit / +PT% scale out 50% / MA-break sells the rest."""

    def test_target_then_ma_break_two_legs(self):
        # Entry 10 at idx 3 (MA3 for testability). j=4 close 13 >= target 12
        # → leg A +30%. j=6 close 9 < MA3(13,12,9)=11.33 → leg B −10%.
        bars = make_bars([10, 10, 10, 10, 13, 12, 9])
        legs, path = strict_exit(bars, 3, entry=10.0, stop=8.0, pt_pct=20.0, ma_period=3)
        assert path == "target+ma"
        assert legs == [
            (0.5, 4, pytest.approx(30.0)),
            (0.5, 6, pytest.approx(-10.0)),
        ]

    def test_stop_before_target_exits_full(self):
        # Bar 4 holds above its MA3 (10.2 >= 10.07); bar 5 gaps below the stop.
        bars = make_bars([10, 10, 10, 10, 10.2, 7.5, 13])
        legs, path = strict_exit(bars, 3, entry=10.0, stop=8.0, pt_pct=20.0, ma_period=3)
        assert path == "stop-full"
        assert legs == [(1.0, 5, pytest.approx(-25.0))]

    def test_ma_break_without_target_exits_full(self):
        # Never reaches +20%; j=6 close 9 breaks MA3.
        bars = make_bars([10, 10, 10, 10, 11, 10.5, 9])
        legs, path = strict_exit(bars, 3, entry=10.0, stop=8.0, pt_pct=20.0, ma_period=3)
        assert path == "ma-full"
        assert legs == [(1.0, 6, pytest.approx(-10.0))]

    def test_data_end_marks_remaining_leg_open(self):
        bars = make_bars([10, 10, 10, 10, 13, 14])
        legs, path = strict_exit(bars, 3, entry=10.0, stop=8.0, pt_pct=20.0, ma_period=3)
        assert path == "target+open"
        assert legs[0] == (0.5, 4, pytest.approx(30.0))
        assert legs[1] == (0.5, 5, pytest.approx(40.0))


class TestMomentumWalk:
    """Hard stop always; optional laggard cull and winner ride."""

    def test_cull_fires_on_laggard_at_cull_day(self):
        bars = make_bars([10] + [9.9] * 12)
        j, reason = momentum_walk(
            bars, 0, entry=10.0, stop=8.0,
            cfg={"cull_day": 10, "cull_min": 0.0}, base_hold=60,
        )
        assert (j, reason) == (10, "cull")

    def test_strong_trade_escapes_cull_and_times_out(self):
        bars = make_bars([10] + [11] * 70)
        j, reason = momentum_walk(
            bars, 0, entry=10.0, stop=8.0,
            cfg={"cull_day": 10, "cull_min": 0.0}, base_hold=60,
        )
        assert (j, reason) == (60, "timeout")

    def test_qualified_winner_rides_to_extended_timeout(self):
        # +20% on day 2 (within window) → extended hold applies.
        bars = make_bars([10, 11, 12.5] + [12.6] * 100)
        j, reason = momentum_walk(
            bars, 0, entry=10.0, stop=8.0,
            cfg={"ride_trigger": 20.0, "ride_window": 20, "ride_hold": 80},
            base_hold=60,
        )
        assert (j, reason) == (80, "ride_timeout")

    def test_qualified_winner_trail_exit(self):
        # Qualifies at 12.5, runs to 14, then 10.4 < 14*(1-25%) = 10.5 → trail.
        bars = make_bars([10, 12.5, 14, 10.4, 10.4])
        j, reason = momentum_walk(
            bars, 0, entry=10.0, stop=8.0,
            cfg={"ride_trigger": 20.0, "ride_window": 20, "ride_hold": 80,
                 "ride_trail": 25.0},
            base_hold=60,
        )
        assert (j, reason) == (3, "ride_trail")

    def test_hard_stop_always_wins(self):
        bars = make_bars([10, 12.5, 7.9, 14])
        j, reason = momentum_walk(
            bars, 0, entry=10.0, stop=8.0,
            cfg={"ride_trigger": 20.0, "ride_window": 20, "ride_hold": 80},
            base_hold=60,
        )
        assert (j, reason) == (2, "stop")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
