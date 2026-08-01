# Constructive Pivot-Retest — Train-Only Discovery Report

Generated 2026-08-01 under `family_spec.md`. The selector did **not** inspect
2022-2026 validation data.

| Variant | Trades | CAGR | Sharpe | PF | Drop-top-5 expectancy | Eligible |
|---|---:|---:|---:|---:|---:|---|
| baseline | 34 | 1.77% | 0.627 | 2.104 | -0.53% | baseline |
| breakout_no_gap_1pct | 27 | 1.58% | 0.624 | 2.131 | -1.58% | no |
| bullish_retest | 24 | 0.22% | 0.122 | 1.152 | -3.49% | no |
| strong_close_clv60 | 23 | 0.33% | 0.164 | 1.380 | -2.88% | no |
| retest_high_confirm3 | 17 | -0.13% | -0.063 | 1.149 | -5.29% | no |

## Selection verdict

No non-baseline cell passed every prespecified gate, so the family closes and
validation remains unread:

- No-gap retained PF but did not improve Sharpe and remained top-five fragile.
- Bullish and strong-close filters cut the sample below 25 and reduced Sharpe.
- Three-session retest-high confirmation was negative and too sparse.
- Every cell had negative drop-top-five expectancy; the apparent train edge is
  a small-winner subset sitting underneath five dominant outliers.

No threshold sensitivity, cell conjunction, or post-result substitution is
permitted. Full JSON/Markdown output is in `results/`.
