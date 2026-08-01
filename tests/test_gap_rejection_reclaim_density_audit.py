from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from gap_rejection_reclaim_density_audit import (
    is_gap_rejection,
    rejection_reclaim_signals,
)


def _bar(day: int, open_price: float, high: float, low: float,
         close: float) -> dict:
    return {"date": f"2020-01-{day:02d}", "open": open_price, "high": high,
            "low": low, "close": close, "volume": 1_000}


def _rows(bars: list[dict], pivot: float = 103.0,
          stop: float = 95.0) -> list[dict]:
    return [{
        "setup_id": "AAA|2020-01-01|0", "symbol": "AAA", "sector": "Tech",
        "as_of_date": "2020-01-01", "signal_date": bar["date"],
        "fill_date": bars[index + 1]["date"], "fill_idx": index + 1,
        "edge_rank": 70.0, "pattern_stop": stop, "pivot": pivot,
    } for index, bar in enumerate(bars[:-1])]


def _reclaim_fixture() -> list[dict]:
    return [
        _bar(1, 100, 101, 99, 100),
        _bar(2, 102, 103, 100.5, 101),  # +2% gap, bearish rejection
        _bar(3, 101, 102.5, 100.8, 102),
        _bar(4, 102, 104.5, 101.5, 104),  # strict high+pivot reclaim
        _bar(5, 104, 104.2, 100.0, 100.2),  # close below frozen low
        _bar(6, 100, 101, 99, 100),
    ]


def test_gap_rejection_uses_current_and_prior_completed_bar_only() -> None:
    bars = _reclaim_fixture()
    assert is_gap_rejection(bars[:2], 1)
    changed_future = bars[:2] + [_bar(3, 200, 220, 180, 210)]
    assert is_gap_rejection(changed_future, 1)
    bullish = [bars[0], {**bars[1], "close": 102.5}]
    assert not is_gap_rejection(bullish, 1)


def test_reclaim_signals_next_open_and_failure_exits_next_open() -> None:
    bars = _reclaim_fixture()
    signals = rejection_reclaim_signals(_rows(bars), {"AAA": bars})
    assert len(signals) == 1
    signal = signals[0]
    assert signal["rejection_date"] == "2020-01-02"
    assert signal["signal_date"] == "2020-01-04"
    assert signal["fill_date"] == "2020-01-05"
    assert signal["fill_idx"] == 4
    assert signal["model_exit_idx"] == 5
    assert "return" not in signal


def test_reclaim_must_clear_frozen_high_and_pivot() -> None:
    bars = _reclaim_fixture()
    bars[3] = {**bars[3], "close": 103.0}
    assert rejection_reclaim_signals(_rows(bars), {"AAA": bars}) == []


def test_reclaim_after_five_sessions_is_rejected() -> None:
    bars = [
        _bar(1, 100, 101, 99, 100),
        _bar(2, 102, 103, 100.5, 101),
        _bar(3, 101, 102, 100, 101),
        _bar(4, 101, 102, 100, 101),
        _bar(5, 101, 102, 100, 101),
        _bar(6, 101, 102, 100, 101),
        _bar(7, 101, 102, 100, 101),
        _bar(8, 102, 105, 101, 104),
        _bar(9, 104, 105, 103, 104),
    ]
    assert rejection_reclaim_signals(_rows(bars), {"AAA": bars}) == []


def test_lifecycle_is_truncation_invariant_after_observed_exit() -> None:
    bars = _reclaim_fixture()
    initial = rejection_reclaim_signals(_rows(bars), {"AAA": bars})
    extended = bars + [_bar(7, 300, 320, 290, 310)]
    later = rejection_reclaim_signals(_rows(extended), {"AAA": extended})
    assert later[0] == initial[0]
