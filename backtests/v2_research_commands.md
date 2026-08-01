# VCP v2 research reproduction commands — 2026-08-01

Run from the repository root with the repo-local Python environment.

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt

# Build the 2016-2026 PIT symbol list directly from membership intervals and
# download all available stock histories plus benchmark-only SPY.
{ awk -F, 'NR > 1 && $2 <= "2026-06-30" && ($3 == "" || $3 >= "2016-07-01") {gsub(/\r/, "", $1); print $1}' scripts/data/sp500_membership.csv; printf 'SPY\n'; } \
  | sort -u | tr '\n' '\0' \
  | xargs -0 .venv/bin/python scripts/download_sp500_history.py \
      --output SP500_PIT_2016_2026_raw.csv \
      --start 2014-01-01 --end 2026-07-02 \
      --batch-size 50 --retries 1 --retry-delay 0 --sleep-secs 0 \
      --no-retry-missing --symbols

.venv/bin/python scripts/build_pit_universe.py \
  --survivors-csv SP500_PIT_2016_2026_raw.csv \
  --win-start 2016-07-01 --win-end 2026-06-30 \
  --out SP500_PIT_2016_2026.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json

.venv/bin/python scripts/backtest_vcp.py \
  --csv-data SP500_PIT_2016_2026.csv --limit 0 --years 10 \
  --no-support-resistance --workers 8 \
  --output-dir backtests/pivot_retest_v2/detections

# Substitute the timestamped detection JSON emitted by the preceding command.
DETECTIONS=backtests/pivot_retest_v2/detections/vcp_backtest_2026-08-01_120903.json
COMMON=(--price-csv SP500_PIT_2016_2026.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --iterations 1000)

.venv/bin/python scripts/pivot_retest_experiment.py "$DETECTIONS" "${COMMON[@]}" \
  --output-dir backtests/pivot_retest_v2/results \
  --entry-rule pivot_retest --strategy-name 'Pivot-Retest v2' \
  --frozen-spec backtests/pivot_retest_v2/frozen_spec.md --trials 195

.venv/bin/python scripts/pivot_retest_experiment.py "$DETECTIONS" "${COMMON[@]}" \
  --output-dir backtests/detection_entry_v2/results \
  --entry-rule detection_entry --strategy-name 'Immediate Post-Detection Entry v2' \
  --frozen-spec backtests/detection_entry_v2/frozen_spec.md --trials 196

.venv/bin/python scripts/pivot_retest_experiment.py "$DETECTIONS" "${COMMON[@]}" \
  --output-dir backtests/breakeven_1r_v2/results \
  --entry-rule pivot_retest --exit-rule breakeven_r \
  --strategy-name 'Pivot-Retest + 1R Break-Even Stop v2' \
  --frozen-spec backtests/breakeven_1r_v2/frozen_spec.md --trials 197

.venv/bin/python scripts/constructive_retest_discovery.py "$DETECTIONS" "${COMMON[@]}"

.venv/bin/python scripts/pivot_failure_train_gate.py "$DETECTIONS" "${COMMON[@]}"

.venv/bin/python scripts/two_close_breakout_train_gate.py "$DETECTIONS" "${COMMON[@]}"

.venv/bin/python scripts/first_down_close_train_gate.py "$DETECTIONS" "${COMMON[@]}"

.venv/bin/python scripts/down_close_pivot_hold_train_gate.py "$DETECTIONS" "${COMMON[@]}"

# Run only after the preceding train gate reports open_validation=true.
.venv/bin/python scripts/pivot_retest_experiment.py "$DETECTIONS" "${COMMON[@]}" \
  --output-dir backtests/down_close_pivot_hold_v2/results \
  --entry-rule down_close_pivot_hold --strategy-name 'Down-Close Pivot-Hold v2' \
  --frozen-spec backtests/down_close_pivot_hold_v2/frozen_spec.md --trials 206

.venv/bin/python scripts/pivot_reclaim_train_gate.py "$DETECTIONS" "${COMMON[@]}"

.venv/bin/python scripts/inside_day_breakout_train_gate.py "$DETECTIONS" "${COMMON[@]}"

