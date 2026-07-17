# Backtest Verification Report

## Backtest Score: 20 / 100 — Reject

Pocket Pivot materially outperformed the existing pullback portfolio in the full sample,
but did not demonstrate a robust, benchmark-relative edge. The current-constituent data
have confirmed survivorship bias, which applies the 20-point hard cap.

| Component | Score | Max |
|---|---:|---:|
| A. Statistical Validity & Significance | 4 | 30 |
| B. Risk-Adjusted Performance | 7 | 25 |
| C. Robustness & Out-of-Sample | 11 | 25 |
| D. Trade Quality & Consistency | 9 | 20 |
| **Raw total** | **31** | **100** |
| Caps applied | Confirmed survivorship bias → 20; no genuine walk-forward OOS → 55 | |
| **Final score** | **20** | **100** |

Component scoring uses exposure-matched excess return for statistical validity because raw
return is partly market exposure. A receives only sample-adequacy credit; B receives only
drawdown credit; C receives marginal bootstrap plus smooth sensitivity credit; D receives
profit-factor and payoff-coherence credit.

## Executive Summary

On 42 trades from 24 February 2016 through 13 July 2026, Pocket Pivot returned 8.53%
(0.79% CAGR) after 10 bps per side, versus -5.41% for the frozen MA20-pullback portfolio.
Maximum drawdown improved from 15.92% to 3.74%. This is a useful relative improvement, but
not evidence of a deployable edge: Pocket Pivot's exposure-matched excess CAGR was -0.08%,
its raw Sharpe fell from 0.56 in-sample to -0.15 out-of-sample, and the seven 2025–2026
trades produced no winners.

The rule should remain an experimental v2 entry mode. It should not be promoted into the
live screener until it succeeds on genuinely unseen, survivorship-safe data.

## 1. Performance Metrics

| Metric | Pocket Pivot | Healthy benchmark | Status |
|---|---:|---:|---|
| Period / daily observations | 2016-02-24–2026-07-13 / 2,610 | >1 year | Adequate length |
| Executed trades | 42 | ≥30 | Barely adequate |
| Total return / CAGR | 8.53% / 0.79% | Positive after costs | Pass, economically small |
| Annual volatility | 2.13% | Context only | Low because average exposure was 3.82% |
| Sharpe / Sortino | 0.382 / 0.685 | >0.5 / >0.7 | Fail |
| Calmar / Omega | 0.213 / 1.156 | >0.5 / >1 | Mixed |
| Maximum drawdown | -3.74% | <10% | Pass, cash-heavy |
| Ulcer Index / time underwater | 1.87% / 96.17% | Low / <50% | Mixed / fail |
| Longest drawdown / average recovery | 938 / 54.6 trading days | Stable recovery | Fail |
| 95% VaR / CVaR | -0.131% / -0.281% | Context only | Daily portfolio |
| 99% VaR / CVaR | -0.373% / -0.532% | Context only | Daily portfolio |
| Positive months / quarters | 26.2% / 32.6% | >50% | Fail; many cash-flat periods |
| 12-month rolling Sharpe | -2.47 to +2.18; std 1.00 | Stable and positive | Fail |
| Benchmark beta / correlation | 0.024 / 0.212 | Context only | Very low exposure |
| HAC annualised alpha | 0.34%; p=0.580 | p<0.05 | Not significant |
| Exposure-matched excess CAGR / Sharpe | -0.08% / -0.036 | Positive | Fail |

The benchmark is the CSV client's synthetic equal-weight current-constituent index, not a
tradable SPY total-return series.

### Trade statistics

| Metric | Value | Status |
|---|---:|---|
| Profit factor | 1.319 | Above 1.2, below 1.5 |
| Expectancy | +1.20% per trade | Positive but outlier-sensitive |
| Win rate | 30.95% | Low |
| Average win / loss | +16.06% / -5.46% | Coherent asymmetric payoff |
| Payoff ratio | 2.94 | Supports the low win rate |
| Full Kelly fraction | 7.49% | Positive; not a deployment recommendation |

## 2. Statistical Significance

| Series | t-stat / p-value | PSR vs zero | Approx. DSR probability (181 trials) | Interpretation |
|---|---:|---:|---:|---|
| Pocket Pivot raw return | 1.229 / 0.219 | 91.3% | 4.7% | Not significant after multiple testing |
| Pocket Pivot exposure-matched excess | -0.116 / 0.907 | 45.4% | 0.2% | No stock-selection alpha |
| Raw daily lift over pullback | 1.047 / ≈0.295 | 85.8% | 3.2% | Relative lift is not significant |
| Exposure-matched lift over pullback | 1.942 / ≈0.052 | 97.9% | 15.7% | Borderline before, fails after multiplicity |

Raw returns reject normality (Jarque–Bera p≈0), and Ljung–Box p=1.4e-9 detects serial
dependence. The return ADF p=8.7e-16 supports return stationarity, but normal-theory tests
are secondary to the 10-day block bootstrap. The raw-CAGR 90% bootstrap interval is
-0.21% to +1.89%, which crosses zero.

## 3. Bias Assessment

