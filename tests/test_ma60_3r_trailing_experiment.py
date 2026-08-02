import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from ma60_3r_trailing_experiment import exit_state_counts


def test_exit_state_counts_separates_armed_and_unarmed_stops():
    trades = [
        {"exit_reason": "stop"},
        {"exit_reason": "armed_trailing_stop", "trailing_armed_date": "2024-01-02"},
        {"exit_reason": "end_of_data", "trailing_armed_date": "2024-02-01"},
    ]
    result = exit_state_counts(trades)
    assert result == {
        "armed_trailing_stop": 1,
        "end_of_data": 1,
        "stop": 1,
        "armed_trades": 2,
        "unarmed_trades": 1,
    }


def test_exit_state_counts_handles_empty_log():
    assert exit_state_counts([]) == {"armed_trades": 0, "unarmed_trades": 0}
