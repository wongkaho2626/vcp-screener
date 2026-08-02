# VCP Strategy Research Status — 2026-08-01

## Decision

**Goal not complete.** No frozen rule has passed the internal discovery gate,
so 2019–2021 validation and the 2022–2026Q1 best-available frozen OOS remain
sealed. The current goal uses only repository-local 2006+ evidence and no
longer searches or requires 2000–2005 PIT data. Backtest Score has no minimum,
but raw A/B/C/D and every hard cap remain mandatory. Net OOS CAGR >=20% remains
unproved and is contradicted by the available exploratory replay.

The corrected frozen pivot-retest baseline has Backtest Score **41/100**, net
CAGR **0.64%**, and 94 trades. Trial 288's previously reported 5.58% CAGR is
invalidated by a newly discovered historical benchmark-alignment defect: SPY
was sliced by each stock's integer offset rather than its as-of date. The
date-aligned 2020–2021 reconstruction produced 40 trades and **4.82% CAGR**, but
failed both the 15% CAGR gate and drop-top-five robustness.

## Corrected infrastructure and coverage

- Raw/adjusted OHLC mismatches were repaired so detection and portfolio
  execution use the same adjusted scale.
- An outcome-free inventory found 33 impossible source OHLC envelopes. The
  shared detector/portfolio transform now expands adjusted high/low to contain
  open, close and the original range; parity and causality tests cover it.
- A detection whose as-of close is already below its frozen stop is rejected.
- Signals confirmed at a close fill no earlier than the next open.
- Historical relative strength now aligns SPY by date at or before the stock's
  as-of session. This removes future benchmark bars for short/gapped histories
  and restores truncation invariance; regression tests cover the defect.
- PIT S&P 500 price coverage is 599/720 union names and 91.31% overall; SPY is
  present only as benchmark.
