from copy import deepcopy
from datetime import date, timedelta
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from ma60_only_experiment import (
    MA_PERIOD,
    SLOPE_SESSIONS,
    build_standalone_signals,
    calculate_ma60_only_signal,
    evaluate_signals,
)


def _bars(values, start=0, missing=frozenset()):
    return [
        {
            "date": (date(2020, 1, 1) + timedelta(days=index)).isoformat(),
            "open": value,
            "high": value,
            "low": value,
            "close": value,
            "adjClose": value,
            "volume": 1_000_000,
        }
        for index, value in enumerate(values, start)
        if index not in missing
    ]


def _trend(start, step, count=100):
    return [start + step * index for index in range(count)]


def test_positive_stock_ma60_slope_above_spy_is_true():
    result = calculate_ma60_only_signal(
        _bars(_trend(100, 1.0)), _bars(_trend(100, .2)), "9999-12-31")
    assert result is not None
    assert result["positive_relative_ma_slope"] is True
    assert result["stock_ma_slope_pct"] > result["spy_ma_slope_pct"] > 0


def test_equal_slopes_are_strictly_false():
    values = _trend(100, .5)
    result = calculate_ma60_only_signal(_bars(values), _bars(values), "9999-12-31")
    assert result is not None
    assert result["positive_relative_ma_slope"] is False


def test_declining_stock_is_false_even_if_spy_declines_faster():
    result = calculate_ma60_only_signal(
        _bars(_trend(200, -.2)), _bars(_trend(200, -.5)), "9999-12-31")
    assert result is not None
    assert result["stock_ma_slope_pct"] < 0
    assert result["relative_ma_slope_pct"] > 0
    assert result["positive_relative_ma_slope"] is False


def test_insufficient_common_history_returns_none():
    required = MA_PERIOD + SLOPE_SESSIONS
    assert calculate_ma60_only_signal(
        _bars(_trend(100, 1, required - 1)),
        _bars(_trend(100, .1, required)), "9999-12-31") is None


def test_mismatched_calendars_use_only_common_sessions():
    stock = _bars(_trend(100, 1, 105), missing=frozenset({3, 9, 15}))
    spy = _bars(_trend(100, .1, 105), missing=frozenset({4, 10, 16}))
    result = calculate_ma60_only_signal(stock, spy, "9999-12-31")
    assert result is not None
    assert result["signal_date"] == stock[-1]["date"]


def test_no_future_bar_is_used_and_inputs_are_not_mutated():
    stock = _bars(_trend(100, 1, 100))
    spy = _bars(_trend(100, .1, 100))
    original_stock, original_spy = deepcopy(stock), deepcopy(spy)
    result = calculate_ma60_only_signal(stock, spy, stock[89]["date"])
    assert result is not None
    assert result["signal_date"] == stock[89]["date"]
    assert stock == original_stock
    assert spy == original_spy


def test_builder_emits_only_rising_edge_and_next_session_fill():
    values = [100.0] * 80 + _trend(101, 1, 20)
    spy_values = [100.0] * len(values)
    stock = _bars(values)
    spy = _bars(spy_values)
    membership = {"AAA": [("1900-01-01", "9999-12-31")]}
    signals, counts = build_standalone_signals(
        {"AAA": stock, "SPY": spy}, membership, {"AAA": "Test"},
        stock[0]["date"], stock[-1]["date"])
    assert len(signals) == 1
    signal = signals[0]
    assert signal["fill_date"] > signal["signal_date"]
    assert signal["positive_relative_ma_slope"] is True
    assert counts["emitted_signals"] == 1


def test_builder_enforces_membership_on_signal_and_fill():
    values = [100.0] * 80 + _trend(101, 1, 20)
    bars = _bars(values)
    membership = {"AAA": [(bars[0]["date"], bars[79]["date"])]}
    signals, counts = build_standalone_signals(
        {"AAA": bars, "SPY": _bars([100.0] * len(values))},
        membership, {}, bars[0]["date"], bars[-1]["date"])
    assert signals == []
    assert counts["not_member_on_signal"] == 1


def test_builder_accepts_a_shorter_ma_period_without_changing_default():
    values = [100.0] * 30 + _trend(101, 1, 20)
    stock = _bars(values)
    spy = _bars([100.0] * len(values))
    membership = {"AAA": [("1900-01-01", "9999-12-31")]}
    signals, _ = build_standalone_signals(
        {"AAA": stock, "SPY": spy}, membership, {"AAA": "Test"},
        stock[0]["date"], stock[-1]["date"], ma_period=10)
    assert len(signals) == 1
    assert signals[0]["relative_ma_period"] == 10
    assert signals[0]["relative_ma_slope_sessions"] == SLOPE_SESSIONS


def test_cost_stress_does_not_move_raw_open_stop():
    bars = _bars([100.0] * 90)
    signal = {
        "symbol": "AAA", "sector": "Test", "signal_date": bars[79]["date"],
        "fill_date": bars[80]["date"], "fill_idx": 80, "edge_rank": 100.0,
        "pattern_stop": 0.0, "pivot": None, "attempt": 1,
    }
    prices = {"AAA": bars, "SPY": bars}
    one_x = evaluate_signals([signal], prices, iterations=10)["trades"][0]
    ten_x = evaluate_signals(
        [signal], prices, cost_multiplier=10, iterations=10)["trades"][0]
    assert one_x["initial_stop"] == 92.0
    assert ten_x["initial_stop"] == 92.0
