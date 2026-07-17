# Experiment Playbook — mechanics and templates

Concrete conventions extracted from the ~20 experiments already in this repo
(`pullback_experiment.py`, `pocket_pivot_experiment.py`, `rebreak_experiment.py`,
`fib_pocket_pivot_experiment.py`, `industry_momentum_vcp_experiment.py`, …).
When in doubt, open the most recent of those and copy its shape.

## Commands

```bash
python3 -m pytest tests/ -q                     # must stay green before and after
python3 scripts/backtest_vcp.py --csv-data SP500_Historical_Data.csv --limit 0 --years 10
python3 scripts/trade_simulator.py <backtest.json> --price-csv SP500_Historical_Data.csv
python3 scripts/<name>_experiment.py <backtest.json> --price-csv SP500_Historical_Data.csv
```

- If `yfinance not found`: use `/opt/anaconda3/bin/python3` (system python3 lacks deps).
- Reuse an existing `backtests/vcp_backtest_*.json` as the detection source when the
  hypothesis doesn't change detection itself — a fresh 10-year backtest run is slow.
- `SP500_Historical_Data.csv` (~145 MB, gitignored) is the offline price source; the
  R2K equivalent lives alongside it where downloaded.

## Data hygiene checklist (before trusting any number)

- `api_stats.data_source == "csv"` in the report metadata. A silent yfinance
  fallback once produced garbage results.
- Universe is survivorship-biased (current constituents; R2K lost ~26% of names).
  Every number is an optimistic ceiling — say so in the report.
- Benchmark from `csv_client` is a synthetic equal-weight index of the same
  surviving universe, not tradable SPY. Label it.
- Signals: only `as_of_date`-consistent fields and OHLCV windows ending on the
  signal bar. Never read `forward_outcome` inside the rule.
- Fills: next-session open. Costs: 10 bps/side baseline; stress 20/50/100.

## Script skeleton

One file, `scripts/<name>_experiment.py`, ~200–400 lines:

```python
#!/usr/bin/env python3
"""Prespecified test of <hypothesis>.

<Two or three sentences: the frozen rule, what data it may consult,
and how fills/costs work. This docstring IS the frozen spec summary.>
"""
from __future__ import annotations
import argparse, json, math, statistics
from datetime import datetime

from csv_client import CSVClient            # or portfolio_backtest.run_portfolio

SEGMENTS = (
    ("development", "2016-01-01", "2021-12-31"),
    ("validation",  "2022-01-01", "2024-12-31"),
    ("evaluation",  "2025-01-01", "2026-12-31"),
)

def decide_entry(bars: list[dict], detection: dict) -> dict | None:
    """Pure, importable decision logic — this is what the tests cover."""
    ...

def run_experiment(detections: dict, prices: dict) -> dict:
    """Full run + per-segment folds. No I/O; returns a result dict."""
    ...

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backtest_json")
    parser.add_argument("--price-csv", required=True)
    parser.add_argument("--output-dir", default="backtests/<name>")
    ...
    # load, run, write timestamped .md + .json into output-dir
```

Conventions that matter:
- Pure decision functions take synthetic-friendly inputs (list of bar dicts) so
  tests need no CSV. All file I/O stays in `main()`/writer helpers.
- Immutable style: build new dicts/lists, don't mutate inputs.
- The comparison baseline is the frozen shipped rule (MA20 pullback entry,
  stop + 60-bar timeout exit) run under identical constraints — never compare
  against a strawman.
- Report both raw and excess-vs-SPY (or exposure-matched excess) numbers, plus:
  per-fold tables, drop-top-5/10 trim, cost stress, and a parameter-sensitivity
  table (±1 step on each frozen parameter — labelled "robustness check, not a
  search; no variation adopted").

## Test skeleton

`tests/test_<name>_experiment.py`, synthetic bars, red → green:

```python
import unittest
from scripts.<name>_experiment import decide_entry

def make_bars(closes, volumes=None, start="2020-01-01"):
    ...  # build minimal OHLCV dicts, date strings YYYY-MM-DD

class DecideEntryTest(unittest.TestCase):
    def test_fires_on_textbook_setup(self): ...
    def test_rejects_when_condition_absent(self): ...
    def test_never_uses_future_bars(self): ...   # truncate bars after signal; result unchanged
    def test_boundary_of_each_frozen_threshold(self): ...
```

Cover: the happy path, each rejection branch, threshold boundaries, and a
no-lookahead test (truncating bars after the signal date must not change the
decision). Existing examples: `tests/test_pocket_pivot_experiment.py`,
`tests/test_fib_pocket_pivot_experiment.py`.

## Robustness bar (all three, before any conclusion)

1. **Fold split** 2016–2020 vs 2021–2026 (or the 3-segment table above): the
   effect must keep its sign and rough magnitude. Sign-flip = dead.
2. **Outlier trim**: recompute the mean/t after dropping the top 5 and top 10
   trades. If the effect flips or dies, it was a lottery-ticket artifact.
3. **Cross-universe**: replicate on the R2K dataset where available. If not
   available for this hypothesis, state that the prong could not be run.
   **Current status (2026-07-17, found in the breakout-gap live run): there is
   no offline R2K OHLCV price CSV** — only R2K trade logs
   (`backtests/r2k/vcp_trades_merged.json`, 918 trades) and membership data
   (`scripts/data/r2k_membership.csv`). Hypotheses that only need trade-log
   fields (entry/exit dates, `excess_vs_spy_pct`) CAN still replicate on R2K;
   hypotheses needing price bars (gaps, MAs, volume) cannot, and must record
   the limitation. If the user later builds an R2K price CSV (adapt
   `scripts/download_sp500_history.py` to the R2K constituent list), this
   prong comes back for everything — worth mentioning when it blocks a run.

## Evaluation rounds with backtest-analyst

Round 1: hand backtest-analyst the experiment's JSON/markdown outputs (trade log,
equity curve if portfolio-level, segment tables). Let it produce the full report and
score into `backtests/<name>/verification_report.md`.

Between rounds, only these fixes are legitimate:
- computing a metric it flagged as missing (bootstrap, PSR/DSR, MC drawdown band,
  HAC alpha, cost stress);
- correcting an actual bug in the experiment code (then rerun everything);
- adding a missing bias audit (lookahead check, ADV cap, etc.).

Never legitimate between rounds: changing frozen parameters, switching the metric,
narrowing the sample, or re-selecting the baseline. If the score is capped by
survivorship (20) or missing true walk-forward (55), record the pre-cap raw score
too, so the report distinguishes "bad rule" from "good rule, bad data".

## Known score caps on current data (set expectations in round 1)

| Blocker | Cap | Fixable now? |
|---|---|---|
| Survivorship-biased CSV universe | 20 | No — needs delisted-inclusive security master + PIT membership |
| No true rolling walk-forward | 55 | Partially — chronological holdout exists; true WFA needs re-optimising windows |
| < 30 trades | 40 | Sometimes — widen sample only if the frozen spec already allowed it |

## Recording a result

- CLAUDE.md "Established results": one dated bullet, following the house pattern —
  `**<Name>: <verdict> (<date>, <score>/100 <band>).**` + mechanism, key stats
  (t, PF, fold behaviour), and pointer to `backtests/<name>/verification_report.md`.
- Memory file: short, following e.g. `fib-pocket-pivot-null.md`; add a MEMORY.md
  index line.
- Commit body = lab-notebook entry: hypothesis, frozen spec one-liner, headline
  stats, verdict. Conventional type (`feat:` for new experiment code, `docs:` for
  report/CLAUDE.md updates).
