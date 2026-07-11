# Quantitative Statistical Methods

Statistical methodology for quant strategy development and validation: time-series testing,
volatility modeling, regression diagnostics, and statistical inference. Load this when the
user needs stationarity/cointegration testing, GARCH volatility work, regression diagnostics,
bootstrap inference, or a rigorous hypothesis-testing setup — i.e. anything beyond the core
performance/bias checklist in SKILL.md Phases 2–4.

---

## Time-Series Tests

### 1. ADF Unit-Root Test (Stationarity)

**Why it matters**: regressing non-stationary series directly can produce *spurious
regression* — high R² and significant t-stats that are entirely artifactual. Always confirm
stationarity before OLS on levels.

```python
from statsmodels.tsa.stattools import adfuller

def adf_test(series: pd.Series, significance: float = 0.05) -> dict:
    """ADF test: H0 = unit root (non-stationary), H1 = stationary."""
    result = adfuller(series.dropna(), autolag='AIC')
    return {
        'adf_statistic': result[0],
        'p_value': result[1],
        'lags_used': result[2],
        'is_stationary': result[1] < significance,
        'critical_values': result[4],  # 1%, 5%, 10%
    }
```

| p-value | Conclusion | Action |
|---|---|---|
| < 0.01 | Strongly stationary | Use directly for regression/modeling |
| 0.01–0.05 | Stationary | Usable |
| 0.05–0.10 | Weak evidence | Difference and retest |
| > 0.10 | Non-stationary | Difference, or handle via cointegration |

**Stationarity of common financial series**:

| Series | Typical Result | Treatment |
|---|---|---|
| Price series | Non-stationary (unit root) | Use log returns |
| Log returns | Stationary | Use directly |
| PE / PB series | Usually non-stationary | Use changes or logs |
| Volatility series | Usually stationary | Use directly |
| Volume | May be non-stationary | Use logs or standardization |

### 2. Cointegration Test

**Purpose**: determine whether two non-stationary series share a long-run equilibrium — the
foundation of pair trading / statistical arbitrage.

```python
from statsmodels.tsa.stattools import coint

def cointegration_test(y: pd.Series, x: pd.Series) -> dict:
    """Engle-Granger two-step cointegration test. H0: no cointegration."""
    score, p_value, critical = coint(y, x)
    return {
        'test_statistic': score,
        'p_value': p_value,
        'is_cointegrated': p_value < 0.05,
        'critical_values': {'1%': critical[0], '5%': critical[1], '10%': critical[2]},
    }
```

**Hedge ratio & spread for pair trading**:

```python
import statsmodels.api as sm

def find_hedge_ratio(y: pd.Series, x: pd.Series) -> dict:
    """y = α + β·x + ε ; Spread = y - β·x"""
    x_const = sm.add_constant(x)
    model = sm.OLS(y, x_const).fit()
    spread = y - model.params[1] * x
    return {
        'hedge_ratio': model.params[1],
        'intercept': model.params[0],
        'spread_mean': spread.mean(),
        'spread_std': spread.std(),
        'half_life': compute_half_life(spread),  # mean-reversion speed
    }

def compute_half_life(spread: pd.Series) -> float:
    """Estimate mean-reversion half-life via OLS."""
    spread_lag = spread.shift(1)
    delta = spread - spread_lag
    model = sm.OLS(delta.dropna(), sm.add_constant(spread_lag.dropna())).fit()
    return -np.log(2) / model.params[1]
```

**Pair-trading signal** (z-score = `(spread - mean) / std`):

| z_score | Signal |
|---|---|
| > 2.0 | Short spread (sell y, buy x) |
| > 1.5 | Small short spread |
| < -1.5 | Small long spread |
| < -2.0 | Long spread (buy y, sell x) |
| back near 0 | Close position |

### 3. Granger Causality

```python
from statsmodels.tsa.stattools import grangercausalitytests

def granger_test(data: pd.DataFrame, x_col: str, y_col: str, max_lag: int = 5):
    """Does historical x help predict y? Note: predictive, NOT true causality."""
    results = grangercausalitytests(data[[y_col, x_col]].dropna(), maxlag=max_lag)
    return {lag: results[lag][0]['ssr_ftest'][1] for lag in range(1, max_lag+1)}
```

---

## GARCH Volatility Modeling

```
Returns:    r_t = μ + ε_t
Volatility: σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}

- ω (omega): long-run variance baseline
- α (alpha): impact of yesterday's shock on today's volatility
- β (beta):  persistence of yesterday's volatility
- α + β:     volatility persistence (usually 0.95–0.99)
- Long-run volatility = sqrt(ω / (1 - α - β))
```