- The only executable raw price inputs begin on 2014-01-02 and support signals
  from 2016 onward. The prior 2006–2015 reconstruction remains available only
  as a 69.74%-coverage report, not a runnable price CSV. The frozen
  best-available chronology and contamination registry are in
  `backtests/current_2006_plus_data_audit/`.
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
| 363–367 | Wilder DMI(14) crossover lifecycle | 80 train | -0.80% train | -0.350 | 0.921 | -6.78% | -1.37% | train fail; validation/OOS sealed |
| 368–373 | Parabolic SAR(0.02, 0.20) flip lifecycle | 98 train | -0.86% train | -0.331 | 0.699 | -4.97% | -1.66% | train fail; validation/OOS sealed |
| 374–380 | MACD(12,26,9) signal-line lifecycle | 79 signals | — | — | — | — | — | outcome-free density fail; returns/OOS sealed |
| 381–386 | Donchian 55/20 closing-channel lifecycle | 79 signals | — | — | — | — | — | outcome-free density fail; returns/OOS sealed |
| 387–393 | 1.5x ATR bullish range-expansion lifecycle | 72 train | -0.63% train | -0.346 | 0.817 | -4.71% | -1.32% | train fail; validation/OOS sealed |
| 394–399 | Three-bar rising-close/rising-low staircase | 144 train | -1.14% train | -0.553 | 0.700 | -4.90% | -1.01% | train fail; validation/OOS sealed |
| 400–405 | Repeated MA20 touch-and-hold lifecycle | 85 train | -1.82% train | -1.056 | 0.572 | -5.32% | -1.84% | train fail; validation/OOS sealed |
| 406–411 | 20-session OBV accumulation-breakout lifecycle | 90 train | -0.63% train | -0.267 | 0.704 | -4.93% | -1.62% | train fail; validation/OOS sealed |
| 412–417 | Active-VCP cohort 12–1 momentum top quintile | 41 signals | — | — | — | — | — | outcome-free density fail; returns/OOS sealed |
| 418–424 | 20-session log-price OLS trend-quality lifecycle | 79 train | 0.30% train | 0.138 | 1.008 | -5.57% | -1.06% | train fail; validation/OOS sealed |
| 425–431 | 25-session Aroon extreme-recency lifecycle | 75 train | 0.08% train | 0.040 | 1.022 | -5.83% | -1.10% | train fail; validation/OOS sealed |
| 432–440 | Causal Ichimoku 9/26/52 range-midpoint equilibrium | 81 train | -0.95% train | -0.305 | 0.868 | -7.01% | -1.65% | train fail; validation/OOS sealed |
| 441–447 | 20-session realized semivariance asymmetry | 73 train | -0.03% train | 0.002 | 1.120 | -6.04% | -1.09% | train fail; validation/OOS sealed |
| 448–454 | 10-session gap-adjusted intraday follow-through | 125 train | 0.33% train | 0.153 | 1.050 | -4.85% | -0.57% | train fail; validation/OOS sealed |
| 455–466 | AVWAP reclaim + delayed fresh five-day-high exit | 83 train | 0.17% train | 0.085 | 1.009 | -4.91% | -0.90% | train fail; validation/OOS sealed |
| 467–470 | PIT membership-tenure caps of 90/180/365/730 days | 0/0/4/11 signals | — | — | — | — | — | outcome-free density fail; returns/OOS sealed |
| 471–477 | Gap-up rejection then five-session high+pivot reclaim | 27 signals | — | — | — | — | — | outcome-free density fail; returns/OOS sealed |
| 478–482 | First-session-of-month flow, three-session exit | 99 train | -0.32% train | -0.220 | 0.750 | -2.90% | -0.56% | train fail; validation/OOS sealed |
| 483–488 | 20-return lag-1 autocorrelation zero-cross lifecycle | 103 train | 1.29% train | 0.499 | 1.515 | -4.32% | -0.47% | train fail; validation/OOS sealed |
| 489–495 | SEC weighted-average-share contraction, fixed-20 exit | 100 train | 0.69% train | 0.291 | 1.025 | -3.30% | -0.57% | train fail; validation/OOS sealed |
| 496–504 | Strong trend -> character damage -> resistance-flip/swing-low exit | 88 train | 0.50% train | 0.228 | 0.982 | -3.26% | -0.87% | train fail; validation/OOS sealed |
| 505–519 | Positive 20d stock-minus-SPY confirmation gate | 23 train / 64 validation / 101 best-available OOS | 0.75% / 2.52% / -2.16% | 0.439 / 0.602 / -0.566 | 1.330 / 1.743 / 0.586 | -2.05% / -7.74% / -12.03% | -3.27% / 0.54% / -3.49% | confirmatory density fail; later cells descriptive only; INCONCLUSIVE |
| 520 | Close above SMA50 + positive 20-session SMA50 slope | 26 train / 78 validation / 111 best-available OOS | 1.36% / 1.14% / -2.81% | 0.574 / 0.292 / -0.725 | 1.498 / 1.313 / 0.621 | -3.91% / -8.65% / -14.25% | -1.97% / -0.77% / -3.22% | fixed three-fold test; INCONCLUSIVE / practical reject |
| 521 | Positive stock MA50 slope above aligned SPY MA50 slope | 20 train / 60 validation / 94 best-available OOS | 0.84% / 1.28% / -2.89% | 0.383 / 0.363 / -0.787 | 1.368 / 1.526 / 0.541 | -3.94% / -7.16% / -14.46% | -2.95% / -0.50% / -3.92% | stock-selection excess worsened OOS; INCONCLUSIVE / practical reject |
| 522–541 | MA10–200 relative-slope train grid, step 10 | best raw MA60: 17 train; >=20-trade leader MA20: 23 | 1.95% MA60 / 1.13% MA20 | 0.873 / 0.593 | 2.910 / 1.478 | -1.17% / -3.06% | -0.45% / -2.12% | zero all-gates winners; validation/OOS sealed |
| 542 | Standalone relative-MA60 rising-edge entry; no VCP/MA20/Edge Rank | 108 train / 218 validation / 305 best-available OOS | 21.17% / 6.27% / 4.88% | 1.643 / 0.411 / 0.357 | 2.874 / 1.312 / 1.222 | -10.81% / -35.61% / -25.52% | 3.24% / 0.37% / -0.03% | train collapse; materially trails SPY; WORSENS |
| 543 | Same standalone MA60 entry; remove timeout, 8% close-watermark trail | 112 train / 235 validation / 411 best-available OOS | 8.66% / 7.38% / -6.37% | 0.775 / 0.502 / -0.333 | 1.671 / 1.415 / 0.797 | -19.45% / -27.03% / -35.39% | -0.20% / 0.51% / -1.55% | latest CAGR/excess/MDD/cost all worsen; WORSENS |
| 544 | Same standalone MA60 entry; 8% hard stop until +3R, then 24% close trail; no timeout | 18 train / 48 validation / 99 best-available OOS | 13.40% / 6.72% / 6.22% | 1.049 / 0.437 / 0.442 | 7.692 / 2.271 / 1.605 | -13.75% / -32.96% / -23.12% | 3.51% / 0.00% / -1.61% | improves latest CAGR/MDD/cost but fails trim-five; INCONCLUSIVE |
| 545–550 | Standalone MA10–60 buy grid; Trial 544 exit frozen | MA40/50/60 train pass; MA60 selected, 18 train / 48 validation | 13.40% / 6.72% | 1.049 / 0.437 | 7.692 / 2.271 | -13.75% / -32.96% | 3.51% / 0.00% | validation excess CAGR -11.04% and MDD fail; OOS sealed; VALIDATION_FAIL |
| 551–568 | 18 user-supplied MA60 fill-date windows; exit unchanged | 16 train / 47 validation / 49 descriptive OOS | 13.56% / 8.34% / 10.08% | 1.078 / 0.506 / 0.743 | 8.704 / 2.598 / 2.972 | -12.54% / -31.59% / -14.17% | 4.44% / 0.34% / 2.22% | OOS excess CAGR worsens to -7.32%; 11/18 windows untestable; DESCRIPTIVE_ONLY |
| 569–572 | MA60 slope-window grid 10/20/30/40 inside supplied calendar | slope10 selected; 18 train / 44 validation | 19.21% / 13.53% | 1.362 / 0.768 | 8.679 / 3.715 | -9.35% / -28.86% | 4.70% / -1.08% | validation excess CAGR -6.93% and trim fail; OOS sealed; VALIDATION_FAIL |
| 573 | Current slope10 plus forced opening exit outside calendar | 18 train / 46 validation / 92 contaminated OOS | 19.71% / 16.61% / 15.34% | 1.554 / 1.023 / 1.124 | 10.052 / 4.354 / 2.885 | -8.89% / -16.73% / -10.81% | 8.45% / 3.84% / 3.49% | full CAGR 16.39%, full excess CAGR -2.96%; post-hoc and no untouched OOS; score 20/100; DESCRIPTIVE_ONLY |
| 574 | Remove only forced period exit; calendar gates entries only | 18 train / 44 validation / 51 contaminated OOS | 19.21% / 13.53% / 12.27% | 1.362 / 0.768 / 0.869 | 8.679 / 3.715 / 3.424 | -9.35% / -28.86% / -14.60% | 4.70% / -1.08% / 2.18% | full CAGR 15.16%, MDD -27.24%; worse portfolio performance; score 20/100; DESCRIPTIVE_ONLY |
| 575 | QQQ-synchronized regime: end date is exit open and entry-ineligible | 18 train / 46 validation / 91 contaminated OOS | 20.08% / 18.97% / 15.66% | 1.598 / 1.149 / 1.147 | 10.098 / 4.988 / 2.962 | -8.89% / -16.73% / -10.81% | 8.38% / 5.06% / 3.56% | full CAGR 17.33%, MDD -18.16%; improves absolute/risk metrics, excess remains negative; score 20/100; DESCRIPTIVE_ONLY |
| 576 | MA60/slope10 no-QQQ-regime control | 24 train / 45 validation / 95 contaminated OOS | 17.76% / 12.22% / 11.01% | 1.208 / 0.695 / 0.727 | 5.624 / 3.392 / 2.076 | -12.83% / -30.67% / -19.89% | 1.45% / -1.35% / 0.01% | full CAGR 14.46%, MDD -29.84%; confirms QQQ overlay is market-timing/risk improvement; score 20/100 |

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
- A Wilder DMI(14) positive-direction crossover emitted 80 trades but produced
  -0.80% CAGR, -0.350 Sharpe and PF below one. The stricter ADX>20/rising
  ignition emitted only one outcome-free signal. Directional-movement strength
  does not identify the missing continuation edge.
