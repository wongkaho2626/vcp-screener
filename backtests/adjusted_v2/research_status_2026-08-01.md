# VCP Strategy Research Status — 2026-08-01

## Decision

**Goal not complete.** No frozen rule has passed the internal discovery gate,
so formal validation and untouched OOS remain sealed. The amended goal no
longer requires Backtest Score >80; it requires transparent raw A/B/C/D and
hard-cap reporting. Net OOS CAGR >=20% remains unproved and is contradicted by
the available exploratory replay.

The corrected frozen pivot-retest baseline has Backtest Score **41/100**, net
CAGR **0.64%**, and 94 trades. Trial 288's previously reported 5.58% CAGR is
invalidated by a newly discovered historical benchmark-alignment defect: SPY
was sliced by each stock's integer offset rather than its as-of date. The
date-aligned 2020–2021 reconstruction produced 40 trades and **4.82% CAGR**, but
failed both the 15% CAGR gate and drop-top-five robustness.

## Corrected infrastructure and coverage

- Raw/adjusted OHLC mismatches were repaired so detection and portfolio
  execution use the same adjusted scale.
- A detection whose as-of close is already below its frozen stop is rejected.
- Signals confirmed at a close fill no earlier than the next open.
- Historical relative strength now aligns SPY by date at or before the stock's
  as-of session. This removes future benchmark bars for short/gapped histories
  and restores truncation invariance; regression tests cover the defect.
- PIT S&P 500 price coverage is 599/720 union names and 91.31% overall; SPY is
  present only as benchmark.
- Current SEC ticker mapping covers 576/599 priced PIT names. The 23 unmapped
  legacy names represent 21,236 of 1,152,014 member trading days, giving 98.16%
  mapped member-day coverage on the priced sample.
- Among 738 PIT detections in 2016–2021, 713 (96.61%) have cached SEC facts,
  645 (87.40%) have a prior strictly as-filed same-accession EPS/revenue event,
  and 501 (67.89%) have one no more than 120 days old.

## New orthogonal trials

All rows below are prespecified discovery results (train or 2020–2021 internal
holdout as labelled), net of the unchanged 5 bps commission plus 5 bps
slippage on each side. Formal validation and untouched OOS were not accessed.

| Trial | Hypothesis | Trades | CAGR | Sharpe | PF | MDD | Trim-5 expectancy | Gate |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 296 | p70 timing + fresh SEC EPS>=20% and revenue>=10% | 21 | 1.76% | 0.690 | 1.876 | -2.00% | -1.47% | fail |
| 297–299 | p70 loss-decay + 10%/3xATR chandelier | 72 | 2.78% | 0.606 | 1.251 | -3.46% | -1.18% | fail |
| 300–302 | setup-balanced k=15 nonlinear analogues | 145 | -1.96% | -0.575 | 0.810 | -6.96% | -0.69% | fail |
| 303–304 | first VCP state <=30d after dual-growth filing, fixed-20 exit | 30 | 1.26% | 0.402 | 1.198 | -2.90% | -1.91% | fail |
| 305–307 | last-contraction undercut/reclaim | 21 train | 1.04% train | 1.148 | 4.012 | -1.35% | +0.34% | train fail; holdout sealed |
| 308–309 | hard-stop survival classifier, p70 | 65 | -1.82% | <0.75 | <1.20 | -6.42% | negative | fail |
| 310–311 | positive fixed-20 classifier, p70 | 67 | -2.37% | <0.75 | <1.20 | -6.28% | negative | fail |
| 312 | expanded 2016–2018 fit, same forward-20 ridge | 60 | 2.09% | <0.75 | >1.20 | -3.29% | negative | fail |
| 313–315 | p70 prove-it exit + reset/re-entry lifecycle | 99 | 1.35% | 0.320 | 1.288 | -5.35% | -0.70% | fail |
| 316–319 | RSI(2)<10 + SMA(5)/five-session lifecycle | 214 train | -0.72% train | -0.442 | 0.976 | -4.94% | -0.20% | train fail; holdout sealed |
| 320–323 | 12–1 positive + five-day momentum cross, SMA20 lifecycle | 158 train | -1.35% train | <0.75 | <1.20 | -4.40% | negative | train fail; holdout sealed |
| 324–327 | prior-SMA20 opening limit + full-gap recovery | 80 train | 0.07% train | <0.75 | <1.20 | -2.12% | negative | train fail; holdout sealed |
| 328–333 | active-VCP 5d/20d cross-sectional leadership lifecycle | 95 train | 0.88% train | 0.356 | 1.359 | -3.81% | -0.37% | train fail; holdout sealed |
| 334–339 | signed ER(10) path-efficiency crossover lifecycle | 109 train | -0.74% train | -0.353 | 0.895 | -3.67% | -0.93% | train fail; holdout sealed |
| 340–344 | 63-session stock/SPY RS-line high lifecycle | 65 train | 0.44% train | 0.213 | 1.208 | -3.24% | -0.82% | train fail; holdout sealed |
| 345–351 | Bollinger bandwidth squeeze-release lifecycle | 71 train | -0.05% train | -0.018 | 0.995 | -2.61% | -1.20% | train fail; holdout sealed |
| 352–357 | detection-anchored VWAP reclaim lifecycle | 85 train | 1.62% train | 0.566 | 1.386 | -5.21% | -0.53% | train fail; holdout sealed |
| 358–362 | 20-session Chaikin Money Flow zero-cross lifecycle | 74 train | -0.23% train | -0.091 | 0.975 | -5.07% | -1.40% | train fail; holdout sealed |

