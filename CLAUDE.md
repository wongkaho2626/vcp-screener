# CLAUDE.md — vcp-screener

Research repo: Minervini VCP screener + 10-year backtests. Python-only, no
framework, no build step. **There is no qualifying deployable strategy in the
repository.** Read "Current v2 checkpoint" and "Established results" before
proposing an experiment: more than 300 declared variants have already consumed
most obvious VCP entry/exit directions, and the latest existing-data replay is
a reject rather than untouched OOS.

## Commands

```bash
.venv/bin/python -m pytest tests/ -q          # full suite, must stay green
.venv/bin/python scripts/screen_vcp.py        # live screen (yfinance)
.venv/bin/python scripts/backtest_vcp.py --csv-data SP500_Historical_Data.csv --limit 0 --years 10
.venv/bin/python scripts/trade_simulator.py <backtest.json> --price-csv SP500_Historical_Data.csv
.venv/bin/python scripts/download_sp500_history.py  # rebuild local price CSV
```

Create the reproducible environment with `uv venv .venv --python 3.12` and
`uv pip install --python .venv/bin/python -r requirements.txt`. The system
Python may not contain the project dependencies. Exact v2 commands and frozen
artifact paths live in `backtests/v2_research_commands.md`.

## Architecture

Pipeline: `screen_vcp.py` (live, orchestrates `calculators/`) →
`historical_scanner.py` (as-of walk) → `backtest_vcp.py` (universe backtest →
`vcp_backtest_*.json`) → `trade_simulator.py` (detections → trades with
excess-vs-SPY → `vcp_trades_*.json`) → experiment CLIs (see README table).

The realistic research path is detections → declared train/discovery gate →
`portfolio_backtest.py` / `daily_score_decay_discovery.py` → frozen JSON and
daily/trade CSVs → a dedicated verification script. Portfolio capital, sizing,
maximum holdings, cash/capacity/sector/ADV constraints and cost assumptions are
fixed; signal research may change only entry/exit behavior.

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
- Large local price inputs and ordinary generated outputs remain gitignored.
  Frozen specifications, curated verification reports and selected JSON/CSV
  evidence are explicitly allowlisted and committed under `backtests/`; do not
  assume every file below that directory is disposable.

## Conventions

- **Metric**: per-trade excess vs SPY over the trade's own holding dates.
  Raw returns are beta in a 2016–2026 bull tape; never present them as edge.
- **Causality**: a signal confirmed using a day's close may fill no earlier
  than the next session. PIT membership must be true on signal and fill dates.
  Historical SPY data must be selected by date at or before the stock as-of
  date, never by sharing the stock's integer bar offset.
- **Fixed portfolio model**: do not alter starting capital, position sizing,
  holding limits, costs, sector/name/ADV constraints, risk caps or leverage to
  improve CAGR. SPY is benchmark-only and must never become a position or
  fallback asset.
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

## Current v2 checkpoint (2026-08-01)

- The frozen Trial 288 existing-data replay covers signals from 2022-01-01
  through 2026-03-31 and is exploratory, not untouched OOS. Existing PIT
  member-day coverage is 91.31%; incomplete delisted coverage remains.
- A historical benchmark bug was fixed before outcomes were opened:
  `screen_vcp.analyze_stock` had sliced SPY using the stock's integer bar
  offset, which could expose the wrong or future benchmark session for short
  or gapped stock histories. SPY is now date-aligned at or before the stock
  as-of date, with regression coverage in
  `tests/test_historical_benchmark_alignment.py`.
- Corrected result: 89 trades, net CAGR 0.05%, Sharpe 0.031, Sortino 0.045,
  Calmar 0.007, PF 1.059 and MDD -6.81%. Raw Backtest Score is 25/100; the
  unresolved-survivorship cap makes the rubric result 20/100. Drop-top-five
  expectancy is -1.71%, 5x-cost CAGR is -1.18%, DSR probability is 0.22%, and
  the 2024–2026 fold is negative.
- Therefore the hard goal is **not complete**. Never describe this replay as a
  pass. The amended completion rule accepts a score capped at or below 80 but
  still requires the same frozen S&P 500 stocks-only strategy to deliver at
  least 20% net CAGR and 30 independent trades on the pre-frozen
  best-available 2022–2026Q1 OOS, with raw A/B/C/D and every hard cap disclosed.
  Use repository-local 2006+ evidence only; do not search or require 2000–2005.
