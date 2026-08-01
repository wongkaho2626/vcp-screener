# Detector / Portfolio Price-Scale Audit

Generated 2026-08-01.

## Critical finding

The original v2 detection run used raw OHLC in `CSVHistoricalClient`, while the
portfolio engine's `CSVClient` scaled OHLC by `Adj Close / Close`. Serialized
pivots and contraction stops were therefore on a different price scale from
entries, stops and marks. Example: CAT on 2016-07-13 had raw close 79.69 and
adjusted close 63.38; the old serialized stop 73.35 sat above the portfolio
price.

Among 389 old train-eligible immediate-detection signals, 282 had adjusted
as-of close below the raw-scale serialized stop. All portfolio scores, CAGRs,
oracle diagnostics and strategy comparisons produced from
`backtests/pivot_retest_v2/detections/vcp_backtest_2026-08-01_120903.json` are
**invalidated** and must not support a strategy claim.

## Correction

`backtest_vcp.CSVHistoricalClient` now applies the identical adjusted-OHLC
transformation as `csv_client.CSVClient`. A parity test compares every bar field
between both clients. The corrected detection run scanned 599 PIT stocks with
zero failures and produced 1,095 detections:

`detections/vcp_backtest_2026-08-01_132107.json`.

A second causal defect was then identified: the detector can serialize a VCP
whose as-of close has already fallen below its final-contraction stop. Entry
planning previously started invalidation checks on the following session. The
shared signal builder and breakout walker now reject such patterns on the
as-of bar itself; synthetic tests cover immediate entry and breakout planning.

The old research artifacts remain only as an audit trail. Corrected baselines
and every subsequent hypothesis must use the adjusted detection JSON above.
