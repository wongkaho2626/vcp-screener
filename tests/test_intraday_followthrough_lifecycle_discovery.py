from __future__ import annotations

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from intraday_followthrough_lifecycle_discovery import (
    followthrough_state,
    return_decomposition,
)


def bars(values: list[tuple[float, float]]) -> list[dict]:
    return [{"date": f"d{index:03d}", "open": open_price,
             "high": max(open_price, close) * 1.01,
             "low": min(open_price, close) * .99,
             "close": close, "volume": 1000}
            for index, (open_price, close) in enumerate(values)]


def test_return_decomposition_separates_intraday_and_overnight() -> None:
    history = bars([(100, 100), (102, 103), (101, 104)])
    intraday, overnight = return_decomposition(history, 2, period=2) or (0, 0)
    assert intraday == pytest.approx(math.log(103 / 102) + math.log(104 / 101))
    assert overnight == pytest.approx(math.log(102 / 100) + math.log(101 / 103))


def test_state_requires_positive_intraday_lead_and_pivot() -> None:
    history = bars([(100, 100), (99, 102), (101, 104)])
    state = followthrough_state(history, 2, pivot=103, period=2)
    assert state["positive_cross"]
    assert not state["negative_dominance"]
    assert not followthrough_state(history, 2, pivot=105,
                                   period=2)["positive_cross"]


def test_nonpositive_intraday_sum_is_failure() -> None:
    history = bars([(100, 100), (102, 101), (103, 102)])
    state = followthrough_state(history, 2, pivot=90, period=2)
    assert not state["positive_cross"]
    assert state["negative_dominance"]


def test_future_append_cannot_change_existing_decomposition() -> None:
    history = bars([(100, 100), (99, 102), (101, 104)])
    before = followthrough_state(history, 2, pivot=103, period=2)
    extended = [*history, {"date": "d003", "open": 200, "high": 210,
                           "low": 190, "close": 205, "volume": 1000}]
    assert followthrough_state(extended, 2, pivot=103, period=2) == before


def test_decomposition_rejects_invalid_period() -> None:
    with pytest.raises(ValueError):
        return_decomposition(bars([(1, 1)]), 0, period=0)
