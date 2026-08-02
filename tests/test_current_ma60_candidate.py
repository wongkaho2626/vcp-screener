"""Tests for the user-directed current MA60 research override."""

from datetime import date, timedelta
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from current_ma60_candidate import (  # noqa: E402
    EXIT_PARAMS,
    MA_PERIOD,
    SLOPE_SESSIONS,
    STATUS,
    calculate_current_buy_signal,
    current_candidate_spec,
    in_qqq_risk_on_session,
)


def _bars(count, step):
    return [
        {
            "date": (date(2024, 1, 1) + timedelta(days=index)).isoformat(),
            "adjClose": 100 + step * index,
        }
        for index in range(count)
    ]


def test_current_candidate_is_explicitly_ma60_slope10_override():
    spec = current_candidate_spec()
    assert MA_PERIOD == spec["ma_period"] == 60
    assert SLOPE_SESSIONS == spec["slope_sessions"] == 10
    assert EXIT_PARAMS["trigger_r"] == 3.0
    assert EXIT_PARAMS["trailing_pct"] == 24.0
    assert len(EXIT_PARAMS["holding_windows"]) == 18
    assert spec["timeout_sessions"] is None
    assert spec["force_exit_outside_calendar"] is True
    assert spec["period_exit_timing"] == "first_ticker_open_outside_all_windows"
    assert "VALIDATION_FAILED" in STATUS


def test_current_calculator_uses_ten_session_slope_metadata():
    result = calculate_current_buy_signal(
        _bars(90, 1.0), _bars(90, 0.1), "9999-12-31")
    assert result is not None
    assert result["ma_period"] == 60
    assert result["slope_sessions"] == 10
    assert result["positive_relative_ma_slope"] is True


def test_candidate_spec_returns_fresh_nested_values():
    first = current_candidate_spec()
    first["exit_params"]["trigger_r"] = 99
    first["exit_params"]["holding_windows"][0][0] = "changed again"
    first["calendar_windows"][0][0] = "changed"
    second = current_candidate_spec()
    assert second["exit_params"]["trigger_r"] == 3.0
    assert second["exit_params"]["holding_windows"][0][0] == "2002-07-24"
    assert second["calendar_windows"][0][0] == "2002-07-24"


def test_qqq_risk_on_state_excludes_finite_exit_open():
    assert in_qqq_risk_on_session("2023-10-30") is True
    assert in_qqq_risk_on_session("2024-12-18") is True
    assert in_qqq_risk_on_session("2024-12-19") is False
    assert in_qqq_risk_on_session("2025-04-07") is True
    assert in_qqq_risk_on_session("2099-01-01") is True