- Canonical artifacts:
  `backtests/exploratory_existing_data_replay/frozen_spec.md`,
  `backtests/exploratory_existing_data_replay/results/verification_report.md`,
  `backtests/exploratory_existing_data_replay/results/verification_metrics.json`,
  and `backtests/v2_research_commands.md`.

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
  2026-07-21 PIT correction: the pullback overlay's true effect size is
  ≈ +0.98 pp (see the pullback_pit2016 bullet below) — reset any sizing
  intuition built on the survivor-only numbers.
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
- **Signal-crowding conditioning: null (2026-07-17, 7/100 Reject).** Frozen
  rule (crowded = ≥2 co-detections within trailing 10 calendar days on
  `as_of_date`; declared direction crowded-worse on excess vs SPY): S&P
  −0.76 pp (t −0.42, ns), trim flips sign, sensitivity cells sign-unstable;
  R2K −1.89 pp (t −1.27, ns) with 81% of trades cluster-overlapped so the
  nominal t overstates independence. Give-up criteria fired round 1. First
  experiment where the cross-universe prong ran offline (trade-log-only
  feature). See `backtests/crowding/verification_report.md`.
- **Initial stop-width (base tightness) conditioning: null, sign reversed
  (2026-07-17, 7/100 Reject).** Frozen rule (tight = entry-to-stop risk ≤ 6%;
  declared direction tight-better per the Minervini tightness thesis): S&P
  tight trades are *worse* (−1.97 pp, t −1.13, ns; PF 0.53 vs 0.98) and the
  predeclared confound explains it — tight stops exit on the stop 64.5% vs
  45.1%, i.e. tagged out by noise. R2K null (+0.27 pp, t 0.21) with fold
  sign-flips; cross-universe signs disagree. Structural finding: 52% (S&P) /
  71% (R2K) of trades sit at the simulator's 8% risk cap, censoring the width
  distribution. Any future tightness test must measure the base itself
  (contraction depths), not the risk-capped stop distance. See
  `backtests/stop_width/verification_report.md`.
- **Detection-to-entry latency conditioning: null (2026-07-17, 6/100
  Reject).** Frozen rule (fresh = breakout triggers ≤7 calendar days after
  `as_of_date`; declared direction fresh-better): S&P +0.23 pp (t 0.12, coin
  flip), fold AND trim sign-flips; R2K +0.55 pp (t 0.50, ns).
  Spearman(latency, excess) −0.04 / +0.01 — no gradient exists at any
  threshold. Fourth entry-conditioning family closed (tape urgency, crowding,
  stop width, latency — all null/reversed); the trade log's causal fields are
  nearly exhausted, further cuts of the same 1,102 trades mostly re-measure
  noise.
  See `backtests/latency/verification_report.md`.
- **Contraction-tightening sequence: Reject, sign reversed (2026-07-17,
  7/100).** First direct test of the Minervini halving claim, from detection
  metadata (`vcp_pattern.contractions`, last/first depth ratio ≤ 0.5 =
  "textbook"): textbook sequences are *worse* on S&P — −2.24% vs +0.94%
  excess (t −1.90, bootstrap P 3.1%), PF 0.58 vs 1.23, and the gap widens
  under trims (t −2.34). R2K same sign (−0.91 pp) but ns with sign-flipping
  sensitivity cells; Spearman incoherent across universes — threshold-local,
  not a gradient. Second independent hint (after stop-width) that textbook
  tightness is adversely selected among detections; hypothesis-generating
  only. See `backtests/contraction/verification_report.md`.
- **Pre-2016 OOS replication of MA20 pullback entry: FAILED on
  delisted-inclusive PIT data — survivor-only "pass" was a survivorship
  artifact (2026-07-18, final 12/100 Reject).** Two-stage result. Stage 1
  (survivors-only CSV): paired Δ +0.69 pp, t 2.50, n 196 — passed the frozen
  bar, scored 20 capped / 71 pre-cap. Stage 2 (predeclared PIT protocol,
  `backtests/pullback_oos/pit_addendum.md`, frozen before results): built a
  delisted-inclusive universe (735 PIT members, 175+ recovered via Yahoo, 7
  curated rename aliases, wrong-entity/scale-break screens, 69.7% member-day
  coverage via `scripts/build_pit_universe.py`) and replayed the identical
  rule with a membership gate — **Δ collapses to +0.22 (t 0.58), 2006–10
  fold flips negative, trims flip negative**. Attribution: shared detections
  keep their Δ (+0.40); the 28 new delisted-name pairs average −0.43 and the
  91 pairs PIT discipline removes averaged +0.96. Lessons: (1) the paired
  design does NOT immunize against survivorship — buying weakness in
  survivors is adversely selected; (2) treat the shipped overlay's 2016–2026
  survivors-only evidence more cautiously (a 2016–2026 PIT rebuild via
  `build_pit_universe.py` is the natural follow-up); (3) Yahoo serves many
  delisted names but with corrupt series (TIE/CFC-style 100x scale breaks) —
  always run the scale-break screen; Stooq is bot-walled. 2006–2015 is spent;
  do NOT re-tune on it. See `backtests/pullback_oos/verification_report.md`.
