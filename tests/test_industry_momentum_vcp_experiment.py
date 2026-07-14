"""Tests for the frozen 6-1 GICS industry-momentum VCP gate."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from industry_momentum_vcp_experiment import (
    filter_detections,
    load_classifications,
    rank_industries,
    trailing_return,
)


def price_bars(start: float, count: int = 150) -> list[dict]:
    return [
        {"date": f"d{i:03d}", "close": start + i}
        for i in range(count)
    ]


class IndustryMomentumGateTests(unittest.TestCase):
    def test_classifications_are_promoted_from_subindustry_to_industry(self):
        with tempfile.TemporaryDirectory() as directory:
            constituents = os.path.join(directory, "constituents.json")
            hierarchy = os.path.join(directory, "hierarchy.json")
            with open(constituents, "w") as handle:
                json.dump([{"symbol": "AAA", "subSector": "Application Software"}], handle)
            with open(hierarchy, "w") as handle:
                json.dump({"Application Software": "Software"}, handle)
            self.assertEqual(
                load_classifications(constituents, hierarchy),
                {"AAA": "Software"},
            )

    def test_trailing_return_uses_exact_126_to_21_window(self):
        bars = price_bars(100)
        actual = trailing_return(bars, "d149")
        expected = bars[128]["close"] / bars[23]["close"] - 1
        self.assertAlmostEqual(actual, expected)

    def test_future_bars_do_not_change_as_of_return(self):
        bars = price_bars(100)
        original = trailing_return(bars, "d140")
        extended = bars + [
            {"date": "d150", "close": 1_000_000},
            {"date": "d151", "close": 2_000_000},
        ]
        self.assertEqual(trailing_return(extended, "d140"), original)

    def test_rank_keeps_top_thirty_percent_with_cutoff_ties(self):
        ranked = rank_industries({
            "A": 0.50, "B": 0.40, "C": 0.40, "D": 0.30,
            "E": 0.20, "F": 0.10, "G": 0.00,
        })
        self.assertEqual(ranked["A"]["rank"], 1)
        self.assertTrue(ranked["A"]["passes"])
        self.assertTrue(ranked["B"]["passes"])
        self.assertTrue(ranked["C"]["passes"])
        self.assertFalse(ranked["D"]["passes"])
        self.assertEqual(ranked["A"]["top_count"], 3)

    def test_filter_keeps_only_top_industry_and_annotates_detection(self):
        prices = {
            "AAA": price_bars(100),
            "BBB": price_bars(100),
            "CCC": [{"date": f"d{i:03d}", "close": 300 - i} for i in range(150)],
        }
        industries = {"AAA": "Leader", "BBB": "Leader", "CCC": "Laggard"}
        detections = {
            "AAA": [{"as_of_date": "d149"}],
            "CCC": [{"as_of_date": "d149"}],
        }
        kept, audit = filter_detections(detections, prices, industries)
        self.assertEqual(list(kept), ["AAA"])
        detail = kept["AAA"][0]["industry_momentum_gate"]
        self.assertEqual(detail["industry"], "Leader")
        self.assertEqual(detail["rank"], 1)
        self.assertEqual(audit, {"not_top_30pct": 1, "passed": 1})


if __name__ == "__main__":
    unittest.main()