.venv/bin/python scripts/train_feasibility_audit.py "$DETECTIONS" "${COMMON[@]}" \
  --output-dir backtests/train_feasibility_audit

.venv/bin/python scripts/stop_reentry_train_gate.py "$DETECTIONS" "${COMMON[@]}"

.venv/bin/python scripts/distribution_exit_train_gate.py "$DETECTIONS" "${COMMON[@]}"

.venv/bin/python scripts/loss_distribution_exit_train_gate.py "$DETECTIONS" "${COMMON[@]}"

.venv/bin/python -m pytest tests/ -q
```

## Corrected adjusted-scale rerun

The `DETECTIONS` variable above is retained only for invalidated audit-trail
reproduction. Correct work after the raw/adjusted OHLC fix uses:

```bash
ADJUSTED_DETECTIONS=backtests/adjusted_v2/detections/vcp_backtest_2026-08-01_132107.json

.venv/bin/python scripts/pivot_retest_experiment.py "$ADJUSTED_DETECTIONS" "${COMMON[@]}" \
  --output-dir backtests/adjusted_v2/pivot_retest_results \
  --entry-rule pivot_retest --strategy-name 'Adjusted Pivot-Retest Baseline' \
  --frozen-spec backtests/adjusted_v2/pivot_retest_frozen_spec.md --trials 212

.venv/bin/python scripts/five_day_low_train_gate.py "$ADJUSTED_DETECTIONS" "${COMMON[@]}"

.venv/bin/python scripts/low_reversal_train_gate.py "$ADJUSTED_DETECTIONS" "${COMMON[@]}"

.venv/bin/python scripts/pivot_open_limit_train_gate.py "$ADJUSTED_DETECTIONS" "${COMMON[@]}"

# Trials 254-255: physically train-truncated daily causal rescreen
awk -F, 'NR == 1 || $2 <= "2021-12-31"' SP500_PIT_2016_2026.csv \
  > backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv
.venv/bin/python scripts/backtest_vcp.py \
  --csv-data backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --limit 0 --years 10 --stride-days 1 --no-support-resistance --workers 8 \
  --output-dir backtests/daily_rescreen_v2/detections
.venv/bin/python scripts/train_feasibility_audit.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/daily_rescreen_v2/feasibility
.venv/bin/python scripts/daily_downclose_managed_gate.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/daily_downclose_managed_v2/results --iterations 1000

# Trial 256-272: purged daily ridge entry + causal score-decay exit
.venv/bin/python scripts/daily_score_decay_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/daily_score_decay_v2/results --iterations 1000

# Trial 273-287: fixed quadratic expansion, same purged joint score-decay rule
.venv/bin/python scripts/daily_score_decay_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/daily_quadratic_decay_v2/results --iterations 1000 \
  --model-type quadratic --trials-before 272 --new-multiplicity-units 15 \
  --trials-declared 287 \
  --family-spec backtests/daily_quadratic_decay_v2/family_spec.md \
  --result-prefix daily_quadratic_decay

# Trial 288: fixed hard-stop-aware 20-session continuation label
.venv/bin/python scripts/daily_score_decay_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/daily_forward20_decay_v2/results --iterations 1000 \
  --label-mode forward20 --trials-before 287 --new-multiplicity-units 1 \
  --trials-declared 288 \
  --family-spec backtests/daily_forward20_decay_v2/family_spec.md \
  --result-prefix daily_forward20_decay

# Trial 292: label-aligned fixed 20-session time exit
.venv/bin/python scripts/daily_score_decay_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/daily_forward20_fixed_exit_v2/results --iterations 1000 \
  --label-mode forward20 --exit-mode fixed20 --gate-cagr 10 --trials-before 291 \
  --new-multiplicity-units 1 --trials-declared 292 \
  --family-spec backtests/daily_forward20_fixed_exit_v2/frozen_spec.md \
  --result-prefix daily_forward20_fixed_exit

