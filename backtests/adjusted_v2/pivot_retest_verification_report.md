# Corrected Adjusted-Scale Pivot-Retest Baseline Verification

Generated 2026-08-01. Trial 212 was frozen before corrected validation.

## Verdict: REJECT — 41/100; untouched OOS remains sealed

| Metric | Train 2016-07 to 2021 | Validation 2022 to 2026-06 |
|---|---:|---:|
| Trades | 85 | 94 |
| Net CAGR | 0.95% | 0.64% |
| Sharpe | 0.247 | 0.184 |
| Sortino | 0.391 | 0.262 |
| Calmar | 0.102 | 0.102 |
| MDD | -9.36% | -6.26% |
| Profit factor | 1.239 | 1.047 |
| Drop-top-5 expectancy | -1.20% | -2.08% |
| PSR | 72.1% | 65.0% |
| Approximate DSR (212 trials) | 1.22% | 0.45% |

Validation t-statistic was 0.39. Bootstrap CAGR 5th/median/95th percentiles
were -2.52% / 0.70% / 4.09%; Monte Carlo final equity percentiles were 0.895 /
1.031 / 1.172. Positive months/quarters were 46.3%/44.4%. Train-to-validation
Sharpe efficiency was 0.745 in the scoring comparison.

Sensitivity did not rescue the rule: 10/15/20-session windows produced
-0.03%/0.64%/0.66% validation CAGR. Cost stress produced 0.46% at 2x, -0.06%
at 5x and -1.28% at 10x. PF was at most 1.060 across neighbouring windows.

The corrected run used identical adjusted OHLC in detector and executor,
rejected patterns already below stop on the as-of bar, enforced PIT membership
(40 train and 26 validation drops), kept SPY benchmark-only, and retained all
fixed portfolio and cost constraints. Coverage remained 91.31%.

Machine-readable result and daily/trade CSVs:
`pivot_retest_results/pivot_retest_baseline_validation_2026-08-01_132708.json`.