- **2016–2026 PIT re-measurement of the shipped MA20 pullback overlay:
  PASSED — real but 58% smaller, first uncapped score (2026-07-21, 68/100
  Promising).** Predeclared follow-up to the pullback_oos reversal
  (`backtests/pullback_pit2016/frozen_spec.md`, frozen pre-results): built a
  600-ticker delisted-inclusive 2016–2026 universe with
  `build_pit_universe.py` (98 recovered + 15 same-entity rename aliases incl.
  FB←META; **91.39% member-day coverage ⇒ survivorship cap lifted** per the
  predeclared schedule) and replayed the identical frozen rule
  membership-gated. Paired Δ +0.98 pp (t 2.73, adj 2.55; PSR 99.4%, DSR 92.5%
  at N=4; PF 1.85; bootstrap P(≤0) 0.31%); both folds positive (2016H2–20
  +2.17 t 3.42; 2021–26 +0.33 t 0.75); trim signs hold. Verdict: the shipped
  overlay's improvement is real, NOT a survivorship artifact — but PIT
  discipline cuts it from +2.35 to +0.98 (survivor-only numbers overstated
  2.4×), the 2021–2026 half is a coin flip (faded since 2022), and the failed
  2006–2015 OOS stands. Overlay stays live with corrected expectations
  (≈ +1 pp, median +0.8); materially higher confidence requires prospective
  forward evidence, not more history. See
  `backtests/pullback_pit2016/verification_report.md`.
- **Frozen v1 portfolio verdict: Reject (20/100).** Realistic daily-marked
  portfolio (next-open fills, costs, constraints) over 10.3y: CAGR −0.45%,
  exposure-matched excess t ≈ −1.8 to −2.7, OOS Sharpe collapse. See
  `backtests/improved/final_verification_report.md` and
  `references/frozen_strategy_v1.md`. The programme is closed: no deployable
  edge in this data; further work requires new data + a new predeclared
  hypothesis.
- **Cross-sectional VCP leadership lifecycle: train reject (Trial 328–333,
  20/100 capped; 33/100 normalized raw).**
  The prespecified same-date 5d/20d active-VCP rank crossover produced 95
  train trades, 0.88% CAGR, 0.356 Sharpe and PF 1.359. Removing the five
  largest winners changed expectancy from +0.79% to -0.37%; the train gate
  failed and 2020–2021 internal holdout, formal validation and untouched OOS
  remained sealed. Dynamic relative leadership does not close the joint
  timing/exit oracle gap.
- **Signed path-efficiency lifecycle: train reject (Trial 334–339, 17/100).**
  A causal ER(10) crossover above +0.30 with pivot/SMA20 confirmation produced
  109 trades, -0.74% CAGR, -0.353 Sharpe and PF 0.895. Drop-top-five
  expectancy was -0.93%. Measuring a smooth intermediate price path rather
  than endpoint momentum did not identify continuation winners; holdout stayed
  sealed.
- **RS-line leadership lifecycle: train reject (Trial 340–344, 20/100 capped;
  33/100 normalized raw).** A
  causal 63-session stock/SPY RS-line high with price pivot/SMA20 confirmation
  produced 65 trades, 0.44% CAGR, 0.213 Sharpe and PF 1.208. Removing the five
  largest winners changed expectancy from +0.46% to -0.82%. SPY was
  benchmark-only and date-aligned at or before every stock date. The train
  gate failed; holdout, formal validation and untouched OOS stayed sealed.
- **Volatility squeeze-release lifecycle: train reject (Trial 345–351,
  17/100).** A causal prior-day bottom-20% Bollinger bandwidth squeeze followed
  by bandwidth expansion, an up-close and pivot confirmation produced 71
  trades, -0.05% CAGR, -0.018 Sharpe and PF 0.995. Drop-top-five expectancy
  was -1.20%. The stricter +2-sigma release was rejected outcome-free at only
  31 signals. Neither squeeze definition supports a robust continuation edge;
  holdout stayed sealed.
