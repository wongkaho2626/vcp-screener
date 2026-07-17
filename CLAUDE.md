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
python3 scripts/download_sp500_history.py     # (re)build SP500_Historical_Data.csv from yfinance
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
- Support/resistance zones: `calculators/support_resistance_calculator.py`
  enriches live, historical and backtest scans by default (disable with
  `--no-support-resistance`). Additive overlay — never changes VCP score or
  ranking unless an explicit `--sr-*` filter is passed; causal by
  construction (swings confirm N bars late, breaks on confirmed closes only).
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
- **Support-aware + industry-momentum gate: null (2026-07-14).** Declared
  test (`industry_momentum_vcp_experiment.py`, frozen 6-1 GICS
  industry-momentum top-30% gate on detections already within 3% of strong
  support): gate cuts trades 104→48, both variants lose in the 2021–2026
  fold, exposure-matched excess t −0.48 (gate) / −0.69 (support-only), OOS
  Sharpe negative. GICS mapping is a current snapshot, not PIT. See
  `backtests/industry_momentum_vcp/`. S/R zones remain a context overlay,
  not an alpha source.
- **Pullback-then-rebreak entry: null (2026-07-14, 10/100 Reject).** Variant
  (breakout → MA20 touch-and-hold ≤15 sessions → close above post-breakout
  high, next-open entry): 145 trades, mean −0.11%/trade net (t −0.105), PF
  0.945, PSR 46%. Fails the robustness bar on both prongs — fold sign-flip
  (2016–2020 t +1.53 vs 2021–2026 t −1.81) and trim-fragile (drop-top-5 →
  t −2.01, significantly negative). Spearman(Edge, ret) −0.06: overlays don't
  stack, again. Raw returns, so excess vs SPY is worse. See
  `backtests/rebreak/verification_report.md`.
- **Pocket Pivot entry: relative improvement but no edge (2026-07-16, 20/100 Reject).**
  Causal v2 rule (up-day volume above every prior-10-session down-day volume,
  SMA10>SMA50>SMA200, within 3% of SMA10/pivot, next-open fill) returned +8.53%
  on 42 trades versus -5.41% for frozen pullback, with -3.74% MDD. The result
  is development-period concentrated: 2022–2024 PF 0.80; 2025–2026 seven
  trades, zero winners. Exposure-matched excess CAGR -0.08%, raw DSR 4.7%,
  and OOS Sharpe -0.15. Keep as research-only; do not promote live. See
  `backtests/pocket_pivot/verification_report.md`.
- **Fibonacci-retracement fill on Pocket Pivot: harmful (2026-07-16, 15/100
  Reject).** Frozen rule (v2 signal unchanged; wait ≤10 sessions for a 38.2%
  retracement of the 10-session signal leg, touch-and-hold fill, next-open
  entry): only 19 of 42 signals fill, PF 0.75, expectancy −0.93%/trade, lift
  vs plain pocket pivot t −1.44. Structural adverse selection — 6 of the 7
  >10% v2 winners never retraced, and the one that did (ALGN +62.9%) became a
  −8.1% stop-out; deeper fib levels (50%/61.8%) are worse. Retrace-style fills
  and momentum signals are substitutes, not complements (same lesson as
  edge×pullback). See `backtests/pocket_pivot_fib/verification_report.md`.
- **Breakout-day opening-gap conditioning: null, sign reversed (2026-07-17,
  7/100 Reject).** Frozen rule (entry-day open ≥ +1.0% above prior close ⇒
  "institutional demand" group, metric per-trade excess vs SPY, 173 classified
  CSV trades): gap trades are *worse*, not better — mean −2.97% vs +0.10%
  (Welch t −1.43, ns), PF 0.489 vs 1.024, negative at every threshold
  (0.5/1/2%) and in both folds. Prespecified give-up criteria fired round 1.
  Post-hoc reading (gap-ups = adverse selection, chasing extended opens) joins
  the fib-fill lesson as hypothesis-generating only. Side finding: 43/173
  entry fills deviate >1% from entry-day close (mixed fill convention in
  `trade_simulator.py`, unaudited). See
  `backtests/breakout_gap/verification_report.md`.
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