# Trial 293: repeated p85/p50 score-hysteresis lifecycle
.venv/bin/python scripts/daily_score_decay_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/forward20_score_lifecycle_v2/results --iterations 1000 \
  --label-mode forward20 --entry-mode lifecycle --exit-mode decay --gate-cagr 10 --gate-trades 40 \
  --trials-before 292 --new-multiplicity-units 1 --trials-declared 293 \
  --family-spec backtests/forward20_score_lifecycle_v2/frozen_spec.md \
  --result-prefix forward20_score_lifecycle

# Trial 294: p50 decay exits losses only; winners retain 60-session timeout
.venv/bin/python scripts/daily_score_decay_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/forward20_loss_decay_v2/results --iterations 1000 \
  --label-mode forward20 --entry-mode first --exit-mode loss_decay --gate-cagr 10 \
  --trials-before 293 --new-multiplicity-units 1 --trials-declared 294 \
  --family-spec backtests/forward20_loss_decay_v2/frozen_spec.md \
  --result-prefix forward20_loss_decay

# Trial 295: classify hard-stop-aware forward-20 winners >= +10%
.venv/bin/python scripts/daily_score_decay_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/daily_logistic10_decay_v2/results --iterations 1000 \
  --label-mode forward20 --model-type logistic --gate-cagr 10 \
  --trials-before 294 --new-multiplicity-units 1 --trials-declared 295 \
  --family-spec backtests/daily_logistic10_decay_v2/frozen_spec.md \
  --result-prefix daily_logistic10_decay

# SEC Company Facts cache and strictly as-filed coverage audit (no outcomes)
curl -L https://www.sec.gov/files/company_tickers.json \
  -o backtests/sec_pit_audit/company_tickers.json
.venv/bin/python scripts/sec_companyfacts.py \
  --tickers-json backtests/sec_pit_audit/company_tickers.json \
  --symbols-file backtests/sec_pit_audit/daily_detection_symbols.txt \
  --output-dir backtests/sec_pit_audit/companyfacts \
  --user-agent 'vcp-screener-research/1.0 research@example.com' \
  --workers 4 --delay .5
.venv/bin/python scripts/sec_fundamental_coverage.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --companyfacts-dir backtests/sec_pit_audit/companyfacts \
  --membership-csv scripts/data/sp500_membership.csv \
  --output-dir backtests/sec_pit_audit

# Trial 296: p70 timing plus fresh SEC dual EPS/revenue growth
.venv/bin/python scripts/sec_dual_growth_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --growth-events-json backtests/sec_pit_audit/sec_growth_events.json \
  --output-dir backtests/sec_dual_growth_v2/results --iterations 1000

# Trial 297-299: p70 density, loss-only score decay, 10%/3xATR chandelier
.venv/bin/python scripts/forward20_chandelier_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/forward20_chandelier_v2/results --iterations 1000

# Trial 300-302: setup-balanced k=15 nearest analogue model
.venv/bin/python scripts/forward20_knn_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/forward20_knn_v2/results --iterations 1000

# Trial 303-304: first active VCP state within 30d of dual-growth filing
.venv/bin/python scripts/sec_filing_window_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --growth-events-json backtests/sec_pit_audit/sec_growth_events.json \
  --output-dir backtests/sec_filing_window_v2/results --iterations 1000

# Outcome-free SEC Form 4 coverage and open-market purchase classification
.venv/bin/python scripts/sec_submissions.py \
  --tickers-json backtests/sec_pit_audit/company_tickers.json \
  --symbols-file backtests/sec_pit_audit/daily_detection_symbols.txt \
  --output-dir backtests/sec_pit_audit/submissions \
  --user-agent 'vcp-screener-research/1.0 YOUR_EMAIL@example.com' \
  --workers 4 --delay .5
.venv/bin/python scripts/sec_form4_coverage.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --submissions-dir backtests/sec_pit_audit/submissions \
  --membership-csv scripts/data/sp500_membership.csv \
  --output-dir backtests/sec_pit_audit
.venv/bin/python scripts/sec_form4_documents.py \
  backtests/sec_pit_audit/sec_form4_candidate_filings.csv \
  --output-dir backtests/sec_pit_audit/form4_raw_documents \
  --user-agent 'vcp-screener-research/1.0 YOUR_EMAIL@example.com' \
  --workers 4 --delay .5
