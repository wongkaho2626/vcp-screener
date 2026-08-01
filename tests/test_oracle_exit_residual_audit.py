from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from oracle_exit_residual_audit import exit_proxy_flags, summarize


def bars(closes: list[float]) -> list[dict]:
    return [{"date": f"d{index:02d}", "open": close,
             "high": close + 1, "low": close - 1,
             "close": close, "volume": 1000}
            for index, close in enumerate(closes)]


def test_exit_proxy_flags_use_only_close_before_exit_open() -> None:
    history = bars([100, 101, 102, 103, 104, 110])
    flags = exit_proxy_flags(history, entry_idx=0, exit_idx=5)
    assert flags is not None
    assert flags["five_day_close_high"]
    assert flags["two_up_closes"]
    assert flags["gain_10pct"] is False
    extended = [*history, {"date": "d06", "open": 1, "high": 2,
                           "low": .5, "close": 1, "volume": 1000}]
    assert exit_proxy_flags(extended, entry_idx=0, exit_idx=5) == flags


def test_exit_proxy_flags_detect_weakness_and_giveback() -> None:
    history = bars([100, 110, 108, 105, 100, 99])
    flags = exit_proxy_flags(history, entry_idx=0, exit_idx=5)
    assert flags is not None
    assert flags["down_close"]
    assert flags["trailing_drawdown_5pct"]
    assert not flags["five_day_close_high"]


def test_summarize_reports_fixed_proxy_rates() -> None:
    false_flags = {key: False for key in (
        "five_day_close_high", "two_up_closes", "down_close", "below_sma10",
        "trailing_drawdown_5pct", "gain_10pct")}
    true_flags = {key: True for key in false_flags}
    records = [
        {"entry_delay_sessions": 1, "hold_sessions": 5,
         "oracle_return_pct": 2, "flags": false_flags},
        {"entry_delay_sessions": 3, "hold_sessions": 15,
         "oracle_return_pct": 4, "flags": true_flags},
    ]
    result = summarize(records)
    assert result["records"] == 2
    assert result["entry_delay_sessions"]["median"] == 2
    assert result["hold_sessions"]["within_10_pct"] == 50
    assert all(value == 50 for value in result["proxy_hit_rates"].values())
