from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from squeeze_release_lifecycle_discovery import (
    band_series,
    lifecycle_signals,
    release_state,
)


def bars(closes: list[float]) -> list[dict]:
    return [{"date": f"d{i:03d}", "open": value, "high": value + 1,
             "low": value - 1, "close": value, "volume": 1000}
            for i, value in enumerate(closes)]


def row(index: int) -> dict:
    return {"setup_id": "AAA|d000|0", "symbol": "AAA", "sector": "Tech",
            "signal_date": f"d{index:03d}", "fill_date": f"d{index + 1:03d}",
            "fill_idx": index + 1, "edge_rank": 70, "pattern_stop": 90,
            "pivot": 100, "close": 110, "features": [0.0] * 15}


def test_flat_squeeze_then_up_close_is_release() -> None:
    history = bars([100] * 29 + [110])
    bands = band_series(history, period=20)
    state = release_state(history, bands, 29, pivot=105,
                          reference_lookback=5, squeeze_percentile=20)
    assert state == {"release": True, "below_mid": False}


def test_future_append_cannot_change_existing_release_state() -> None:
    history = bars([100] * 29 + [110])
    before = release_state(history, band_series(history), 29, 105,
                           reference_lookback=5)
    extended = [*history, *bars([50, 200])]
    after = release_state(extended, band_series(extended), 29, 105,
                          reference_lookback=5)
    assert after == before


def test_release_requires_pivot_and_up_close() -> None:
    history = bars([100] * 29 + [99])
    assert not release_state(history, band_series(history), 29, 100,
                             reference_lookback=5)["release"]


def test_lifecycle_schedules_next_open_exit_and_limits_attempts() -> None:
    states = []
    values = [(True, False), (False, False), (False, True),
              (True, False), (False, True), (True, False),
              (False, True), (True, False)]
    for i, (release, below_mid) in enumerate(values, start=150):
        states.append({**row(i), "release": release, "below_mid": below_mid})
    signals = lifecycle_signals(states, max_attempts=3)
    assert [signal["attempt"] for signal in signals] == [1, 2, 3]
    assert [signal["fill_idx"] for signal in signals] == [151, 154, 156]
    assert [signal["model_exit_idx"] for signal in signals] == [153, 155, 157]
