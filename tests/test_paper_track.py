"""Tests for the prospective paper-tracking harness (frozen VCP v1 forward)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts"))

from paper_track import (  # noqa: E402
    TrackConfig,
    attach_excess,
    evaluate_setup,
    ingest_candidates,
    ledger_stats,
    new_ledger,
    score_readiness,
)


def _bars(specs, start=0):
    """specs: list of (open, low, close). Dates are zero-padded and sortable."""
    return [{"date": f"d{start + i:03}", "open": o, "high": max(o, c) + 1.0,
             "low": lo, "close": c, "volume": 1_000_000}
            for i, (o, lo, c) in enumerate(specs)]


def _flat(n, price=100.0, start=0):
    return _bars([(price, price - 1, price)] * n, start=start)


def _setup(**overrides):
    base = {"id": "TEST-d029", "symbol": "TEST", "sector": "Tech",
            "as_of_date": "d029", "pivot": 105.0, "pattern_stop": 95.0,
            "edge_rank": 60.0, "suggested_weight_pct": 10.0, "status": "watching"}
    return {**base, **overrides}


def _candidate(symbol="TEST", pivot=105.0, low=95.0, valid=True, edge=60.0):
    return {"symbol": symbol, "sector": "Tech", "valid_vcp": valid,
            "edge_rank": edge, "suggested_weight_pct": 10.0,
            "pivot_proximity": {"pivot_price": pivot},
            "vcp_pattern": {"contractions": [{"low_price": 100.0},
                                             {"low_price": low}]}}


class LifecycleTests(unittest.TestCase):
    """30 flat bars at 100 (as-of bar 29), pivot 105, pattern stop 95."""

    def test_still_watching_before_breakout(self):
        chrono = _flat(32)
        out = evaluate_setup(_setup(), chrono)
        self.assertEqual(out["status"], "watching")

    def test_breakout_then_awaiting_pullback(self):
        chrono = _flat(32) + _bars([(105, 104, 106)], start=32)
        out = evaluate_setup(_setup(), chrono)
        self.assertEqual(out["status"], "awaiting_pullback")
        self.assertEqual(out["breakout_date"], "d032")

    def test_pullback_signal_without_next_open_is_entry_pending(self):
        chrono = _flat(32) + _bars([(105, 104, 106), (101, 100, 101)], start=32)
        out = evaluate_setup(_setup(), chrono)
        self.assertEqual(out["status"], "entry_pending")
        self.assertEqual(out["signal_date"], "d033")

    def test_entry_fills_next_open_with_costs_and_stop(self):
        chrono = _flat(32) + _bars([(105, 104, 106), (101, 100, 101),
                                    (102, 101, 103)], start=32)
        out = evaluate_setup(_setup(), chrono)
        self.assertEqual(out["status"], "open")
        self.assertEqual(out["entry_date"], "d034")
        self.assertAlmostEqual(out["entry_price"], 102 * 1.001, places=4)
        # max(pattern stop 95, fill * 0.92 = 93.93)
        self.assertAlmostEqual(out["stop"], 95.0, places=4)

    def test_close_below_stop_exits_next_open(self):
        chrono = _flat(32) + _bars([(105, 104, 106), (101, 100, 101),
                                    (102, 101, 103), (100, 93, 94),
                                    (96, 95, 97)], start=32)
        out = evaluate_setup(_setup(), chrono)
        self.assertEqual(out["status"], "closed")
        self.assertEqual(out["exit_reason"], "stop")
        self.assertEqual(out["exit_date"], "d036")
        fill, exit_price = 102 * 1.001, 96 * 0.999
        self.assertAlmostEqual(out["net_return_pct"],
                               (exit_price / fill - 1) * 100, places=2)

    def test_stop_close_on_last_bar_is_exit_pending(self):
        chrono = _flat(32) + _bars([(105, 104, 106), (101, 100, 101),
                                    (102, 101, 103), (100, 93, 94)], start=32)
        out = evaluate_setup(_setup(), chrono)
        self.assertEqual(out["status"], "exit_pending")

    def test_timeout_exits_at_open_after_60_holding_bars(self):
        tail = [(103, 102, 103)] * 61
        chrono = _flat(32) + _bars([(105, 104, 106), (101, 100, 101)],
                                   start=32) + _bars(tail, start=34)
        out = evaluate_setup(_setup(), chrono)
        self.assertEqual(out["status"], "closed")
        self.assertEqual(out["exit_reason"], "timeout")
        self.assertEqual(out["holding_bars"], 60)
        self.assertEqual(out["exit_date"], "d094")

    def test_close_below_pattern_stop_while_waiting_invalidates(self):
        chrono = _flat(32) + _bars([(105, 104, 106), (95, 93, 94)], start=32)
        out = evaluate_setup(_setup(), chrono)
        self.assertEqual(out["status"], "invalidated")

    def test_close_below_pattern_stop_before_breakout_invalidates(self):
        chrono = _flat(31) + _bars([(95, 93, 94)], start=31)
        out = evaluate_setup(_setup(), chrono)
        self.assertEqual(out["status"], "invalidated")

    def test_pullback_window_expires_after_15_bars(self):
        # Price runs away: lows never touch the lagging MA20.
        run = [(106 + i, 105.5 + i, 107 + i) for i in range(16)]
        chrono = _flat(32) + _bars([(105, 104, 106)], start=32) + _bars(run, start=33)
        out = evaluate_setup(_setup(), chrono)
        self.assertEqual(out["status"], "window_expired")

    def test_no_breakout_within_watch_window_expires(self):
        chrono = _flat(75)
        out = evaluate_setup(_setup(), chrono)
        self.assertEqual(out["status"], "expired_no_breakout")


class ExcessTests(unittest.TestCase):
    def test_excess_is_net_minus_spy_over_holding_dates(self):
        trade = _setup(status="closed", entry_date="d034", exit_date="d036",
                       net_return_pct=2.0)
        spy = [{"date": f"d{i:03}", "close": 500 + i} for i in range(40)]
        out = attach_excess(trade, spy)
        spy_ret = (536 / 534 - 1) * 100
        self.assertAlmostEqual(out["excess_vs_spy_pct"], 2.0 - spy_ret, places=4)

    def test_excess_left_unset_when_spy_dates_missing(self):
        trade = _setup(status="closed", entry_date="d034", exit_date="d036",
                       net_return_pct=2.0)
        self.assertIsNone(attach_excess(trade, [])["excess_vs_spy_pct"])


class IngestTests(unittest.TestCase):
    def test_ingest_creates_setup_and_dedups(self):
        ledger = new_ledger("2026-07-11T00:00:00+00:00")
        audit = ingest_candidates(ledger, [_candidate()], "d029", "ts")
        self.assertEqual(audit["recorded"], 1)
        setup = ledger["setups"][0]
        self.assertEqual(setup["pivot"], 105.0)
        self.assertEqual(setup["pattern_stop"], 95.0)  # final contraction low
        again = ingest_candidates(ledger, [_candidate()], "d030", "ts")
        self.assertEqual(again.get("duplicate"), 1)
        self.assertEqual(len(ledger["setups"]), 1)

    def test_ingest_applies_frozen_gates(self):
        ledger = new_ledger("2026-07-11T00:00:00+00:00")
        rows = [_candidate(symbol="LOWEDGE", edge=25.0),
                _candidate(symbol="NOVCP", valid=False),
                _candidate(symbol="NOPIVOT", pivot=None)]
        audit = ingest_candidates(ledger, rows, "d029", "ts")
        self.assertEqual(len(ledger["setups"]), 0)
        self.assertEqual(audit["edge_below_min"], 1)
        self.assertEqual(audit["invalid_vcp"], 1)
        self.assertEqual(audit["missing_pivot"], 1)


class ReadinessTests(unittest.TestCase):
    def _closed(self, n, excess, first="2026-01-02", last="2027-06-30"):
        rows = []
        for i in range(n):
            rows.append(_setup(id=f"T{i}", status="closed", net_return_pct=excess,
                               excess_vs_spy_pct=excess + (0.1 * (i % 3)),
                               entry_date=first, exit_date=last))
        return rows

    def test_caps_bind_below_30_trades(self):
        stats = ledger_stats(self._closed(10, 1.0))
        gates = {g["gate"]: g["passed"] for g in score_readiness(stats)}
        self.assertFalse(gates["at least 30 closed trades"])
        self.assertTrue(gates["prospective data (survivorship-free)"])

    def test_all_gates_pass_with_enough_positive_trades(self):
        stats = ledger_stats(self._closed(40, 1.5))
        gates = score_readiness(stats)
        self.assertTrue(all(g["passed"] for g in gates))

    def test_stats_aggregate_closed_trades_only(self):
        rows = self._closed(3, 2.0) + [_setup(id="W", status="watching")]
        stats = ledger_stats(rows)
        self.assertEqual(stats["closed_trades"], 3)
        self.assertEqual(stats["status_counts"]["watching"], 1)
        self.assertGreater(stats["t_stat_excess"], 0)


if __name__ == "__main__":
    unittest.main()
