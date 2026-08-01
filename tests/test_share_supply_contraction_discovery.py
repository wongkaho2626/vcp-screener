from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from share_supply_contraction_discovery import (
    SHARE_TAGS,
    as_filed_share_events,
    share_contraction_signals,
)


def _fact(val: float, end: str, start: str, accession: str,
          filed: str, form: str = "10-Q") -> dict:
    return {"val": val, "start": start, "end": end, "accn": accession,
            "filed": filed, "form": form}


def _payload(current: float = 90.0, prior: float = 100.0) -> dict:
    accession = "0001-20-000001"
    return {"facts": {"us-gaap": {
        SHARE_TAGS[0]: {"units": {"shares": [
            _fact(prior, "2019-03-31", "2019-01-01", accession, "2020-05-01"),
            _fact(current, "2020-03-31", "2020-01-01", accession, "2020-05-01"),
        ]}}
    }}}


def _row(signal_date: str, fill_idx: int = 1) -> dict:
    return {"setup_id": "AAA|2020-05-01|0", "symbol": "AAA", "sector": "Tech",
            "signal_date": signal_date, "fill_date": "2020-05-04",
            "fill_idx": fill_idx, "edge_rank": 70.0, "pattern_stop": 90.0,
            "pivot": 100.0, "close": 101.0}


def test_share_event_uses_same_accession_and_diluted_priority() -> None:
    events = as_filed_share_events(_payload())
    assert len(events) == 1
    assert events[0]["share_tag"] == SHARE_TAGS[0]
    assert abs(events[0]["share_growth"] - (-.10)) < 1e-12
    assert events[0]["current_shares"] == 90.0
    assert events[0]["prior_shares"] == 100.0


def test_same_day_filing_cannot_signal_but_next_day_can() -> None:
    event = as_filed_share_events(_payload())[0]
    events = {"AAA": [event]}
    assert share_contraction_signals([_row("2020-05-01")], events) == []
    signals = share_contraction_signals([_row("2020-05-02")], events)
    assert len(signals) == 1
    assert signals[0]["signal_date"] == "2020-05-02"
    assert signals[0]["fill_idx"] == 1
    assert signals[0]["model_exit_idx"] == 21
    assert "return" not in signals[0]


def test_latest_noncontraction_supersedes_older_contraction() -> None:
    contraction = as_filed_share_events(_payload())[0]
    noncontraction = {**contraction, "filed": "2020-05-02",
                      "accession": "0001-20-000002", "share_growth": .01}
    rows = [_row("2020-05-03")]
    assert share_contraction_signals(
        rows, {"AAA": [contraction, noncontraction]}) == []


def test_stale_event_and_close_at_pivot_are_ineligible() -> None:
    event = as_filed_share_events(_payload())[0]
    assert share_contraction_signals(
        [_row("2020-09-15")], {"AAA": [event]}) == []
    at_pivot = {**_row("2020-05-02"), "close": 100.0}
    assert share_contraction_signals([at_pivot], {"AAA": [event]}) == []


def test_future_filing_does_not_change_earlier_signal() -> None:
    contraction = as_filed_share_events(_payload())[0]
    row = _row("2020-05-02")
    initial = share_contraction_signals([row], {"AAA": [contraction]})
    future = {**contraction, "filed": "2020-06-01",
              "accession": "0001-20-000002", "share_growth": .25}
    assert share_contraction_signals(
        [row], {"AAA": [contraction, future]}) == initial
