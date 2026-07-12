# CLAUDE.md — vcp-screener

Research repo: Minervini VCP screener + 10-year backtests. Python-only, no
framework, no build step. **The research programme is essentially concluded**
— read "Established results" before proposing new experiments, because most
obvious ideas have already been tested to a null.

## Commands

```bash
python3 -m pytest tests/ -q                 # full suite, must stay green
python3 scripts/screen_vcp.py               # live screen (yfinance)
python3 scripts/backtest_vcp.py --csv-data SP500_Historical_Data.csv --limit 0 --years 10
python3 scripts/trade_simulator.py <backtest.json> --price-csv SP500_Historical_Data.csv
```

If `yfinance not found`: use `/opt/anaconda3/bin/python3` (system python3
lacks the deps).

## Architecture

Pipeline: `screen_vcp.py` (live, orchestrates `calculators/`) →
`historical_scanner.py` (as-of walk) → `backtest_vcp.py` (universe backtest →
`vcp_backtest_*.json`) → `trade_simulator.py` (detections → trades with
excess-vs-SPY → `vcp_trades_*.json`) → experiment CLIs (see README table).

- Live-screen overlays: `edge_rank.annotate_candidates` (Edge/Weight) and
  `pullback_experiment.annotate_pullback_entry` (Entry) — both non-mutating,
  called in `screen_vcp.py` before report generation.
- Offline data: `--csv-data` (backtest, `CSVHistoricalClient`) / `--price-csv`
  (everything else, `csv_client.CSVClient`) read `SP500_Historical_Data.csv`
  (gitignored, ~145 MB). Always verify `api_stats.data_source == "csv"` in
  report metadata — a silent yfinance fallback once produced garbage results.
- Generated outputs (`backtests/**/*.json|md|csv|log`, `reports/*`) are
  gitignored; only code and curated data snapshots (`scripts/data/`) are
  committed.

## Conventions

- **Metric**: per-trade excess vs SPY over the trade's own holding dates.
  Raw returns are beta in a 2016–2026 bull tape; never present them as edge.
- **Robustness bar** for any claimed effect: 2016–2020 vs 2021–2026 fold
  split, drop-top-5/10 outlier trim, and cross-universe (S&P + R2K)
  replication. Several shiny numbers (edges==3 gate, stop-only +24% mean,
  MA-break exits on S&P) died exactly here — check before believing a mean.
- **No post-hoc parameter switching**: if a scan finds a better cell than the
  shipped rule, note it for prespecified validation on future data instead of
  swapping it in (see MA30 in `pullback_sensitivity.py`).
- Experiments are one CLI file each in `scripts/`, taking a trades/backtest
  JSON + `--price-csv`, writing a timestamped markdown report. Pure
  decision logic lives in importable functions with pytest coverage in
  `tests/` (see `simulate_exit`, `plan_pullback_entry`, `strict_exit`,
  `momentum_walk`).
- Tests are synthetic-bars unit tests; TDD (red → green) is the house style.
- Commits: conventional format (`feat:`/`fix:`/`chore:`), body records the
  experimental result so `git log` doubles as a lab notebook.

## Established results (do not re-litigate without new data)

- **Entry alpha: none.** ~1,500 trades, both universes: excess vs SPY ≈ 0,
  negative after costs. Failed rescues: detection gates, 108-combo grid,
  trend-template prerequisite, Russell 2000 universe, M.E.T.A. edges.
- **Exit rules: baseline (stop + 60-bar timeout) is optimal.** Trails, ATR,
  profit targets, MA-breaks, scale-outs, cull/ride — all ≈ 0 or worse; the
  60d timeout is load-bearing (removing it creates a survivorship lottery).
- **Validated and shipped**: MA20 pullback entry (+1.36 pp paired, t 3.13,
  replicates on R2K, smooth parameter surface) and Edge Rank sizing
  (+1.01%/trade, PIT-only — did not replicate on the CSV dataset).
- **The two overlays don't stack.** Edge×pullback interaction
  (`edge_pullback_interaction.py`, one-shot declared test): the pullback
  improvement does NOT concentrate in high-Edge names (Edge≥70 pooled t 1.09,
  trim-flips negative; interaction sign flips across universes; Spearman
  −0.04). Substitutes, not complements — matches frozen v1 gaining nothing
  from combining them.
- **Market-regime gates are dead.** Breadth levels/rising
  (`breadth_experiment.py`), SPY>200DMA and SPY 20d realized-vol conditioning:
  all null on both universes (|Welch t| ≤ 0.83). Structural reason: the
  excess-vs-SPY metric is market-neutral by construction.
- **Frozen v1 portfolio verdict: Reject (20/100).** Realistic daily-marked
  portfolio (next-open fills, costs, constraints) over 10.3y: CAGR −0.45%,
  exposure-matched excess t ≈ −1.8 to −2.7, OOS Sharpe collapse. See
  `backtests/improved/final_verification_report.md` and
  `references/frozen_strategy_v1.md`. The programme is closed: no deployable
  edge in this data; further work requires new data + a new predeclared
  hypothesis.
- **Data caveats**: CSV and R2K universes are survivorship-biased (R2K lost
  26% of names); close-based fills, no costs. All backtest numbers are
  optimistic ceilings.
