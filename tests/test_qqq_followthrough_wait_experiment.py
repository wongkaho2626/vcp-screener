"""Focused tests for the causal QQQ risk-on wait gate."""

from copy import deepcopy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from qqq_followthrough_wait_experiment import (  # noqa: E402
    filter_after_qqq_wait,
    qqq_risk_on_age_sessions,
    train_parameter_is_identifiable,
)


SESSIONS = [
    "2023-10-27", "2023-10-30", "2023-10-31", "2023-11-01",
    "2023-11-02", "2023-11-03", "2024-12-18", "2024-12-19",
    "2025-04-07", "2025-04-08", "2025-04-09",
]


def test_age_is_number_of_completed_risk_on_sessions_at_open():
    assert qqq_risk_on_age_sessions("2023-10-30", SESSIONS) == (
        "2023-10-30", 0)
    assert qqq_risk_on_age_sessions("2023-10-31", SESSIONS) == (
        "2023-10-30", 1)
    assert qqq_risk_on_age_sessions("2023-11-01", SESSIONS) == (
        "2023-10-30", 2)


def test_two_session_wait_skips_first_two_opens_and_keeps_fresh_later_signal():
    rows = [
        {"symbol": "A", "fill_date": "2023-10-30"},
        {"symbol": "B", "fill_date": "2023-10-31"},
        {"symbol": "C", "fill_date": "2023-11-01"},
    ]
    original = deepcopy(rows)
    selected = filter_after_qqq_wait(rows, SESSIONS, 2)
    assert [row["symbol"] for row in selected] == ["C"]
    assert selected[0]["qqq_risk_on_age_sessions"] == 2
    assert selected[0]["qqq_followthrough_wait_sessions"] == 2
    assert rows == original


def test_finite_exit_open_is_not_entry_eligible():
    assert qqq_risk_on_age_sessions("2024-12-18", SESSIONS) is not None
    assert qqq_risk_on_age_sessions("2024-12-19", SESSIONS) is None


def test_open_ended_window_and_weekend_gap_use_actual_sessions():
    assert qqq_risk_on_age_sessions("2025-04-07", SESSIONS) == (
        "2025-04-07", 0)
    assert qqq_risk_on_age_sessions("2025-04-09", SESSIONS) == (
        "2025-04-07", 2)


def test_future_sessions_do_not_change_current_age():
    before = qqq_risk_on_age_sessions("2023-11-01", SESSIONS[:4])
    after = qqq_risk_on_age_sessions("2023-11-01", SESSIONS)
    assert before == after == ("2023-10-30", 2)


def test_zero_wait_reproduces_synchronized_risk_on_filter():
    rows = [
        {"symbol": "A", "fill_date": "2023-10-30"},
        {"symbol": "B", "fill_date": "2024-12-19"},
        {"symbol": "C", "fill_date": "2025-04-07"},
    ]
    assert [row["symbol"] for row in filter_after_qqq_wait(
        rows, SESSIONS, 0)] == ["A", "C"]


def test_negative_wait_is_rejected():
    try:
        filter_after_qqq_wait([], SESSIONS, -1)
    except ValueError as error:
        assert "non-negative" in str(error)
    else:
        raise AssertionError("negative wait should fail")


def test_train_parameter_requires_distinct_portfolio_outcomes():
    tied = [
        {"signals": 10, "metrics": {"summary": {"trades": 5, "end_value": 110}}},
        {"signals": 10, "metrics": {"summary": {"trades": 5, "end_value": 110}}},
    ]
    assert train_parameter_is_identifiable(tied) is False
    tied[1]["metrics"]["summary"]["end_value"] = 111
    assert train_parameter_is_identifiable(tied) is True
