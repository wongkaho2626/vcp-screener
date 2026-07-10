# Portfolio Robustness Report

Period: 2016-07-21 to 2026-07-09 (2505 daily observations)

## Core metrics

| Metric | Value |
|---|---:|
| CAGR | 0.09% |
| Annual volatility | 1.20% |
| Sharpe | 0.079 |
| Sortino | 0.112 |
| Calmar | 0.030 |
| Maximum drawdown | -2.97% |
| Ulcer index | 1.62% |
| Time underwater | 98.20% |
| 95% VaR | -0.09% |
| 95% CVaR | -0.20% |

## Statistical validation

- t-statistic: 0.249
- Effective sample size: 2505.000
- PSR vs zero: 59.84%
- Approximate DSR probability (181 declared trials): 0.65%
- DSR benchmark Sharpe: 0.867

## Stability and robustness

- IS Sharpe: 0.319
- OOS Sharpe: -1.028
- WFA efficiency: -3.228
- Positive months: 23.14%
- Positive quarters: 29.27%
- Bootstrap CAGR 90% interval: -0.57% to 0.73%
- Monte Carlo MDD 90% interval: -7.33% to -1.96%
- Ljung Box: unavailable (install statsmodels)
- Adf: unavailable (install statsmodels)

## Method notes

- Returns are decimal daily returns; risk-free rate and Omega threshold are zero.
- WFA is a chronological holdout diagnostic, not parameter re-optimisation.
- DSR is an approximation using the declared number of trials and effective sample size.
- Block bootstrap preserves short-range dependence; Monte Carlo uses IID resampling.