.venv/bin/python scripts/sec_form4_purchase_coverage.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --candidates-csv backtests/sec_pit_audit/sec_form4_candidate_filings.csv \
  --documents-dir backtests/sec_pit_audit/form4_raw_documents \
  --membership-csv scripts/data/sp500_membership.csv \
  --output-dir backtests/sec_pit_audit

# Trial 305-307: last-contraction undercut/reclaim with shakeout-low stop
.venv/bin/python scripts/undercut_reclaim_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/undercut_reclaim_v2/results --iterations 1000

# Trial 308-309: hard-stop survival classifier, p70, fixed-20 exit
.venv/bin/python scripts/daily_score_decay_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/daily_survival20_v2/results --iterations 1000 \
  --label-mode survive20 --model-type logistic --entry-percentile 70 \
  --exit-mode fixed20 --gate-cagr 15 --gate-trades 60 \
  --trials-before 307 --new-multiplicity-units 2 --trials-declared 309 \
  --family-spec backtests/daily_survival20_v2/frozen_spec.md \
  --result-prefix daily_survival20

# Trial 310-311: positive fixed-20 classifier, p70, fixed-20 exit
.venv/bin/python scripts/daily_score_decay_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/daily_positive20_v2/results --iterations 1000 \
  --label-mode forward20 --model-type logistic --logistic-label-threshold 0 \
  --entry-percentile 70 --exit-mode fixed20 --gate-cagr 15 --gate-trades 60 \
  --trials-before 309 --new-multiplicity-units 2 --trials-declared 311 \
  --family-spec backtests/daily_positive20_v2/frozen_spec.md \
  --result-prefix daily_positive20

# Trial 312: expand recent fit through 2018, recalibrate on 2019-H2
.venv/bin/python scripts/daily_score_decay_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/expanded_fit_forward20_v2/results --iterations 1000 \
  --label-mode forward20 --model-type linear --entry-percentile 85 \
  --exit-mode decay --gate-cagr 15 --gate-trades 25 \
  --trials-before 311 --new-multiplicity-units 1 --trials-declared 312 \
  --fit-start 2016-07-01 --fit-end 2018-12-31 --fit-price-end 2019-06-30 \
  --calibration-start 2019-07-01 --calibration-end 2019-12-31 \
  --calibration-price-end 2019-12-31 \
  --holdout-start 2020-01-01 --holdout-end 2021-12-31 \
  --family-spec backtests/expanded_fit_forward20_v2/frozen_spec.md \
  --result-prefix expanded_fit_forward20

# Trial 313-315: p70 prove-it exit plus reset/re-entry lifecycle
.venv/bin/python scripts/prove_it_lifecycle_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/prove_it_lifecycle_v2/results --iterations 1000

# Trial 316-319: RSI(2)<10 entry, SMA(5)/five-session lifecycle
.venv/bin/python scripts/rsi2_lifecycle_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/rsi2_lifecycle_v2/results --iterations 1000

# Trial 320-323: 12-1 / five-session dual-momentum lifecycle
.venv/bin/python scripts/dual_momentum_lifecycle_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/dual_momentum_lifecycle_v2/results --iterations 1000

# Trial 324-327: prior-SMA20 opening limit with full-gap recovery exit
.venv/bin/python scripts/sma20_open_recovery_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/sma20_open_recovery_v2/results --iterations 1000

# Trial 328-333: same-date active-VCP 5d/20d cross-sectional leadership lifecycle
.venv/bin/python scripts/cross_sectional_leadership_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/cross_sectional_leadership_v2/results --iterations 1000

# Trial 334-339: signed 10-session path-efficiency crossover lifecycle
.venv/bin/python scripts/path_efficiency_lifecycle_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/path_efficiency_lifecycle_v2/results --iterations 1000

# Trial 340-344: causal 63-session stock/SPY relative-strength-line highs
.venv/bin/python scripts/rs_line_leadership_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/rs_line_leadership_v2/results --iterations 1000