Trial 303–304 is an explicit discovery-collapse check: its fit sample had only
13 setups, 12 positive, with mean fixed-20 label +4.54%; the untouched internal
holdout fell to +0.59% trade expectancy and 1.26% portfolio CAGR. This is not
evidence of a durable edge.

## Structural evidence

- Fixed causal daily entries, even with perfect future exits, peak at 18.72%
  train CAGR, below the required 20%; joint future entry and exit selection can
  reach 31.34%, proving that timing/exit—not sizing—would have to provide the
  missing edge.
- High-threshold linear timing remains too sparse after benchmark alignment
  (Trial 288 reconstruction: 4.82% CAGR, 40 trades) and loses drop-top-five
  stability. Lower thresholds raise trade count without creating durable edge.
- A trailing exit raises average winner size but still fails after removing the
  five largest winners.
- A high-density nonlinear analogue model produces negative expectancy,
  rejecting the idea that simple local interactions in the existing fifteen
  causal technical features recover the oracle gap.
- Strictly as-filed SEC growth data is usable at reasonable coverage, but both
  the permanent dual-growth gate and the fresh-filing timing rule fail out of
  sample.
- Complete SEC Form 4 classification parsed 4,353/4,353 candidate XML files;
  only 25 independent 2020–2021 purchase filings touched 16 active setups, so
  the direction failed the 30-independent-trade coverage gate without outcomes.
- A shakeout entry produced strong train trade-level PF but only 1.04% CAGR at
  fixed sizing; higher-density survival and positive-return classifiers both
  turned negative, confirming that density without upside separation is not a
  solution.
- Expanding the recent fit window increased sample size but reduced the
  original sparse ridge edge to 2.09% CAGR; more rows did not cure the
  train-to-holdout ranking problem.
- A higher-density prove-it/reset lifecycle reached 99 trades but only 1.35%
  CAGR and depended on its five largest winners. RSI(2) mean reversion raised
  train density to 214 trades but had negative CAGR and PF below one. Turnover
  alone does not supply the missing expectancy.
- Dynamic dual momentum produced 158 train trades but -1.35% CAGR. Combining
  positive 12–1 momentum, a fresh five-day momentum crossing, SMA20 exits and
  three-attempt recycling does not close the joint timing/exit oracle gap.
- A causal one-session opening limit at the prior SMA20 produced 80 train
  trades, but waiting for complete gap recovery earned only 0.07% CAGR and
  failed PF/trim stability. Execution price concessions alone are not an edge.
- Same-date 5d/20d active-VCP leadership rankings produced a positive headline
  PF but only 0.88% train CAGR; removing the five largest winners reversed
  expectancy. Cross-sectional leadership did not make the causal selector
  robust enough to approach the joint timing/exit oracle.
- Signed ten-session path efficiency produced negative CAGR and PF below one;
  distinguishing smooth from choppy endpoint-equivalent moves did not recover
  the missing continuation edge.
