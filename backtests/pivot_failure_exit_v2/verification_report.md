# Train-Gate Verification — pivot-failure exit v2

Evaluated 2026-08-01 from the frozen spec. Validation was **not opened**.

| Train metric | Pivot-retest baseline | Pivot-failure exit |
|---|---:|---:|
| Trades | 34 | 35 |
| Net CAGR | +1.77% | **-0.56%** |
| Sharpe | +0.627 | **-0.477** |
| Sortino / Calmar | 1.105 / 0.606 | -0.601 / -0.124 |
| MDD | -2.91% | -4.54% |
| PF / expectancy | 2.10 / +3.88% | **0.81 / -0.46%** |
| Drop-top-5 expectancy | -0.53% | **-2.80%** |
| t / PSR / DSR | 1.46 / 94.8% / 6.4% | -1.11 / 12.7% / 0.004% |

Only the >=30-trade requirement passed. CAGR, Sharpe, PF and trim gates all
failed, so the sequential protocol closed the hypothesis without inspecting
2022-2026 validation or untouched OOS.

Mechanistically, a brief close below the pivot is common noise after a retest,
not reliable structural failure. The exit raises turnover and realizes small
losses while removing later recoveries. No pivot buffer or multi-close retry
may be fitted post hoc on this result.

**Verdict: Reject at train gate.** No Backtest Score is assigned because no
validation/OOS evaluation was permitted; treating missing evidence as a score
would violate the backtest-analyst reduced-component rule.