- A standard Parabolic SAR bullish flip emitted 98 trades but produced -0.86%
  CAGR, -0.331 Sharpe and PF 0.699. Removing the five largest winners reduced
  expectancy to -1.66%. A path-dependent stop-and-reverse trend state does not
  recover the missing continuation edge.
- A standard MACD(12,26,9) bullish crossover above zero and the frozen pivot
  emitted 79 pre-portfolio discovery signals, one below its frozen minimum of
  80. The family was rejected outcome-free and the threshold was not relaxed.
- A canonical Donchian 55-session closing high above the frozen pivot, paired
  with a 20-session closing-low exit, also emitted 79 pre-portfolio signals.
  It was rejected under the unchanged density rule without viewing returns.
- A bullish bar with at least 1.5x prior-20 ATR, a top-quartile close and pivot
  confirmation passed density but produced -0.63% CAGR, -0.346 Sharpe and PF
  0.817 across 72 trades. Removing the five largest winners reduced expectancy
  to -1.32%; large price displacement alone does not identify continuation.
- Three consecutive rising closes and lows above the pivot generated 144
  trades but -1.14% CAGR, -0.553 Sharpe and PF 0.700. An orderly short-term
  price staircase is common enough but has negative continuation expectancy.
- Recycling the historically validated MA20 touch-and-hold execution overlay
  after pivot breakouts produced -1.82% CAGR, -1.056 Sharpe and PF 0.572 across
  85 trades. Removing five winners cut expectancy to -1.84%. A positive paired
  entry-price improvement versus chasing does not create standalone alpha or
  justify repeated exposure.
