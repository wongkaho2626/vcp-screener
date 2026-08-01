# SEC Point-in-Time Fundamental Coverage

Outcome data accessed: **NO**

A filing is usable only when `filed < signal_date`. EPS and revenue YoY
comparisons use current and prior-period facts presented in the same
10-Q/10-K accession. Fresh means no more than 120 calendar days old.

| Period | PIT detections | Facts cache | Comparable | Fresh 120d | EPS>=20% & Rev>=10% |
|---|---:|---:|---:|---:|---:|
| fit | 169 | 163 (96.45%) | 138 (81.66%) | 106 (62.72%) | 17 |
| calibration | 52 | 52 (100.00%) | 49 (94.23%) | 41 (78.85%) | 3 |
| internal_holdout | 284 | 274 (96.48%) | 253 (89.08%) | 182 (64.08%) | 49 |
| all_2016_2021 | 738 | 713 (96.61%) | 645 (87.40%) | 501 (67.89%) | 103 |

Invalid cached JSON files: **0**