```python
from arch import arch_model

def fit_garch(returns: pd.Series) -> dict:
    """Fit GARCH(1,1). returns should be a daily return series."""
    model = arch_model(returns * 100, vol='Garch', p=1, q=1,
                       mean='Constant', dist='normal')
    result = model.fit(disp='off')
    forecast = result.forecast(horizon=5)
    a, b = result.params['alpha[1]'], result.params['beta[1]']
    return {
        'omega': result.params['omega'],
        'alpha': a,
        'beta': b,
        'persistence': a + b,
        'long_run_vol': np.sqrt(result.params['omega'] / (1 - a - b)) / 100,
        'current_vol': np.sqrt(result.conditional_volatility[-1]) / 100,
        'forecast_vol_5d': np.sqrt(forecast.variance.values[-1, :]) / 100,
        'aic': result.aic,
        'bic': result.bic,
    }
```

| Model | Characteristics | Use When |
|---|---|---|
| GARCH(1,1) | Symmetric shock response | Default choice |
| EGARCH | Asymmetric (leverage effect) | Down-move vol > up-move vol |
| GJR-GARCH | Asymmetric, easier to interpret | Same as EGARCH |
| FIGARCH | Long memory | Vol clustering persists very long |

**Regime notes**: A-shares typically show α ≈ 0.05–0.15, β ≈ 0.80–0.90, clear leverage
effect (EGARCH fits better). BTC shows α ≈ 0.05–0.20 (shocks matter more), β ≈ 0.75–0.90,
more symmetric shocks, long-run vol ~60–80% annualized. Volatility-forecast accuracy decays
rapidly beyond 5–10 days.

---

## Regression Diagnostics

Financial data is almost always heteroskedastic and often autocorrelated, so **default to
HAC (Newey-West) standard errors** on any OLS you report.

### Heteroskedasticity

```python
from statsmodels.stats.diagnostic import het_white, het_breuschpagan

def heteroscedasticity_test(model_result) -> dict:
    """H0: homoskedasticity."""
    white_stat, white_p, _, _ = het_white(model_result.resid, model_result.model.exog)
    bp_stat, bp_p, _, _ = het_breuschpagan(model_result.resid, model_result.model.exog)
    return {
        'white_p': white_p, 'bp_p': bp_p,
        'has_heteroscedasticity': white_p < 0.05 or bp_p < 0.05,
        'fix': 'Use HAC (Newey-West) errors or WLS' if white_p < 0.05 else 'None needed',
    }
```
Fix: `model.fit(cov_type='HAC', cov_kwds={'maxlags': 5})`, or WLS.

### Autocorrelation

```python
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.stats.stattools import durbin_watson

def autocorrelation_test(residuals: pd.Series, lags: int = 10) -> dict:
    """H0: no autocorrelation."""
    dw = durbin_watson(residuals)
    lb = acorr_ljungbox(residuals, lags=lags)
    return {
        'durbin_watson': dw,
        'dw_interpretation': ('positive autocorr' if dw < 1.5
                              else 'no autocorr' if dw < 2.5 else 'negative autocorr'),
        'ljung_box_p': lb['lb_pvalue'].values,
        'has_autocorrelation': any(lb['lb_pvalue'] < 0.05),
        'fix': 'Newey-West errors or include lag terms',
    }
```

### Multicollinearity (VIF)

```python
from statsmodels.stats.outliers_influence import variance_inflation_factor

def vif_test(X: pd.DataFrame) -> pd.DataFrame:
    """VIF > 10 severe; VIF > 5 watch."""
    vif = pd.DataFrame({'feature': X.columns})
    vif['VIF'] = [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]
    vif['concern'] = vif['VIF'].apply(lambda x: 'severe' if x > 10 else 'watch' if x > 5 else 'normal')
    return vif
```

**Regression diagnostics checklist**:
```
□ Linearity: residuals vs fitted show no pattern
□ Normality: QQ plot near straight line, Jarque-Bera p > 0.05
□ Heteroskedasticity: White/BP p > 0.05, or use HAC errors
□ Autocorrelation: DW ≈ 2, Ljung-Box p > 0.05
□ Multicollinearity: VIF < 5
□ Outliers: Cook's D < 4/n
```

---

## Bootstrap Methods

