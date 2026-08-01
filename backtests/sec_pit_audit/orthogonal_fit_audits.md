# Orthogonal Event and Quality Audits — 2026-08-01

These screens were evaluated only for coverage or on the frozen
2016-07-01..2018-06-30 fit labels. Internal holdout, formal validation, and
untouched OOS outcomes were not opened for any rejected direction below.

| Direction | Fit evidence | Outcome-free holdout density | Decision |
|---|---|---:|---|
| Form 4 open-market purchase | 20 independent filings touch 19 setups | 25 filings / 16 setups | Reject: below 30 independent events |
| Initial SC 13D | zero fit setups | 3 setups | Reject: insufficient density |
| Initial SC 13G | 23 setups; fixed-20 mean +1.04%, trim-5 -0.83% | 29 setups (31 with 13D) | Reject: thin and outlier-dependent |
| Non-earnings material 8-K, prior 10d | 43 setups; fixed-20 mean +0.71%, trim-5 -0.63% | 77 setups | Reject: no trim-stable fixed exit edge |
| 8-K first-session +2% / 1.5x-volume confirmation | 3 setups | 0 setups | Reject: no density |
| Annual operating-cash-flow / net-income >=1 | 40 setups; mean -0.86%, trim-5 -1.52% | not opened | Reject in fit |
| Gross/operating margin expansion | see `sec_margin_fit_audit.md`; no monotonicity | not opened | Reject in fit |
| Full Stage-2 trend template on first setup state | 40 fit setups; fixed-20 +0.65%, trim-5 -0.82% | 114 detections | Reject: outlier-dependent |
| Stage-2 trend gate on p70 ridge entries | 28 fit signals; +0.67%, trim-5 -1.26% | not opened | Reject in fit |
| Extend fit into 2014–2015 | 2014/2015 PIT member-day price coverage 74.22%/76.51% | n/a | Reject before outcomes: survivorship coverage |

SEC event availability always requires `filed < signal_date`. Form 4 purchase
classification is non-derivative `transactionCode=P` and acquired `A`; sales
are `S` and disposed `D`. Earnings Item 2.02 was excluded from the 8-K audit
because the repository's prior earnings-catalyst work already rejected that
family.

