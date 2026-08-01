from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from macd_crossover_lifecycle_discovery import ema_series, macd_series, macd_state


def bars(closes: list[float]) -> list[dict]:
    return [{"date": f"d{i:03d}", "open": close, "high": close + 1,
             "low": close - 1, "close": close, "volume": 1000}
            for i, close in enumerate(closes)]


def test_ema_uses_arithmetic_seed_then_standard_alpha() -> None:
    assert ema_series([1.0, 2.0, 3.0, 4.0], period=3) == [None, None, 2.0, 3.0]


def test_future_append_cannot_change_existing_macd() -> None:
    history = bars([float(i) for i in range(1, 50)])
    before = macd_series(history)
    after = macd_series([*history, *bars([1.0, 100.0])])
    assert after[0][:len(history)] == before[0]
    assert after[1][:len(history)] == before[1]


def test_macd_state_requires_positive_cross_and_pivot() -> None:
    history = bars([9, 12])
    macd = [.1, .3]
    signal = [.2, .2]
    assert macd_state(history, macd, signal, 1, pivot=10) == {
        "positive_cross": True, "negative_dominance": False,
    }
    assert not macd_state(history, macd, signal, 1, pivot=13)["positive_cross"]
    assert not macd_state(history, [-.3, -.1], [-.2, -.2], 1, pivot=10)["positive_cross"]
