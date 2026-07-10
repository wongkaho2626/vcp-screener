# Improved VCP Backtest Verification Report

Generated 2026-07-10 from frozen VCP Strategy v1.

## Backtest Score: 20 / 100 — Reject

| Component | Score | Max |
|---|---:|---:|
| A. Statistical Validity & Significance | 7 | 30 |
| B. Risk-Adjusted Performance | 5 | 25 |
| C. Robustness & Out-of-Sample | 11 | 25 |
| D. Trade Quality & Consistency | 3 | 20 |
| **Raw total** | **26** | **100** |
| Survivorship-bias cap | **20** | |
| **Final score** | **20** | **100** |

The implementation materially improves the realism and completeness of the evidence, but
does not demonstrate a tradeable edge. The unresolved survivorship limitation caps the score
at 20; independently, the frozen portfolio has negative raw and exposure-matched performance.

## Performance metrics

| Metric | Frozen v1 result | Status |
|---|---:|---|
| Period | 2016-02-25 to 2026-07-09 | Adequate length |
| Daily observations | 2,607 | Adequate nominal sample |
| Signals / executed trades | 240 / 212 | Adequate nominal count |
| Total portfolio return | -4.53% | Fail |
| CAGR | -0.45% | Fail |
| Annual volatility | 4.08% | Low because the book is often in cash |
| Sharpe | -0.089 | Fail |
| Sortino | -0.117 | Fail |
| Calmar | -0.026 | Fail |
| Maximum drawdown | -17.13% | Moderate magnitude, very long duration |
| Ulcer Index | 8.12% | Weak |
| Time underwater | 96.47% | Fail |
| 95% VaR / CVaR | -0.44% / -0.69% | Daily portfolio |
| Raw positive months / quarters | 53.17% / 48.84% | Inconsistent |
| Trade win rate | 35.85% | Low |
| Average win / loss | +12.82% / -6.92% | Coherent payoff shape |
| Profit factor | 1.03 | Marginal; below 1.2 threshold |

## Statistical significance

The exposure-matched excess series is the primary stock-selection diagnostic because the
portfolio is intentionally cash-heavy.

| Metric | Value | Status |
|---|---:|---|
| Exposure-matched excess CAGR | -1.79% | Fail |
| Exposure-matched excess Sharpe | -0.553 | Fail |
| t-statistic | -1.778 | Evidence points negative |
| Effective sample size | 1,952 | Adequate |
| PSR versus zero | approximately 0% | Fail |
| Approximate DSR, 180 declared trials | approximately 0% | Fail |
| Jarque-Bera | 38,575.7; p approximately 0 | Fat-tailed; use bootstrap |

The raw daily return series also rejects normality (skew -0.81, excess kurtosis 5.62), so
normal-theory confidence alone is not trusted.

## Robustness

- Chronological 70/30 split: raw IS Sharpe +0.237, OOS Sharpe -0.900.
- Exposure-matched split: IS Sharpe +0.092, OOS Sharpe -1.997. The sign and magnitude
  deterioration reject the frozen combination.
- 5,000-iteration block bootstrap, 10-day blocks: raw CAGR 90% interval -2.60% to +1.75%;
  exposure-matched CAGR -3.57% to +0.04%.
- 5,000 IID Monte Carlo paths: raw MDD 90% interval -28.04% to -8.18%; observed MDD lies
  inside the expected distribution, so the loss is not an anomalous ordering accident.
- Existing MA sensitivity remains a smooth gradient around MA20, but that execution benefit
  does not survive as positive portfolio alpha after combining realistic fills, sizing,
  constraints, and costs.
- Existing Russell 2000 replication supports the paired MA20 entry improvement, but its
  constituent snapshot is not point-in-time and the standalone excess result remains weak.

## Cost stress

Combined commission plus slippage is charged on each side.

| Cost multiplier | Cost per side | Total return | CAGR | MDD |
|---|---:|---:|---:|---:|
| 1x | 10 bps | -4.53% | -0.45% | -17.13% |
| 2x | 20 bps | -6.48% | -0.65% | -18.46% |
| 5x | 50 bps | -17.10% | -1.80% | -24.72% |
| 10x | 100 bps | -27.67% | -3.08% | -32.90% |

## Bias assessment

| Bias | Status | Evidence |
|---|---|---|
| Lookahead | Absent in reviewed implementation | Same-date Edge Rank; later pullback; next-open fill |
| Survivorship | Present, unresolved | 115/717 PIT names lack usable Yahoo histories; local CSV is current-member biased |
| Data snooping | Present but penalised | Strategy frozen; DSR declares 180 prior trials |
| Cost underestimate | Addressed | Two-sided 1x/2x/5x/10x stress |
| Liquidity | Addressed approximately | 1% of trailing 20-day ADV; no order-book model |
| Capacity/overlap | Addressed | Cash, ten-name, 10% name, 30% sector constraints |
| Bar alignment | Addressed | Pullback signal followed by next-session-open entry |
| Regime overfit | Present | OOS Sharpe deteriorates materially |

## Recommendation execution status

| Recommendation | Result |
|---|---|
| Treat VCP as candidate generator | Frozen specification does so |
| Freeze MA20/15-day rule | Completed; no MA30 or post-result substitution |
| Causal capped Edge Rank sizing | Completed |
| Survivorship-free data | Blocked by missing delisted OHLCV; external licensed data required |
| Daily marked realistic portfolio | Completed |
| Cash/overlap/capacity/ADV/sector constraints | Completed |
| Next-bar fills, gaps, slippage, commissions | Completed |
| Effective sample size, PSR and DSR | Completed |
| Block bootstrap and Monte Carlo | Completed |
| Walk-forward/OOS test | Completed; failed |
| Cost stress | Completed; failed |
| Freeze future research | Completed in `references/frozen_strategy_v1.md` |

## Verdict

Backtest Score **20/100 — Reject**. The recommendations improved the research process and
removed optimistic portfolio assumptions, but they did not improve the economic evidence.
VCP may remain useful for discretionary candidate discovery; frozen v1 should not be deployed
as a systematic portfolio. Do not tune v1 in response to this result. A v2 requires a new,
predeclared hypothesis and genuinely untouched or prospective data.