- A fresh 20-session On-Balance Volume high above the pivot produced -0.63%
  CAGR, -0.267 Sharpe and PF 0.704 across 90 trades. Removing five winners cut
  expectancy to -1.62%. Cumulative close-direction-signed volume confirms the
  broader negative evidence from breakout volume, Pocket Pivot and CMF.
- Canonical 12–1 momentum ranked inside the contemporaneous active-VCP cohort
  produced only 41 top-quintile lifecycle signals. The slow factor and the
  short-lived VCP opportunity set have insufficient overlap for the fixed
  portfolio gate; returns were never opened and thresholds were not relaxed.
- A positive 20-session log-close regression slope with R-squared at least
  0.50 emitted 106 signals and 79 portfolio trades, but produced only 0.30%
  CAGR, 0.138 Sharpe and PF 1.008. Removing the five largest winners reduced
  expectancy to -1.06%. Linear trend smoothness is sufficiently dense but
  does not isolate robust continuation after the frozen pivot.
- A 25-session Aroon recent-high/stale-low state emitted 101 signals and 75
  trades, but produced only 0.08% CAGR, 0.040 Sharpe and PF 1.022. Removing
  the five largest winners reduced expectancy to -1.10%. Extreme recency is
  mechanically distinct from move magnitude but still fails to isolate
  continuation after the pivot.
- A causal, zero-displacement Ichimoku 9/26/52 range-midpoint state emitted
  115 signals and 81 trades, but produced -0.95% CAGR, -0.305 Sharpe and PF
  0.868. Removing the five largest winners reduced expectancy to -1.65%.
  Multi-horizon high-low equilibrium does not rescue the failed trend family;
  its canonical windows are closed under the frozen give-up rule.
- A fixed 20-session upside/downside semivariance ratio emitted 104 signals
  and 73 trades. Untrimmed expectancy was +0.41%, but fixed-portfolio CAGR was
  -0.03%, Sharpe 0.002 and PF 1.120; removing five winners reduced expectancy
  to -1.09%. Sign-separated return energy remains outlier-dependent and does
  not provide the missing portfolio edge.
- A fixed 10-session decomposition of regular-session and overnight log
  returns emitted 164 signals and 125 trades, but produced only 0.33% CAGR,
  0.153 Sharpe and PF 1.050. Removing five winners reduced expectancy to
  -0.57%. Avoiding gap-led moves while requiring positive intraday drift still
  does not identify robust continuation.
- A non-deployable train-only oracle-exit residual audit reconstructed 90
  positive perfect-timing paths. Fresh five-day closing highs occurred before
  84.4% of oracle next-open exits (84.6% early fold, 84.2% late fold, 84.7%
  after drop-top-five), while down-close, SMA10-break and 5% giveback states
  covered only 11.1%, 5.6% and 1.1%. This does not receive a score or authorise
  validation; it only motivates one separately frozen sell-into-strength test.
