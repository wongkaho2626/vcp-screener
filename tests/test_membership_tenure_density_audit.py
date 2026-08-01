from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from membership_tenure_density_audit import (
    annotate_candidates,
    containing_interval,
    density_counts,
    membership_tenure_days,
)


def test_interval_must_contain_signal_and_fill() -> None:
    membership = {"AAA": [("2020-01-01", "2020-01-10")]}
    assert containing_interval(membership, "AAA", "2020-01-09", "2020-01-10") == (
        "2020-01-01", "2020-01-10")
    assert containing_interval(membership, "AAA", "2020-01-10", "2020-01-11") is None


def test_tenure_uses_start_and_signal_only() -> None:
    assert membership_tenure_days("2020-01-01", "2020-04-01") == 91


def test_annotation_does_not_expose_future_end_date() -> None:
    signals = [{"symbol": "AAA", "signal_date": "2020-01-05",
                "fill_date": "2020-01-06"}]
    annotated, drops = annotate_candidates(
        signals, {"AAA": [("2020-01-01", "2020-12-31")]})
    assert drops == {"not_member_on_signal_and_fill": 0}
    assert annotated[0] == {"symbol": "AAA", "signal_date": "2020-01-05",
                            "fill_date": "2020-01-06",
                            "membership_start": "2020-01-01", "tenure_days": 4}
    assert "membership_end" not in annotated[0]


def test_density_caps_are_monotone() -> None:
    annotated = [
        {"symbol": "A", "tenure_days": 10},
        {"symbol": "B", "tenure_days": 100},
        {"symbol": "C", "tenure_days": 300},
        {"symbol": "D", "tenure_days": 600},
    ]
    counts = density_counts(annotated)
    assert [counts[str(cap)]["signals"] for cap in (90, 180, 365, 730)] == [1, 2, 3, 4]