- **Detection-anchored VWAP reclaim lifecycle: train reject (Trial 352–357,
  20/100 capped; 51/100 normalized raw).** A causal typical-price/volume VWAP
  anchored on each setup's detection date, fresh below-to-above reclaim above
  the frozen pivot, and two-close AVWAP exit produced 85 trades, 1.62% CAGR,
  0.566 Sharpe and PF 1.386. Drop-top-five expectancy was -0.53%. The train
  gate failed, so internal holdout, formal validation and untouched OOS stayed
  sealed.
- **Chaikin Money Flow reclaim lifecycle: train reject (Trial 358–362,
  17/100).** A causal 20-session CMF zero cross above the frozen pivot, with a
  two-negative-close exit, produced 74 trades, -0.23% CAGR, -0.091 Sharpe and
  PF 0.975. Drop-top-five expectancy was -1.40%. Multi-session
  close-location-weighted volume did not improve the prior volume/Pocket Pivot
  failures; every later evidence partition stayed sealed.
- **Wilder DMI crossover lifecycle: train reject (Trial 363–367, 17/100).**
  A causal DMI(14) +DI/-DI crossover above the frozen pivot, with a two-close
  reverse-DMI exit, produced 80 trades, -0.80% CAGR, -0.350 Sharpe and PF
  0.921. Drop-top-five expectancy was -1.37%. The stricter ADX>20/rising
  definition had only one outcome-free signal. Validation and OOS stayed
  sealed.
- **Parabolic SAR flip lifecycle: train reject (Trial 368–373, 17/100).**
  A causal standard PSAR(0.02, 0.20) bullish close crossover above the frozen
  pivot, with a two-close bearish-PSAR exit, produced 98 trades, -0.86% CAGR,
  -0.331 Sharpe and PF 0.699. Drop-top-five expectancy was -1.66%.
  Validation and best-available OOS stayed sealed.
- **MACD signal-line lifecycle: outcome-free density reject (Trial 374–380).**
  The exact causal MACD(12,26,9) bullish crossover above zero and the frozen
  pivot emitted 79 pre-portfolio signals, below the predeclared minimum of 80.
  The threshold was not relaxed; no return or later partition was accessed.
- **Donchian price-channel lifecycle: outcome-free density reject (Trial
  381–386).** A canonical 55-session closing high above the frozen pivot with a
  20-session closing-low exit emitted 79 signals, below the same frozen minimum
  of 80. No return or later partition was accessed.
- **ATR range-expansion lifecycle: train reject (Trial 387–393, 17/100).** A
  1.5x prior-20 ATR bullish bar closing in the top quartile above the pivot,
  with a two-close EMA10 exit, produced 72 trades, -0.63% CAGR, -0.346 Sharpe
  and PF 0.817. Drop-top-five expectancy was -1.32%; validation/OOS stayed
  sealed.
- **Three-bar staircase lifecycle: train reject (Trial 394–399, 17/100).**
  Three rising closes and lows above the pivot, with a two-prior-low failure
  exit, produced 144 trades, -1.14% CAGR, -0.553 Sharpe and PF 0.700.
  Drop-top-five expectancy was -1.01%; later partitions stayed sealed.
- **Repeated MA20 touch lifecycle: train reject (Trial 400–405, 17/100).**
  Recycling fresh MA20 touch-and-hold entries after a pivot breakout, with a
  two-close SMA20 exit, produced 85 trades, -1.82% CAGR, -1.056 Sharpe and PF
  0.572. Drop-top-five expectancy was -1.84%. The known paired execution
  improvement does not become standalone alpha when recycled.
- **OBV accumulation lifecycle: train reject (Trial 406–411, 17/100).** A
  fresh 20-session On-Balance Volume high above the pivot, with a two-close
  OBV-EMA10 exit, produced 90 trades, -0.63% CAGR, -0.267 Sharpe and PF 0.704.
  Drop-top-five expectancy was -1.62%; cumulative signed volume does not
  rescue the prior volume failures. Validation/OOS stayed sealed.
- **Slow cross-sectional momentum: outcome-free density reject (Trial
  412–417).** Ranking canonical 12–1 momentum inside each active-VCP cohort and
  requiring the top quintile produced only 41 train signals versus the frozen
  minimum 80. No return or later partition was accessed; the rank threshold
  was not relaxed.
- **Log-price OLS trend quality: train reject (Trial 418–424, 20/100
  capped).** A causal 20-session log-close regression with positive slope,
  R-squared >=0.50 and frozen-pivot confirmation produced 79 train trades,
  0.30% CAGR, 0.138 Sharpe and PF 1.008. Drop-top-five expectancy was -1.06%.
  The reduced-denominator raw score was 29/100; unresolved survivorship capped
  it at 20. Validation and best-available OOS stayed sealed.
