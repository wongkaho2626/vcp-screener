# Corrected Adjusted-Scale Train Feasibility Audit

Generated 2026-08-01 from train 2016-07-01 through 2021-12-31 only. Validation
and untouched OOS were not accessed. All oracle cells are explicitly non-causal
and cannot be scored or deployed.

| Cell | Signals | Trades | Net CAGR | MDD |
|---|---:|---:|---:|---:|
| Immediate detection | 268 | 198 | 0.56% | -8.51% |
| Pivot retest | 93 | 85 | 0.95% | -9.36% |
| Down-close pivot hold | 150 | 123 | 0.51% | -10.43% |
| Future-winner / baseline exit oracle | 89 | 71 | 8.89% | -2.87% |
| Perfect entry selection + best exit, 60d | 211 | 181 | 15.66% | -2.72% |
| Perfect entry selection + best exit, 120d | 211 | 167 | 16.72% | -3.01% |
| Perfect entry selection + best exit, 252d | 211 | 141 | 15.58% | -5.18% |
| Perfect entry timing + best exit, 60d | 239 | 200 | **28.06%** | -1.69% |
| Perfect entry timing + best exit, 120d | 239 | 182 | **25.66%** | -3.00% |
| Perfect entry timing + best exit, 252d | 239 | 150 | **22.44%** | -4.04% |
| Perfect entry timing + ordinary stop/60d exit | 144 | 112 | **16.78%** | -2.53% |

The corrected oracle establishes three boundaries. Perfect selection at the
as-of next open is insufficient (<20%). Perfect choice of one entry within the
following 60 setup sessions also remains insufficient when paired with the
ordinary hard-stop/60-session exit (16.78%). Only perfect timing paired with a
perfect feasible next-open exit crosses 20% under unchanged sizing, costs and
capacity. The target is therefore structurally possible only through a jointly
better causal entry-timing and exit mechanism; entry filters or timing alone
cannot bridge the gap.

Machine-readable result:
`feasibility/train_feasibility_2026-08-01_134021.json`.

## Oracle timing path diagnostic

Among 239 future-profitable perfectly timed train opportunities, median delay
was 5 sessions (mean 12.5); 53.1% occurred within sessions 0–5. Only 36.4% of
chosen signal closes were above pivot and only 1.3% crossed pivot that day.
Median close was 2.44% below pivot, median five-session return -1.73%, and
median close-location value 0.24. This is hypothesis-generating lookahead
evidence only, but it points toward causal short-term pullback timing rather
than another breakout-strength confirmation.
