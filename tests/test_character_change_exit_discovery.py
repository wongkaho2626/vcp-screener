from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from character_change_exit_discovery import (
    attach_character_change_exits,
    character_change_exit,
    is_abnormal_down_day,
    is_strong_state,
    simple_moving_average,
)


def _bar(index: int, close: float, *, open_price: float | None = None,
         high: float | None = None, low: float | None = None) -> dict:
    return {
        "date": f"2020-02-{index + 1:02d}",
        "open": close if open_price is None else open_price,
        "high": close + 1 if high is None else high,
        "low": close - 5 if low is None else low,
        "close": close,
        "volume": 1_000_000,
    }


def _signal(fill_idx: int = 20) -> dict:
    return {
        "symbol": "AAA", "sector": "Tech", "signal_date": "2020-02-20",
        "fill_date": "2020-02-21", "fill_idx": fill_idx,
        "edge_rank": 75.0, "pattern_stop": 50.0, "pivot": 100.0,
    }


def test_simple_moving_average_is_inclusive_and_requires_full_history() -> None:
    bars = [_bar(i, float(i + 1)) for i in range(4)]
    assert simple_moving_average(bars, 1, 3) is None
    assert simple_moving_average(bars, 2, 3) == 2.0


def test_strong_state_uses_only_completed_contemporaneous_averages() -> None:
    bars = [_bar(i, 100.0 + i) for i in range(30)]
    assert is_strong_state(bars, 28)
    initial = is_strong_state(bars, 28)
    extended = bars + [_bar(30, 1.0)]
    assert is_strong_state(extended, 28) == initial


def test_abnormal_day_matches_frozen_gap_and_close_thresholds() -> None:
    bars = [_bar(0, 100.0), _bar(1, 99.0, open_price=94.0)]
    assert is_abnormal_down_day(bars, 1)
    bars[1] = _bar(1, 84.0, open_price=100.0)
    assert is_abnormal_down_day(bars, 1)
    bars[1] = _bar(1, 95.0, open_price=95.0)
    assert not is_abnormal_down_day(bars, 1)


def test_failed_recovery_schedules_following_open() -> None:
    bars = [_bar(i, 100.0 + i) for i in range(30)]
    for index in range(25, 30):
        bars[index]["low"] = 115.0
    bars.append(_bar(30, 119.0, open_price=129.0, high=120.0, low=117.0))
    # Frozen lower SMA edge on the damage bar is below 121 and above this close.
    bars.append(_bar(31, 119.5, open_price=119.0, high=121.0, low=118.0))
    bars.append(_bar(32, 120.0))
    activation = character_change_exit(_signal(), bars)
    assert activation == {
        "signal_idx": 31,
        "model_exit_idx": 32,
        "reason": "failed_ma_cluster_recovery",
    }


def test_abnormal_post_arm_day_schedules_following_open() -> None:
    bars = [_bar(i, 100.0 + i) for i in range(30)]
    bars[29] = _bar(29, 127.0, open_price=120.0, high=128.0, low=119.0)
    bars.append(_bar(30, 128.0))
    activation = character_change_exit(_signal(), bars)
    assert activation is not None
    assert activation["signal_idx"] == 29
    assert activation["model_exit_idx"] == 30
    assert activation["reason"] == "abnormal_down_day"


def test_existing_hard_stop_prevents_later_custom_activation() -> None:
    bars = [_bar(i, 100.0 + i) for i in range(30)]
    bars[22] = _bar(22, 122.0, low=100.0)
    bars[24] = _bar(24, 123.0, open_price=114.0, low=113.0)
    assert character_change_exit(_signal(), bars) is None


def test_attached_exit_is_not_revised_by_future_bars() -> None:
    bars = [_bar(i, 100.0 + i) for i in range(30)]
    bars[29] = _bar(29, 127.0, open_price=120.0, high=128.0, low=119.0)
    bars.append(_bar(30, 128.0))
    first, reasons = attach_character_change_exits([_signal()], {"AAA": bars})
    extended = bars + [_bar(31, 10.0), _bar(32, 500.0)]
    second, later_reasons = attach_character_change_exits(
        [_signal()], {"AAA": extended})
    assert first == second
    assert reasons == later_reasons == {"abnormal_down_day": 1}