- That one disclosed oracle-generated translation paired the prior AVWAP
  reclaim with a 10-session-armed fresh five-day-high exit. It produced 83
  trades but only 0.17% CAGR, 0.085 Sharpe and PF 1.009; removing five winners
  reduced expectancy to -0.90%. The causal first occurrence is not equivalent
  to selecting the future-best occurrence, so the strength-exit direction is
  closed without retuning its window or arm.
- A start-date-only PIT membership-tenure audit found 0, 0, 4 and 11
  detection-entry candidates inside fixed 90, 180, 365 and 730 calendar-day
  caps. All were below the unchanged 80-signal minimum. Membership end dates
  were used only to verify signal/fill membership, never as features; no
  return partition was opened and the family was closed outcome-free.
- A separately frozen supply-absorption entry required a >=1% gap-up bearish
  rejection followed within five sessions by a strict close above the frozen
  rejection high and VCP pivot. Only 27 signals across 21 symbols survived
  from 4,165 active setup rows. The 80-signal density gate failed before P&L,
  so the gap threshold, reclaim window and three-attempt lifecycle were not
  relaxed and all later evidence stayed sealed.
- A calendar-flow lifecycle used SPY only to identify observed month
  transitions, required the completed first-session close above the frozen
  pivot, entered next open and exited three sessions later. Density passed at
  143 signals, but 99 executed train trades produced -0.32% CAGR, -0.220
  Sharpe, PF 0.750 and -0.56% trim-five expectancy. Its A/B/C/D scores were
  7/7/0/0, normalized raw and final score 17/100 (Reject); validation and OOS
  stayed sealed. Month-start allocation flow does not rescue active VCPs.
- A canonical 20-return lag-1 autocorrelation zero cross tested order-splitting
  persistence rather than trend magnitude. It produced 129 signals and 103
  trades with 1.29% CAGR, 0.499 Sharpe and PF 1.515, but removing the five
  largest winners reversed PF to 0.715 and expectancy to -0.47%. Its t-stat
  was 0.78, PSR 77.9% and approximate DSR probability 0.08%. A/B/C/D were
  7/10/4/14, normalized raw 42 and survivorship-capped final 20/100 (Reject).
  The train gate failed; window, lag and zero threshold are closed.
- A strictly as-filed SEC share-supply contraction proxy used same-accession
  weighted-average shares, diluted-before-basic priority, latest filing <
  signal date and fixed 120-day freshness. Existing cache coverage was 78/79
  requested train symbols with 4,755 comparable events. The lifecycle emitted
  114 signals and 100 trades, but only 0.69% CAGR, 0.291 Sharpe and PF 1.025;
  trim-five PF/expectancy fell to 0.759/-0.57%. A/B/C/D were 7/7/4/6,
  normalized raw 29 and final survivorship-capped score 20/100 (Reject).
  Coverage was adequate; the economic rule failed before validation.
- A supplied strong-stock exit checklist was translated before outcomes into
  a reproducible state machine: arm only after persistent SMA10/SMA20 support,
  then exit next open on a 6% gap-down / 16% close loss, a frozen five-session
  swing-low break, or a failed recovery into the frozen MA cluster after dual-
  MA damage. Fifty-eight of 103 baseline paths activated, but only one was an
  abnormal day and ten were failed-MA recoveries; 47 were swing-low breaks.
  The 88 trades returned 0.50% CAGR, 0.228 Sharpe, PF 0.982 and -0.87%
  trim-five expectancy. A/B/C/D were 7/7/4/0, normalized raw 22 and final 20
  after the survivorship cap. The ordered character-change claim failed train
  and is closed without relaxing its thresholds or opening later partitions.
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
- Full test suite after Trial 572 and the 2006+ inventory repair:
  **617 passed** after the QQQ regime provenance and synchronized-execution
  audit.
  `git diff --check`: clean.

No current rule meets the research gate. Missing 2000–2005 data is explicitly
out of scope and is no longer a blocker. All available 2006+ periods are
contaminated by prior research, so a genuinely new rule may use the frozen
2022–2026Q1 segment only as capped best-available OOS after passing train and
validation. See `completion_blocker_audit.md` for the current evidence boundary.
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
