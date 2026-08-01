from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from obv_accumulation_lifecycle_discovery import obv_series, obv_state


def bars(closes: list[float], volumes: list[float]) -> list[dict]:
    return [{"date": f"d{i:03d}", "open": close, "high": close + 1,
             "low": close - 1, "close": close, "volume": volume}
            for i, (close, volume) in enumerate(zip(closes, volumes))]


def test_obv_adds_subtracts_or_holds_volume_by_close_direction() -> None:
    history = bars([10, 11, 10, 10], [100, 200, 300, 400])
    assert obv_series(history) == [0.0, 200.0, -100.0, -100.0]


def test_obv_state_requires_prior_window_high_and_price_pivot() -> None:
    history = bars([9, 10, 11, 12], [100, 100, 100, 100])
    obv = obv_series(history)
    ema = [None, 50.0, 100.0, 150.0]
    assert obv_state(history, obv, ema, 3, pivot=11, high_lookback=3) == {
        "positive_cross": True, "negative_dominance": False,
    }
    assert not obv_state(history, obv, ema, 3, pivot=13,
                         high_lookback=3)["positive_cross"]


def test_obv_negative_state_is_below_causal_ema() -> None:
    history = bars([10, 11, 10], [100, 100, 300])
    obv = obv_series(history)
    state = obv_state(history, obv, [None, 50.0, 0.0], 2,
                      pivot=100, high_lookback=2)
    assert state["negative_dominance"] is True


def test_future_append_cannot_change_existing_obv_or_state() -> None:
    history = bars([9, 10, 11, 12], [100, 100, 100, 100])
    before_obv = obv_series(history)
    before = obv_state(history, before_obv, [None, 50.0, 100.0, 150.0],
                       3, pivot=11, high_lookback=3)
    extended = bars([9, 10, 11, 12, 1, 100], [100] * 6)
    after_obv = obv_series(extended)
    after = obv_state(extended, after_obv,
                      [None, 50.0, 100.0, 150.0, 0.0, 0.0],
                      3, pivot=11, high_lookback=3)
    assert after_obv[:len(before_obv)] == before_obv
    assert after == before
