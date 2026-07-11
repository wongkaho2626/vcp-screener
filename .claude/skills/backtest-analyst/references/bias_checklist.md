# Bias Audit Checklist

Use this as an interview script when auditing a backtest.

## Lookahead Bias
- [ ] Are signals computed strictly on data available at bar close (or open, if trading open)?
- [ ] Is there any `shift(0)` where `shift(1)` should be used?
- [ ] Is the target variable constructed from future prices?
- [ ] Are corporate actions (splits, dividends) adjusted retroactively?
- [ ] Does the volatility estimate use the same-bar return?

## Survivorship Bias
- [ ] Does the universe include names that were delisted, bankrupt, or merged?
- [ ] Is the universe membership determined as of today (point-in-time)?
- [ ] Were index constituents taken from a historical snapshot or today's list?
- [ ] For crypto/startup strategies: are dead coins/companies included?

## Data Snooping / Overfitting
- [ ] How many parameters were optimised? (>5 on <5 years = high risk)
- [ ] Were parameters chosen after seeing OOS data (even informally)?
- [ ] Is the same dataset used for both model development AND reported performance?
- [ ] Were there previous strategy versions tested on the same data?

## Transaction Cost Underestimation
- [ ] What spread model is used? (bid-ask, market impact)
- [ ] Are commissions included per-trade?
- [ ] Is slippage modelled? (especially for illiquid or large trades)
- [ ] Is short interest / borrow cost included for short legs?
- [ ] Are fills assumed at limit or market prices?

## Liquidity Bias
- [ ] What is the maximum position as % of ADV?
  - Guideline: < 5% ADV for daily strategies, < 1% for HF
- [ ] Are fills assumed during halts or low-volume periods?
- [ ] Is the strategy tested on assets that were illiquid in early history?

## Data Quality
- [ ] Are there known data errors (outliers, bad ticks) in the source?
- [ ] Is corporate action adjustment consistent across the full history?
- [ ] Are earnings/fundamental dates point-in-time (e.g., Compustat PIT)?

## Execution Bias
- [ ] Is execution assumed at OHLC or a realistic model?
- [ ] Are margin calls / forced liquidations modelled?
- [ ] Is portfolio rebalancing done at realistic intraday times?