# Trial 345-351: 20d/126d Bollinger bandwidth squeeze-release lifecycle
.venv/bin/python scripts/squeeze_release_lifecycle_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/squeeze_release_lifecycle_v2/results --iterations 1000

# Trial 352-357: detection-anchored typical-price/volume VWAP reclaim lifecycle
.venv/bin/python scripts/anchored_vwap_reclaim_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/anchored_vwap_reclaim_v2/results --iterations 1000

# Trial 358-362: 20-session Chaikin Money Flow zero-cross lifecycle
.venv/bin/python scripts/chaikin_money_flow_discovery.py \
  backtests/daily_rescreen_v2/detections/vcp_backtest_2026-08-01_141348.json \
  --price-csv backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/chaikin_money_flow_v2/results --iterations 1000

# Outcome-free public 2000-2005 data-source audit. The downloaded archives
# are temporary inputs and are not committed.
audit_dir=$(mktemp -d)
curl -L --fail --silent --show-error --max-time 600 --retry 2 \
  -o "$audit_dir/huge-stock-market.zip" \
  'https://www.kaggle.com/api/v1/datasets/download/borismarjanovic/price-volume-data-for-all-us-stocks-etfs'
curl -L --fail --silent --show-error --max-time 30 \
  -o "$audit_dir/wiki_tickers.csv" \
  'https://gist.githubusercontent.com/phibry/62d89ea7187f4257d66b3a612c581e05/raw/WIKI_PRICES.csv'
.venv/bin/python scripts/public_oos_data_audit.py \
  --stock-archive "$audit_dir/huge-stock-market.zip" \
  --wiki-tickers "$audit_dir/wiki_tickers.csv" \
  --membership-csv scripts/data/sp500_membership.csv \
  --start 2000-01-01 --end 2005-12-31 \
  --output-dir backtests/data_source_audit

# User-requested existing-data exploratory replay. Frozen before outcomes in
# backtests/exploratory_existing_data_replay/frozen_spec.md.
.venv/bin/python scripts/backtest_vcp.py \
  --csv-data SP500_PIT_2016_2026.csv --limit 0 --years 10 \
  --stride-days 1 --no-support-resistance --workers 8 \
  --output-dir backtests/exploratory_existing_data_replay/detections_date_aligned

.venv/bin/python scripts/daily_score_decay_discovery.py \
  backtests/exploratory_existing_data_replay/detections_date_aligned/vcp_backtest_2026-08-01_202358.json \
  --price-csv SP500_PIT_2016_2026.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --output-dir backtests/exploratory_existing_data_replay/results \
  --iterations 1000 --label-mode forward20 --trials-before 287 \
  --new-multiplicity-units 1 --trials-declared 288 \
  --family-spec backtests/exploratory_existing_data_replay/frozen_spec.md \
  --result-prefix trial288_existing_data_replay \
  --holdout-start 2022-01-01 --holdout-end 2026-03-31 \
  --evaluation-label '2022–2026 existing-data exploratory replay' \
  --exploratory-only

.venv/bin/python scripts/exploratory_existing_data_verification.py \
  backtests/exploratory_existing_data_replay/detections_date_aligned/vcp_backtest_2026-08-01_202358.json \
  backtests/exploratory_existing_data_replay/results/trial288_existing_data_replay_2026-08-01_202443.json \
  --price-csv SP500_PIT_2016_2026.csv \
  --membership-csv scripts/data/sp500_membership.csv \
  --output-dir backtests/exploratory_existing_data_replay/results

# Verification
.venv/bin/python -m pytest -q
git diff --check
```

`--no-support-resistance` is reproducibility-safe here because the support /
resistance overlay is additive and no S/R entry filter is enabled. It changes
runtime, not VCP detection decisions.

The 2000-2005 untouched OOS command is intentionally absent. All frozen
validation gates failed or their train gates prevented validation, so opening
that data would violate their specs. The required survivorship-safe 2000-2005
price/security-master dataset is also absent. Two public archives were audited
and rejected rather than treated as substitutes; see
`backtests/data_source_audit/public_oos_coverage.md` and
`backtests/adjusted_v2/completion_blocker_audit.md`.