| Bias | Status | Evidence |
|---|---|---|
| Lookahead | Absent in reviewed Pocket Pivot path | Starts from `as_of_date`; uses only prior/contemporaneous OHLCV and as-of VCP pivot/stop; next-open fill; `forward_outcome` is not consulted |
| Survivorship | Present | Local CSV is a current-constituent security set and lacks a complete delisted-name history |
| Data snooping / overfitting | Present, penalised | New rule is prespecified, but evaluated after at least 180 prior strategy trials on the same research history |
| Transaction-cost underestimate | Addressed | Two-sided 10/20/50/100 bps-per-side stress |
| Liquidity | Addressed approximately | Position capped at 1% of trailing 20-day ADV; no order-book/market-impact model |
| Sector concentration | Cannot verify correctly | All 1,008 source detections have `sector=Unknown`, so the nominal 30% sector cap behaves as an approximately 30% whole-book cap |
| Data-frequency mismatch | Absent in reviewed path | Signal is known at daily close and fills at next daily open |
| Look-forward in features | Absent in reviewed Pocket Pivot path | SMA and volume windows end on the signal bar |
| Regime overfit | Present | Positive development result decays to flat validation and negative evaluation results |
| Benchmark quality | Limited | Synthetic equal-weight index is also based on the surviving CSV universe |

## 4. Robustness

### Chronological stability

| Segment | Trades | Return | Sharpe | Profit factor |
|---|---:|---:|---:|---:|
| Development, 2016–2021 | 20 | +10.89% | 0.742 | 2.951 |
| Validation, 2022–2024 | 15 | +0.41% | 0.100 | 0.799 |
| Evaluation, 2025–2026 | 7 | -2.88% | -1.151 | 0.000 |

The independent 70/30 chronological diagnostic gives IS Sharpe 0.558 and OOS Sharpe
-0.152, for an efficiency ratio of -0.27. This is a holdout diagnostic, not a true rolling
re-optimising walk-forward analysis.

### Resampling and drawdowns

- 5,000-iteration, 10-day block bootstrap raw CAGR 90% interval: -0.21% to +1.89%.
- 5,000-path IID Monte Carlo maximum-drawdown 90% interval: -8.56% to -2.61%.
- Observed -3.74% drawdown lies inside the expected Monte Carlo range.
- Exposure-matched bootstrap CAGR interval: -1.00% to +0.93%.

### Cost stress

| Cost per side | Trades | Return | CAGR | Maximum drawdown |
|---|---:|---:|---:|---:|
| 10 bps | 42 | 8.53% | 0.79% | -3.74% |
| 20 bps | 42 | 7.99% | 0.74% | -3.80% |
| 50 bps | 42 | 6.17% | 0.58% | -4.29% |
| 100 bps | 42 | 3.23% | 0.31% | -5.77% |

The raw strategy survives cost stress because turnover and exposure are low; this does not
repair the missing benchmark-relative alpha or OOS failure.

### Parameter sensitivity

| Robustness variation | Trades | Return | Sharpe | Profit factor |
|---|---:|---:|---:|---:|
| Scan window 5 sessions | 27 | 7.37% | 0.376 | 1.425 |
| Frozen scan window 10 | 42 | 8.53% | 0.382 | 1.319 |
| Scan window 15 | 57 | 6.70% | 0.278 | 1.148 |
| Extension limit 2% | 21 | 6.64% | 0.449 | 1.541 |
| Frozen extension limit 3% | 42 | 8.53% | 0.382 | 1.319 |
| Extension limit 4% | 62 | 10.65% | 0.374 | 1.324 |
| Volume lookback 8 sessions | 55 | 7.10% | 0.303 | 1.222 |
| Frozen volume lookback 10 | 42 | 8.53% | 0.382 | 1.319 |
| Volume lookback 12 | 36 | 8.76% | 0.423 | 1.410 |

The in-sample surface degrades smoothly rather than falling off a cliff. No variation is
adopted: these are robustness checks, not a post-hoc parameter search.

## 5. Red Flags 🚩

1. Performance collapses after 2021; the latest seven trades have zero winners.
2. Exposure-matched excess return is slightly negative and statistically indistinguishable
   from zero.
3. The multiple-testing-adjusted probability is only 4.7% even on raw return.
4. Survivorship bias is unresolved and independently caps the score at 20.
5. Forty-two trades and 3.82% average exposure make headline drawdown and volatility look
   safer than a normally invested strategy.
6. Missing sector labels turn the sector limit into a de facto whole-book exposure cap.
   This affects both variants equally, but distorts absolute return and capacity estimates.
7. Returns are extremely non-normal and serially dependent; rolling Sharpe is unstable.

## 6. Improvement Recommendations 💡

1. Do not add Pocket Pivot as a promoted live buy signal. Keep it as an optional research
   entry rule and collect prospective signals without tuning the frozen thresholds.
2. Re-evaluate only after a genuinely untouched sample with at least 30 additional
   independent trades; require positive exposure-matched excess and OOS Sharpe.
3. Use a survivorship-safe security master with delisted OHLCV and point-in-time membership,
   plus a real tradable benchmark series.
4. Restore point-in-time sector labels before re-estimating portfolio capacity and
   concentration risk.
5. Preserve next-open fills, the ADV cap, and 10–100 bps cost stress. Do not revert to
   same-close fills to improve the curve.
6. If fundamentals or industry leadership are added later, declare that as a separate v3
   hypothesis rather than tuning v2 on this history.

## 7. Verdict

Backtest Score **20/100 — Reject**. Pocket Pivot is better than the current systematic
pullback baseline in this sample and has a smooth parameter surface, but the improvement is
not a durable tradeable edge. It fails benchmark-relative, multiple-testing, and
chronological OOS checks, and the survivorship flaw remains fatal.