- **Aroon extreme recency: train reject (Trial 425–431, 20/100 capped).** A
  fixed 25-session recent-high/stale-low state above the pivot produced 75
  trades, 0.08% CAGR, 0.040 Sharpe and PF 1.022. Drop-top-five expectancy was
  -1.10%. The reduced-denominator raw score was 24/100 and survivorship-capped
  final score 20; validation/OOS stayed sealed.
- **Causal Ichimoku equilibrium: train reject (Trial 432–440, 17/100).** A
  zero-displacement 9/26/52 high-low-midpoint state above the current cloud and
  pivot produced 81 trades, -0.95% CAGR, -0.305 Sharpe and PF 0.868.
  Drop-top-five expectancy was -1.65%. Validation/OOS stayed sealed; do not
  retune the canonical windows or cloud threshold.
- **Realized semivariance asymmetry: train reject (Trial 441–447, 20/100
  capped).** A fixed 20-session upside/downside squared-return ratio with
  1.50/0.75 hysteresis produced 73 trades, -0.03% CAGR, 0.002 Sharpe and PF
  1.120. Untrimmed expectancy was positive but drop-top-five expectancy was
  -1.09%. Raw score 28, survivorship-capped final 20; later partitions sealed.
- **Gap-adjusted intraday follow-through: train reject (Trial 448–454, 20/100
  capped).** A fixed 10-session regular-session-vs-overnight log-return state
  produced 125 trades, 0.33% CAGR, 0.153 Sharpe and PF 1.050. Drop-top-five
  expectancy was -0.57%. Raw score 29, capped final 20; validation/OOS sealed.
- **Oracle exit residual audit: diagnostic only, never scoreable.** On 90
  future-profitable perfect-timing train paths, 84.4% of closes before the best
  next-open exit were fresh five-day closing highs in both halves and after
  trim-5. Weakness proxies covered <=11.1%. This can motivate exactly one
  frozen sell-into-strength test; it is lookahead evidence, not a strategy.
- **AVWAP + delayed five-day-high exit: train reject (Trial 455–466, 20/100
  capped).** The sole oracle-generated translation produced 83 trades, 0.17%
  CAGR, 0.085 Sharpe, PF 1.009 and -0.90% trim-5 expectancy. Raw score 35,
  capped final 20. Validation/OOS stayed sealed; do not retune high/arm windows.
- **PIT membership tenure: outcome-free reject (Trial 467–470).** Fixed
  90/180/365/730-day start-tenure caps emitted 0/0/4/11 signals versus the
  frozen minimum 80. Membership end was verification-only; no P&L was opened.
- **Gap rejection/reclaim: outcome-free reject (Trial 471–477).** A >=1%
  gap-up bearish rejection followed by a five-session strict reclaim of its
  high and the pivot emitted 27 signals across 21 symbols. No return,
  validation or OOS partition was opened; do not relax the frozen rule.
- **Month-start flow: train reject (Trial 478–482, 17/100).** SPY was
  calendar/benchmark-only. A first-monthly-session close above pivot, next-open
  entry and three-session exit produced 99 trades, -0.32% CAGR, -0.220 Sharpe,
  PF 0.750 and -0.56% trim-five expectancy. A/B/C/D = 7/7/0/0; validation/OOS
  stayed sealed.
- **Lag-1 serial dependence: train reject (Trial 483–488, 20/100 capped).**
  A fixed 20-return autocorrelation zero cross produced 103 trades, 1.29% CAGR,
  0.499 Sharpe and PF 1.515, but trim-five PF/expectancy fell to 0.715/-0.47%.
  A/B/C/D = 7/10/4/14, raw 42, final 20; validation/OOS stayed sealed.
- **SEC share-supply contraction: train reject (Trial 489–495, 20/100
  capped).** Existing cached same-accession diluted/basic weighted shares
  covered 78/79 train symbols and emitted 114 signals. One hundred trades
  returned 0.69% CAGR, 0.291 Sharpe, PF 1.025 and -0.57% trim-five expectancy.
  A/B/C/D = 7/7/4/6, raw 29, final 20; no external data or later partition.
- **Data caveats**: legacy CSV and R2K pattern-level universes are
  survivorship-biased (R2K lost 26% of names), with close-based fills and no
  costs. Newer portfolio reports include costs and next-session execution but
  are still non-qualifying unless their own PIT coverage, frozen chronology
  and untouched-OOS contract are satisfied.
