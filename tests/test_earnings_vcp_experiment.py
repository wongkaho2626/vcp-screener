"""Tests for the frozen earnings-catalyst VCP gate."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from earnings_vcp_experiment import _subset, earnings_gate, filter_detections


def bars():
    return [
        {"date": "2024-01-02", "open": 99, "close": 100},
        {"date": "2024-01-03", "open": 103, "close": 104},
        {"date": "2024-02-01", "open": 108, "close": 110},
    ]


class EarningsGateTests(unittest.TestCase):
    def test_passes_predeclared_gate(self):
        ok, detail = earnings_gate([{"event_date": "2024-01-02", "surprise_pct": 5}],
                                   bars(), "2024-02-01")
        self.assertTrue(ok)
        self.assertEqual(detail["gap_pct"], 3.0)

    def test_latest_completed_event_controls(self):
        events = [{"event_date": "2023-12-01", "surprise_pct": 10},
                  {"event_date": "2024-01-02", "surprise_pct": -1},
                  {"event_date": "2024-03-01", "surprise_pct": 20}]
        ok, detail = earnings_gate(events, bars(), "2024-02-01")
        self.assertFalse(ok)
        self.assertEqual(detail["reason"], "nonpositive_surprise")

    def test_rejects_old_event_low_gap_and_lost_price(self):
        old = [{"event_date": "2023-01-01", "surprise_pct": 1}]
        self.assertEqual(earnings_gate(old, bars(), "2024-02-01")[1]["reason"],
                         "event_outside_90_days")
        low_gap_bars = bars()
        low_gap_bars[1]["open"] = 101
        self.assertEqual(earnings_gate([{"event_date": "2024-01-02", "surprise_pct": 1}],
                                      low_gap_bars, "2024-02-01")[1]["reason"],
                         "event_gap_below_2pct")
        weak = bars()
        weak[-1]["close"] = 99
        self.assertEqual(earnings_gate([{"event_date": "2024-01-02", "surprise_pct": 1}],
                                      weak, "2024-02-01")[1]["reason"],
                         "price_not_above_pre_event_close")

    def test_filter_preserves_only_passing_breakout(self):
        det = {"AAA": [{"forward_outcome": {"outcome_type": "breakout",
                                               "exit_date": "2024-02-01"}}]}
        events = {"AAA": [{"event_date": "2024-01-02", "surprise_pct": 1}]}
        kept, audit = filter_detections(det, events, {"AAA": bars()})
        self.assertEqual(len(kept["AAA"]), 1)
        self.assertEqual(audit, {"passed": 1})
        self.assertIn("earnings_gate", kept["AAA"][0])

    def test_subset_ignores_detections_without_exit_dates(self):
        detections = {"AAA": [
            {"forward_outcome": {"exit_date": None}},
            {"forward_outcome": {"exit_date": "2024-02-01"}},
        ]}
        selected = _subset(detections, "2024-01-01", "2024-12-31")
        self.assertEqual(len(selected["AAA"]), 1)


if __name__ == "__main__":
    unittest.main()
