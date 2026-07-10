# Portfolio Robustness Report

Period: 2016-07-21 to 2026-07-09 (2505 daily observations)

## Core metrics

| Metric | Value |
|---|---:|
| CAGR | -0.28% |
| Annual volatility | 1.02% |
| Sharpe | -0.268 |
| Sortino | -0.370 |
| Calmar | -0.054 |
| Maximum drawdown | -5.15% |
| Ulcer index | 2.99% |
| Time underwater | 99.08% |
| 95% VaR | -0.09% |
| 95% CVaR | -0.17% |

## Statistical validation

- t-statistic: -0.844
- Effective sample size: 2505.000
- PSR vs zero: 19.84%
- Approximate DSR probability (181 declared trials): 0.02%
- DSR benchmark Sharpe: 0.867

## Stability and robustness

- IS Sharpe: 0.009
- OOS Sharpe: -1.486
- WFA efficiency: -170.036
- Positive months: 23.14%
- Positive quarters: 29.27%
- Bootstrap CAGR 90% interval: -0.84% to 0.26%
- Monte Carlo MDD 90% interval: -9.02% to -2.27%
- Ljung Box: unavailable (install statsmodels)
- Adf: unavailable (install statsmodels)

## Method notes

- Returns are decimal daily returns; risk-free rate and Omega threshold are zero.
- WFA is a chronological holdout diagnostic, not parameter re-optimisation.
- DSR is an approximation using the declared number of trials and effective sample size.
- Block bootstrap preserves short-range dependence; Monte Carlo uses IID resampling.
