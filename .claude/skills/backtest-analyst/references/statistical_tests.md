# Statistical Tests Reference

## Probabilistic Sharpe Ratio (PSR)
Bailey & López de Prado (2012). Accounts for non-normality and finite sample.

```
PSR(SR*) = Φ [ (SR_hat - SR*) * sqrt(T - 1)
               / sqrt(1 - γ3*SR_hat + (γ4 - 1)/4 * SR_hat²) ]
```

Where:
- SR_hat = observed Sharpe Ratio
- SR* = benchmark Sharpe (usually 0 or category median)
- T = number of return observations
- γ3 = skewness of returns
- γ4 = excess kurtosis of returns
- Φ = standard normal CDF

Interpretation: PSR > 0.95 → 95% confident SR > SR*

## Deflated Sharpe Ratio (DSR)
Penalises for multiple strategy tests. Select the trial with max SR* such that:

```
SR* = sqrt(Var(SR)) * [ (1-γ) * Φ^{-1}(1 - 1/N) + γ * Φ^{-1}(1 - 1/(N*e)) ]
```

Where N = number of independent trials, γ = Euler-Mascheroni ≈ 0.5772

A DSR > 0.95 indicates the best observed SR is unlikely due to selection bias.

## Ljung-Box Test (Autocorrelation)
```
Q = T(T+2) * Σ_{k=1}^{m} ρ_k² / (T - k)
```
- Under H0 (no autocorrelation), Q ~ χ²(m)
- If p < 0.05, returns have significant autocorrelation
- Positive autocorrelation inflates Sharpe (divide by sqrt(1 + 2Σρ_k) to correct)

## Jarque-Bera Normality Test
```
JB = (T/6) * [S² + (K-3)²/4]
```
- S = skewness, K = kurtosis
- Under H0 (normal), JB ~ χ²(2)
- p < 0.05 → reject normality → use t-distribution with fat tails correction

## Effective Sample Size
```
n_eff = T / (1 + 2 * Σ_{k=1}^{L} ρ_k)
```
- Use n_eff (not T) in t-test denominator
- L = lag where autocorrelation drops below significance threshold

## Two-Sample Sharpe Test (IS vs OOS)
```
t = (SR_IS - SR_OOS) / sqrt(2/T)
```
- If t > 1.96 → IS and OOS Sharpes are significantly different → overfitting likely

## Maximum Drawdown Distribution (Monte Carlo)
Under IID returns, expected MDD scales approximately as:
```
E[MDD] ≈ σ * sqrt(2 * ln(T))
```
Compare actual MDD to this: if actual >> expected, fat-tailed risk or clustering.
