# Outcome-Free Remaining-Hypothesis Audit — after Trial 431

Status: recorded **before Trial 432–440 density or return evaluation** on
2026-08-01. This document uses prior experiment descriptions and indicator
mechanics only; it does not inspect new outcomes.

## Closed or heavily duplicated families

| Family | Existing evidence | Decision |
|---|---|---|
| Price magnitude / momentum | multi-horizon returns, 12–1 and 5d/20d cross-sectional momentum, MACD, DMI | Do not retest minor lookback variants |
| Trend path / persistence | signed efficiency ratio, three-bar staircase, PSAR, OLS slope/R-squared, Aroon recency | Do not add CCI, TSI or generic slope variants |
| Channel / breakout location | pivot breakout/retest, Donchian 55/20, 52-week high, gap, ATR expansion | Do not add a nearby channel length post hoc |
| Short-horizon oscillator / mean reversion | RSI(2), undercut/reclaim, five-day low/reversal families | Stochastic and Williams %R are near-duplicates |
| Volatility transition | contraction geometry, Bollinger squeeze/release, ATR expansion, narrow/inside-day work | Keltner/Choppiness variants are insufficiently orthogonal |
| Volume / accumulation | volume dry-up, breakout volume, Pocket Pivot, anchored VWAP, CMF, OBV | Do not add PVT, MFI or A/D oscillator variants |
| Moving-average / support execution | MA10/20/50 exits, MA20 touch, open-limit recovery, support/pivot retests | Do not recycle another simple MA length |
| Fundamental / filing events | causal EPS/revenue growth, filing freshness, margin and cash-quality audits, Form 4, 13D/G, 8-K | Remaining variants are sparse or post-hoc |
| Portfolio / sizing / regime | sizing is fixed by goal; breadth and market-regime filters are null | Out of scope or already rejected |

## Remaining defensible directions

1. **Multi-horizon range-midpoint equilibrium (selected next).** Ichimoku's
   Tenkan/Kijun/cloud construction uses rolling high-low midpoints rather than
   arithmetic means, return magnitudes, volume or extreme recency. Use all
   values on the current completed bar with no forward displacement.
2. **Downside-path asymmetry.** A future prespecified rule could compare
   downside and upside semivariance inside the active setup. It must first
   demonstrate that this is not another path-efficiency or volatility filter.
3. **Causal gap-adjusted intraday efficiency.** Only defensible if the rule
   separates overnight information from regular-session follow-through and
   does not repackage the rejected gap/ATR/high-close experiments.

The selected Trial 432–440 is the last clearly interpretable canonical
multi-horizon price-state family in the current audit. Failure will close the
range-midpoint-equilibrium direction; thresholds and windows may not be
relaxed or changed after density or returns are observed.

## Subsequent frozen resolutions

This section was appended only after the corresponding frozen trials completed;
it is an outcome ledger, not part of the original outcome-free selection.

- Trial 432–440 closed multi-horizon range-midpoint equilibrium: 81 train
  trades, -0.95% CAGR and PF 0.868.
- Trial 441–447 closed downside-path asymmetry: 73 train trades, -0.03% CAGR;
  drop-top-five expectancy -1.09%.
- Trial 448–454 closed gap-adjusted intraday efficiency: 125 train trades,
  0.33% CAGR; drop-top-five expectancy -0.57%.
- A later lookahead train-only residual audit found five-day-high coincidence
  before oracle exits, but its sole frozen translation in Trial 455–466
  produced only 0.17% CAGR and -0.90% trim-five expectancy. The diagnostic
  strength-exit direction is closed without retuning.
- Trial 467–470 tested a new index-inclusion mechanism using only causal
  membership-start tenure. Its four fixed caps emitted 0/0/4/11 candidates
  versus the frozen minimum 80, so the family closed without returns.
- Trial 471–477 translated the previously documented adverse gap-chasing
  result into a new supply-absorption mechanism: a >=1% bearish gap rejection
  followed by a five-session rejection-high and pivot reclaim. It emitted only
  27 signals and also closed outcome-free under the same density rule.
- Trial 478–482 tested a new month-start institutional-flow lifecycle. Density
  passed at 143 signals, but 99 train trades returned -0.32% CAGR, PF 0.750 and
  -0.56% trim-five expectancy, closing the calendar-flow mechanism before
  validation.
- Trial 483–488 tested a canonical 20-return lag-1 autocorrelation zero-cross
  lifecycle. Its 103 train trades reached PF 1.515 but only 1.29% CAGR, and
  trim-five expectancy reversed to -0.47%; serial dependence is closed without
  retuning its window, lag or threshold.
- Trial 489–495 tested an orthogonal SEC share-supply contraction proxy from
  repository-cached same-accession weighted-average shares. Coverage and
  density passed, but 100 train trades returned only 0.69% CAGR, PF 1.025 and
  -0.57% trim-five expectancy; the supply-contraction lifecycle is closed.

All three failed their unchanged train gates without opening validation or
best-available OOS. No canonical residual direction in this audit remains
unresolved. Membership tenure, gap-rejection reclaim, month-start flow and
serial dependence are now closed too. The SEC share-supply mechanism is also
closed despite adequate cached coverage.
Further work must begin with another genuinely new economic mechanism or a
formal train-only residual analysis; it must not tune these closed indicators.
