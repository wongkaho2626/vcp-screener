# Improvement Playbook by Strategy Class

## Trend-Following / Momentum
- **Signal**: Combine short + long lookbacks (dual MA); add volatility filter to avoid choppy markets
- **Position sizing**: Volatility-target (e.g. 10% annualised vol per position)
- **Filter**: Only trade when trend strength (ADX > 25) is confirmed
- **Risk**: Time-stop — exit if position hasn't moved in X bars
- **Cost reduction**: Reduce signal sensitivity to lower turnover; use weekly rebalance

## Mean Reversion / Stat Arb
- **Signal stability**: Use cointegration (Engle-Granger or Johansen) rather than simple correlation
- **Regime filter**: Only enter when z-score < -2.0 AND volatility is normal (not crisis)
- **Half-life**: Compute OU half-life; min holding time = half-life / 2
- **Decay**: If half-life > 30 days, rethink — too slow for stat arb, too fast for macro
- **Hedge ratio**: Refit Kalman filter hedge ratio rather than static OLS

## ML / Factor Models
- **Feature engineering**: Use time-aware cross-validation (purging + embargo)
- **Target leakage**: Verify no future information in any feature
- **Overfitting**: Max depth limit; use hold-out set for early stopping, not validation fold
- **Ensemble**: Average predictions from multiple independently trained models
- **Model risk**: Track model degradation in live paper-trading before committing capital

## Options / Derivatives
- **Greeks hedging**: Model delta/gamma PnL separately from theta/vega
- **Vol surface**: Use realistic vol surface (not flat Black-Scholes) for backtest pricing
- **Pin risk**: Model expiry risk explicitly (positions at strike)
- **Liquidity**: Options markets: use mid-point minus 1/3 bid-ask as realistic fill

## High-Frequency / Intraday
- **Tick data quality**: Use cleaned, normalised tick data (remove outliers, bad prints)
- **Latency**: Add realistic network + processing latency (even 1ms matters)
- **Queue position**: Model queue position for limit orders (not guaranteed fills)
- **Intraday costs**: Include exchange fees, rebates, market impact
- **Regime**: Many HF strategies stop working after market structure changes (e.g. decimalization)

## Multi-Asset / Macro
- **FX hedging**: Model currency exposure explicitly if trading non-base-currency assets
- **Carry**: Include roll cost for futures (nearby vs deferred)
- **Correlation regime**: Use DCC-GARCH for time-varying correlations in portfolio construction
- **Macro regimes**: Test separately for growth/recession, risk-on/risk-off periods

---

## Universal Quick Wins (apply to any strategy)

1. **Vol targeting**: Scale position size by `target_vol / realised_vol_lookback`
   → reduces drawdown depth, improves Sharpe by 0.1–0.4 typically

2. **Ensemble / vote**: If you have multiple signals, average them
   → reduces single-signal variance, improves IR

3. **Signal smoothing**: Replace `raw_signal` with `EMA(raw_signal, 3–5 days)`
   → reduces whipsawing and transaction costs

4. **Drawdown throttle**: If portfolio DD > 10%, halve position sizes
   → dramatically reduces tail losses at cost of capping upside in recovery

5. **Calendar effects filter**: Avoid holding positions through earnings/central bank days
   → removes fat-tail event risk from return distribution
