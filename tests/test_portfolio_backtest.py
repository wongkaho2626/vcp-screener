"""Focused tests for conservative portfolio execution and constraints."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from portfolio_backtest import Config, _adv_dollars, _plan_rebreak_after_pullback, run_portfolio


class PortfolioBacktestTests(unittest.TestCase):
    def test_rebreak_waits_for_close_above_frozen_prior_high(self):
        bars = [{"date": f"d{i:02}", "open": c, "high": h, "low": lo,
                 "close": c, "volume": 1_000_000}
                for i, (c, h, lo) in enumerate([
                    *[(90, 91, 89)] * 19, (100, 102, 99), (101, 103, 100),
                    (100, 101, 90), (102, 103, 101), (104, 104.5, 103)])]
        # idx 21 is MA20 touch-and-hold; frozen prior high is 103.  A close
        # equal to 102 does not trigger; idx 23 closes above it.
        self.assertEqual(_plan_rebreak_after_pullback(bars, 19, 92), 23)

    def test_rebreak_invalidates_on_close_below_pattern_stop(self):
        closes = [90] * 19 + [100, 101, 100, 91, 105]
        bars = [{"date": f"d{i:02}", "open": c, "high": c + 1, "low": c - 1,
                 "close": c, "volume": 1_000_000} for i, c in enumerate(closes)]
        self.assertIsNone(_plan_rebreak_after_pullback(bars, 19, 92))

    def test_rebreak_respects_wait_window(self):
        closes = [90] * 19 + [100, 101, 100, 99, 105]
        bars = [{"date": f"d{i:02}", "open": c, "high": c + 1, "low": c - 1,
                 "close": c, "volume": 1_000_000} for i, c in enumerate(closes)]
        self.assertIsNone(_plan_rebreak_after_pullback(bars, 19, 92, rebreak_window=1))

    def test_trailing_adv_excludes_fill_day(self):
        bars = [{"close": 10, "volume": v} for v in (100, 200, 10_000)]
        self.assertEqual(_adv_dollars(bars, 2), 1500)

    def test_daily_marking_stop_gap_and_costs(self):
        bars = [
            {"date": f"d{i:02}", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1_000_000}
            for i in range(25)
        ]
        bars[23] = {"date": "d23", "open": 90, "high": 91, "low": 89, "close": 90, "volume": 1_000_000}
        signal = {"symbol": "AAA", "sector": "Tech", "signal_date": "d20", "fill_date": "d21",
                  "fill_idx": 21, "edge_rank": 82.5, "pattern_stop": 92}
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio({}, {"AAA": bars}, Config(initial_cash=100_000, commission_bps=5, slippage_bps=5))
        trade = out["trades"][0]
        self.assertEqual(trade["entry_price"], 100.1)  # next-bar open plus 10 bps
        self.assertEqual(trade["exit_price"], 89.91)  # gap below stop plus sell costs
        self.assertEqual(trade["exit_reason"], "stop")
        self.assertEqual(out["equity_curve"][0]["positions"], 1)
        self.assertLess(out["summary"]["max_drawdown_pct"], 0)

    def test_position_and_sector_caps(self):
        bars = [{"date": f"d{i:02}", "open": 10, "high": 11, "low": 9.5, "close": 10, "volume": 10_000_000}
                for i in range(24)]
        signals = [{"symbol": s, "sector": "Tech", "signal_date": "d20", "fill_date": "d21",
                    "fill_idx": 21, "edge_rank": e, "pattern_stop": 8}
                   for s, e in (("AAA", 80), ("BBB", 70), ("CCC", 60))]
        with patch("portfolio_backtest._candidate_signals", return_value=signals):
            cfg = Config(initial_cash=10_000, max_positions=2, max_position_pct=20, max_sector_pct=25,
                         commission_bps=0, slippage_bps=0)
            out = run_portfolio({}, {s: bars for s in ("AAA", "BBB", "CCC")}, cfg)
        entered = [t["symbol"] for t in out["trades"]]
        self.assertEqual(entered, ["AAA", "BBB"])
        self.assertEqual(out["summary"]["rejected"]["duplicate_or_position_limit"], 1)
        self.assertLessEqual(sum(t["shares"] * t["entry_price"] for t in out["trades"]), 2500)

    def test_missing_symbol_date_uses_last_close(self):
        aaa = [
            {"date": "d20", "open": 10, "high": 10, "low": 10, "close": 10, "volume": 1_000_000},
            {"date": "d21", "open": 10, "high": 12, "low": 10, "close": 12, "volume": 1_000_000},
        ]
        spy = [
            {"date": d, "open": 100, "high": 100, "low": 100, "close": 100, "volume": 0}
            for d in ("d20", "d21", "d22")
        ]
        signal = {"symbol": "AAA", "sector": "Tech", "signal_date": "d20", "fill_date": "d21",
                  "fill_idx": 1, "edge_rank": 82.5, "pattern_stop": 8}
        with patch("portfolio_backtest._candidate_signals", return_value=[signal]):
            out = run_portfolio({}, {"AAA": aaa, "SPY": spy}, Config(commission_bps=0, slippage_bps=0))
        self.assertEqual(out["equity_curve"][-1]["equity"], out["equity_curve"][-2]["equity"])
        self.assertIn("excess_return", out["equity_curve"][-1])
        # Day-one benchmark exposure is zero; the following day's benchmark
        # return is scaled by the prior close's portfolio exposure.
        self.assertEqual(out["equity_curve"][0]["exposure_matched_spy_return"], 0.0)
        self.assertGreater(out["equity_curve"][0]["gross_exposure_pct"], 0)
        self.assertIn("exposure_matched_excess_return", out["equity_curve"][-1])


if __name__ == "__main__":
    unittest.main()