- A causal 63-session RS-line high produced PF just above 1.20 but only 0.44%
  CAGR, 0.213 Sharpe and negative trim-5 expectancy. Dynamic benchmark-relative
  leadership remains dependent on a handful of winners.
- A prior-day bottom-20% Bollinger bandwidth squeeze followed by directional
  expansion produced approximately zero CAGR and PF below one. Explicitly
  measuring the contraction-to-expansion transition does not rescue VCP entry
  timing.
- A causal typical-price/volume VWAP anchored on each setup's detection date
  produced the strongest recent headline PF (1.386) but only 1.62% CAGR and
  0.566 Sharpe. Removing the five largest winners reversed expectancy to
  -0.53%; an institutional-cost-basis reclaim remains outlier-dependent.
- A 20-session Chaikin Money Flow zero cross above the frozen pivot produced
  negative CAGR, PF below one and -1.40% trim-5 expectancy. Aggregating
  close-location-weighted volume across multiple sessions does not rescue the
  previously failed isolated volume and Pocket Pivot directions.
- Additional fit/coverage audits rejected initial SC 13D/13G ownership events,
  non-earnings 8-K catalysts, cash-conversion quality, and the full Stage-2
  trend template. Either independent-event density was below 30 or fixed-20
  expectancy became negative after removing the five largest labels.

## Reproducibility and integrity

- Frozen specifications precede every outcome evaluation.
- Commands are recorded in `backtests/v2_research_commands.md`.
- Each evaluated rule has timestamped JSON, Markdown, trade CSV, and daily
  equity CSV outputs.
- SEC-derived events preserve filing/accession dates and require
  `filed < signal_date`; same-day filings cannot trigger an entry.
- Full test suite after Trial 358–362: **424 passed**.
  `git diff --check`: clean.

No current rule meets the research gate. Independently, completion remains
externally blocked: this workspace has no survivorship-safe 2000–2005 daily
price/security-master dataset, no configured CRSP/WRDS access, and the available
2006–2015 PIT reconstruction covers only 69.74% of member-days. The amended
goal permits the resulting score cap, but it does not waive point-in-time,
delisted-name or untouched-OOS evidence; those requirements still cannot be
demonstrated with the available data. See `completion_blocker_audit.md` for the
exact evidence and unblock contract.
The requirement-by-requirement verdict is recorded in
`completion_matrix_2026-08-01.md`.

## User-requested existing-data exploratory replay

At the user's explicit direction, Trial 288 was replayed on the existing
2022-01-01 through 2026-03-31 data without treating the period as untouched
OOS. The rule, sizing, costs and entry/exit timing stayed frozen; the run was
declared exploratory before outcomes and cannot authorise formal validation.

- 125 signals, 89 executed trades;
- net CAGR **0.05%**, total return 0.19%, Sharpe 0.031, Sortino 0.045;
- PF 1.059, MDD -6.81%, raw Backtest Score **25/100**;
- drop-top-five expectancy -1.71%; 2x-cost CAGR -0.11%;
- all neighbouring sensitivity cells returned between -0.92% and +0.87% CAGR
  and every cell had negative drop-top-five expectancy;
- chronological folds: +1.15% CAGR in 2022–2023 and -0.80% in 2024–2026.

The replay fails the 20% CAGR requirement before any survivorship cap. Full
evidence is in `backtests/exploratory_existing_data_replay/results/`.

## Public data-source audit

- The Stooq CSV endpoint returned a JavaScript verification page in this
  environment rather than price rows.
- A 20-symbol Yahoo probe returned full 2000–2005 data for seven names but no
  data for 13 legacy/delisted examples including AAMRQ, ABKFQ, ADCT, ENRNQ,
  HET and WCOM.
- The 2026 Arandkei delisted archive contains only 20 symbols; MEL is its sole
  overlap with the 2000–2005 PIT S&P 500 membership file.
- The CC0 Huge Stock Market archive has 7,195 stock files but matches only
  404/640 historical S&P symbols. Exact 2000–2005 member-day coverage is
  **58.35%**, rising from 51.52% to 65.56% by year. Quandl WIKI's 3,199-symbol
  ticker list matches 415/640 (64.84%) before any price-quality audit.

These sources were rejected outcome-free. The machine-readable audit and
SHA-256 are in `backtests/data_source_audit/public_oos_coverage.json`.
