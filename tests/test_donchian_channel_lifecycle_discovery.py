from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from donchian_channel_lifecycle_discovery import channel_state


def bars(closes: list[float]) -> list[dict]:
    return [{"date": f"d{i:03d}", "open": close, "high": close + 1,
             "low": close - 1, "close": close, "volume": 1000}
            for i, close in enumerate(closes)]


def test_channel_state_excludes_current_bar_from_both_windows() -> None:
    history = bars([10, 11, 12, 13, 14, 15])
    assert channel_state(history, 5, pivot=12, entry_lookback=5,
                         exit_lookback=3) == {
        "positive_cross": True, "negative_dominance": False,
    }


def test_channel_entry_requires_pivot_and_full_history() -> None:
    history = bars([10, 11, 12, 13, 14, 15])
    assert not channel_state(history, 5, pivot=16, entry_lookback=5,
                             exit_lookback=3)["positive_cross"]
    assert channel_state(history, 4, pivot=1, entry_lookback=5,
                         exit_lookback=3) == {
        "positive_cross": False, "negative_dominance": False,
    }


def test_channel_exit_requires_new_prior_window_closing_low() -> None:
    history = bars([10, 11, 12, 9])
    state = channel_state(history, 3, pivot=100, entry_lookback=3,
                          exit_lookback=3)
    assert state == {"positive_cross": False, "negative_dominance": True}


def test_future_append_cannot_change_existing_channel_state() -> None:
    history = bars([10, 11, 12, 13, 14, 15])
    before = channel_state(history, 5, pivot=12, entry_lookback=5,
                           exit_lookback=3)
    after = channel_state([*history, *bars([1, 100])], 5, pivot=12,
                          entry_lookback=5, exit_lookback=3)
    assert after == before
