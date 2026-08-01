# SEC Margin-Quality Fit Audit

Status: **rejected in discovery; internal holdout not evaluated**.

This audit used only hard-stop-aware forward-20 labels from the frozen
2016-07-01..2018-06-30 fit period. SEC values were eligible only when
`filed < signal_date`, age was no more than 120 days, and current/prior facts
were presented in the same accession. Each setup received equal weight by
averaging its eligible daily-state labels.

| Candidate feature | Setups | Mean label | Median | Positive setups |
|---|---:|---:|---:|---:|
| Gross-margin expansion | 22 | -1.64% | -2.19% | 45.5% |
| Gross-margin expansion + revenue growth >=10% | 9 | -0.15% | +0.90% | 77.8% |
| Positive operating-margin expansion | 40 | -1.17% | -0.35% | 50.0% |
| Positive operating-margin expansion + revenue growth >=10% | 16 | +0.20% | +1.07% | 68.8% |
| Gross and operating margins both expand | 19 | -1.88% | -2.13% | 47.4% |
| Both expand + revenue growth >=10% | 8 | -0.30% | +0.90% | 75.0% |

Neither gross-margin-delta nor operating-margin-delta quartiles were monotonic.
The only positive cells were too small and too weak to justify another rule,
especially after 304 declared multiplicity units. No specification was frozen
and no internal-holdout returns were opened for this direction.

