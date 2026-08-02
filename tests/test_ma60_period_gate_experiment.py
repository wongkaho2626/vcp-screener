"""Focused tests for the user-supplied MA60 calendar gate."""

from copy import deepcopy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from ma60_period_gate_experiment import (  # noqa: E402
    WINDOWS,
    filter_entry_windows,
    in_entry_window,
)


def test_all_eighteen_windows_are_frozen_exactly():
    assert len(WINDOWS) == 18
    assert WINDOWS[0] == ("2002-07-24", "2002-08-15")
    assert WINDOWS[-1] == ("2025-04-07", None)


def test_finite_window_boundaries_are_inclusive():
    assert in_entry_window("2022-06-14") is True
    assert in_entry_window("2022-11-14") is True
    assert in_entry_window("2022-06-13") is False
    assert in_entry_window("2022-11-15") is False


def test_open_ended_window_accepts_all_later_dates():
    assert in_entry_window("2025-04-07") is True
    assert in_entry_window("2099-12-31") is True


def test_filter_uses_fill_date_and_does_not_mutate_inputs():
    rows = [
        {"symbol": "A", "signal_date": "2022-06-13", "fill_date": "2022-06-14"},
        {"symbol": "B", "signal_date": "2022-11-14", "fill_date": "2022-11-15"},
    ]
    original = deepcopy(rows)
    selected = filter_entry_windows(rows)
    assert selected == [rows[0]]
    assert selected[0] is not rows[0]
    assert rows == original
