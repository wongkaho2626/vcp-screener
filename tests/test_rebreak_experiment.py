"""Tests for the fixed chronological rebreak experiment."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from rebreak_experiment import _subset


def test_subset_uses_breakout_date_and_inclusive_bounds():
    dets = {"AAA": [
        {"forward_outcome": {"exit_date": "2021-12-31"}},
        {"forward_outcome": {"exit_date": "2022-01-01"}},
    ]}
    out = _subset(dets, "2016-01-01", "2021-12-31")
    assert len(out["AAA"]) == 1
    assert out["AAA"][0]["forward_outcome"]["exit_date"] == "2021-12-31"
