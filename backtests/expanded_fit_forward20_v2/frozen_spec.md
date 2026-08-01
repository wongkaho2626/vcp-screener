# Trial 312 — Expanded Recent Fit / Forward-20 Ridge

Status: **frozen before fitting/evaluating internal-holdout outcomes** on
2026-08-01.

Trial 288 used only 103 fit setups and was robust but sparse. Extending backward
into 2014–2015 is rejected because PIT member-day price coverage is only
74.22%/76.51%. Instead, enlarge the well-covered recent fit window without
changing any feature, target, threshold, or portfolio rule:

- fit detections: 2016-07-01..2018-12-31;
- fit outcome buffer: through 2019-06-30;
- outcome-free calibration: 2019-07-01..2019-12-31; and
- unchanged internal holdout: 2020-01-01..2021-12-31.

Use the same fifteen causal features, setup-equal linear ridge lambda=10,
hard-stop-aware forward-20 net target, calibration p85 next-open entry, p50
next-open score-decay exit, hard stop, and 60-session timeout as Trial 288.
The six-month gap between the last fit detection and calibration prevents
20/60-session label overlap.

All PIT S&P 500 membership, adjusted OHLC, fixed sizing/cash/capacity, name/
sector/ADV restrictions, 8% risk cap, costs, and benchmark-only SPY remain
unchanged. Count the expanded/recent training chronology as one new
multiplicity unit, raising 311 -> 312.

The one 2020–2021 internal holdout requires at least 25 trades, CAGR at least
15%, Sharpe at least 0.75, PF above 1.20, MDD better than -15%, and positive
drop-top-five expectancy. Failure closes the rule without formal validation or
untouched OOS.

