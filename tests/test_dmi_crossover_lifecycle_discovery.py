from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from dmi_crossover_lifecycle_discovery import (
    dmi_series,
    directional_state,
    lifecycle_signals,
)


def bars(count: int) -> list[dict]:
    return [{"date": f"d{i:03d}", "open": 10 + i, "high": 11 + i,
             "low": 9 + i, "close": 10 + i, "volume": 1000}
            for i in range(count)]


def row(index: int) -> dict:
    return {"setup_id": "AAA|d000|0", "symbol": "AAA", "sector": "Tech",
            "as_of_date": "d000", "signal_date": f"d{index:03d}",
            "fill_date": f"d{index + 1:03d}", "fill_idx": index + 1,
            "edge_rank": 70, "pattern_stop": 5, "pivot": 10,
            "close": 20, "features": [0.0] * 15}


def test_rising_series_has_positive_not_negative_directional_index() -> None:
    plus_di, minus_di = dmi_series(bars(20), period=3)
    assert plus_di[-1] is not None and plus_di[-1] > 0
    assert minus_di[-1] == 0


def test_future_append_cannot_change_existing_dmi() -> None:
    history = bars(20)
    before = dmi_series(history, period=3)
    after = dmi_series([*history, {**bars(1)[0], "date": "d020",
                                  "high": 1, "low": 0, "close": .5}], period=3)
    assert after[0][:len(before[0])] == before[0]
    assert after[1][:len(before[1])] == before[1]


def test_directional_state_requires_cross_and_pivot() -> None:
    history = bars(4)
    plus = [None, 10, 9, 12]
    minus = [None, 11, 10, 8]
    assert directional_state(history, plus, minus, 3, pivot=10) == {
        "positive_cross": True, "negative_dominance": False,
    }
    assert not directional_state(history, plus, minus, 3, pivot=20)["positive_cross"]


def test_lifecycle_requires_two_reverse_days_and_caps_attempts() -> None:
    states = []
    values = [(True, False), (False, True), (False, True),
              (True, False), (False, True), (False, True),
              (True, False), (False, True), (False, True), (True, False)]
    for index, (cross, negative) in enumerate(values, start=100):
        states.append({**row(index), "positive_cross": cross,
                       "negative_dominance": negative})
    signals = lifecycle_signals(states)
    assert [signal["fill_idx"] for signal in signals] == [101, 104, 107]
    assert [signal["model_exit_idx"] for signal in signals] == [103, 106, 109]