```python
def bootstrap_statistic(data, statistic_func, n_bootstrap=10000, confidence=0.95) -> dict:
    """Confidence interval for a statistic via nonparametric bootstrap."""
    n = len(data)
    stats_arr = np.array([
        statistic_func(np.random.choice(data, size=n, replace=True))
        for _ in range(n_bootstrap)
    ])
    alpha = 1 - confidence
    return {
        'point_estimate': statistic_func(data),
        'bootstrap_mean': np.mean(stats_arr),
        'bootstrap_std': np.std(stats_arr),
        'ci_lower': np.percentile(stats_arr, alpha/2 * 100),
        'ci_upper': np.percentile(stats_arr, (1 - alpha/2) * 100),
        'confidence': confidence,
    }
```

| Scenario | Method | Purpose |
|---|---|---|
| Sharpe CI | Bootstrap return series | Is Sharpe significantly > 0? |
| Factor return test | Bootstrap factor values | Is the premium robust? |
| Max drawdown distribution | Bootstrap equity paths | Distribution of MDD |
| Strategy A vs B | Paired bootstrap | Is A significantly better than B? |

```python
def bootstrap_sharpe(returns: pd.Series, n_bootstrap: int = 10000) -> dict:
    def sharpe(r):
        return r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else 0
    result = bootstrap_statistic(returns.values, sharpe, n_bootstrap)
    result['is_significant'] = result['ci_lower'] > 0  # 95% CI excludes 0
    return result
```

**Block bootstrap** if returns are autocorrelated — resample contiguous blocks, not iid points,
or the CI will be too tight.

---

## Hypothesis-Testing Framework

| Goal | Test | Null Hypothesis |
|---|---|---|
| Mean = 0 | t-test | μ = 0 |
| Two means equal | Independent t-test | μ1 = μ2 |
| Normality | Jarque-Bera | Normal |
| Stationarity | ADF | Has unit root |
| Autocorrelation | Ljung-Box | No autocorrelation |
| Heteroskedasticity | White / BP | Homoskedasticity |
| Cointegration | Engle-Granger | Not cointegrated |

### Multiple-Testing Problem

Testing 100 factors at p < 0.05 yields ~5 false positives by chance. When screening many
strategies/factors, multiple-testing correction is **mandatory**.

```python
from statsmodels.stats.multitest import multipletests
reject, p_adj, _, _ = multipletests(p_values, method='fdr_bh')  # Benjamini-Hochberg (recommended)
```
Bonferroni (`p × n`) is most conservative; Holm-Bonferroni is stepwise; Benjamini-Hochberg
(FDR) is the recommended default for factor/strategy screens.

### Sharpe Significance

```
H0: Sharpe = 0.  Test statistic: t = Sharpe · sqrt(n) / sqrt(1 + 0.5·Sharpe²)
where n = number of observation periods.

Rules of thumb:
- Sharpe > 0.5 and backtest > 5yr → may be significant
- Sharpe > 1.0 and backtest > 3yr → likely significant
- Sharpe > 2.0 → overfitting warning (hard to sustain live)
```

---

## Output Format

```markdown
## Statistical Testing Report

### Stationarity Test
| Series | ADF Statistic | p-value | Conclusion |
|--------|---------------|---------|------------|
| Price  | -1.23         | 0.65    | Non-stationary |
| Return | -15.8         | 0.000   | Stationary *** |

### Cointegration Test
| Pair          | Statistic | p-value | Cointegrated |
|---------------|-----------|---------|--------------|
| 600519/000858 | -4.52     | 0.002   | Yes ** |

### GARCH Model
| Parameter          | Value | Meaning |
|--------------------|-------|---------|
| α                  | 0.08  | Shock effect |
| β                  | 0.88  | Vol persistence |
| Long-run vol       | 22.5% | Annualized |

### Bootstrap Result
| Metric         | Point Est. | 95% CI        | Significant |
|----------------|------------|---------------|-------------|
| Sharpe         | 1.25       | [0.62, 1.88]  | Yes |
| Alpha (monthly)| 0.8%       | [0.1%, 1.5%]  | Yes |
```

---

## Notes & Cautions

1. **Financial data is non-normal** — return series are fat-tailed; be wary of tests assuming normality.
2. **Multiple testing** — FDR control is mandatory when screening many strategies/factors.
3. **Significance ≠ profitability** — statistical significance never substitutes for out-of-sample testing.
4. **Cointegration breaks down** — historical cointegration doesn't guarantee persistence; monitor pairs continuously.
5. **GARCH horizon is short** — forecast accuracy declines rapidly past 5–10 days.
6. **Small effective samples** — data can look large yet hold few *independent* observations (e.g. annual data).
7. **p-hacking** — predefine the testing plan; don't tune until p < 0.05.
