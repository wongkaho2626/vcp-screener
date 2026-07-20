# Frozen spec — 2016-2026 PIT re-measurement of the shipped MA20 pullback overlay

**Declared:** 2026-07-20, before any delisted-inclusive 2016-2026 detection or
trade result was computed. Follow-up predeclared by the pullback_oos closeout
("a 2016-2026 PIT rebuild via build_pit_universe.py is the natural
follow-up"). Nothing below changes after results are seen.

## Hypothesis and honest framing

The shipped MA20 pullback overlay's paired improvement (survivors-only
evidence: +1.36 pp t 3.13 on live data; +2.35 pp t 4.52 n 96 on the CSV
dataset, same code path as this experiment) **survives PIT discipline on its
own era** — delisted-inclusive universe, membership gating, delisted-inclusive
benchmark.

This is **NOT an out-of-sample test**: the rule is the winner of a 4-variant
scan developed on this very decade. It is a bias-correction re-measurement,
directly motivated by the pre-2016 reversal, where the identical survivor-only
design produced a false pass (+0.69 t 2.50 → +0.22 t 0.58 under PIT). A pass
here means "the shipped overlay's improvement is not purely a survivorship
artifact"; it cannot mean fresh alpha. A fail means the shipped overlay's
evidence base is gone and it should be demoted to research-only.

- **Declared direction:** paired Δ (pullback excess − breakout excess, same
  detection) > 0 under PIT discipline.
- **Success:** pooled Δ > 0, t ≥ 2, same sign both folds, trim signs hold.
- **Failure:** Δ ≤ 0, or |t| < 2, or fold sign-flip. Then the overlay is
  declared survivorship-suspect on its home era and the recommendation is to
  demote it from the live screen annotations (user's call to execute).

## Frozen rule (identical to shipped/prior, zero re-tuning)

1. Detection: `backtest_vcp.py` frozen defaults, `--limit 0 --years 10`,
   anchored at the PIT CSV's newest bar (≈ 2026-07 ⇒ scan ≈ 2016-07 →
   2026-07).
2. Legs, exits, metric: exactly as `pullback_oos_experiment.py` — breakout
   close (≤5% extension) vs `plan_pullback_entry` (window 15, MA20);
   `simulate_exit` stop max(pattern stop, entry−8%) + 60-bar timeout; paired
   Δ of excess vs the synthetic equal-weight benchmark of the PIT CSV.
   Costs cancel exactly in Δ (one round trip per leg).
3. Membership gate: detection counts only if the symbol was an S&P member on
   `as_of_date` (`--membership-csv scripts/data/sp500_membership.csv`).

## Data protocol (mirrors pit_addendum.md, modern window)

- Universe: 720 tickers with membership overlapping 2016-07-01 … 2026-06-30;
  221 missing from the survivors CSV are recovered via Yahoo
  (window 2014-01-01 → present), membership-overlap guarded.
- Build: `scripts/build_pit_universe.py --win-start 2016-07-01 --win-end
  2026-06-30` — per-interval trims (−730d/+130d), ±150% scale-break screen,
  ≥100 bars inside membership, curated same-entity aliases only. The alias
  table gains TMK←GL and ABC←COR (both successors already in the survivors
  CSV, same legal entity, rename dates 2019/2023) alongside the existing
  ANTM←ELV, BLL←BALL, HRS←LHX, UTX←RTX; CTL←LUMN via fresh fetch. No merger
  acquirers.
- **Pre-results amendment (2026-07-20, before any detection/trade was
  computed):** after the recovery sweep, the failure list exposed further
  unambiguous same-entity rename chains whose successors are already in the
  survivors CSV; added FB←META, RE←EG, FLT←CPAY, PEAK←DOC, HCP←DOC,
  WLTW←WTW, NLOK←GEN, SYMC←GEN. Judgment call documented: DOC (Healthpeak
  was the surviving parent in the 2024 Physicians Realty merger) and GEN
  (Symantec→NortonLifeLock→Gen Digital) are continuous share lines.
  CDAY/DAY and KORS/CPRI successors are absent from the CSV — not added.
  No further alias changes after first results.
- Coverage honesty rule (same schedule as pit_addendum): ≥90% member-day
  coverage ⇒ survivorship cap lifted; 70–90% ⇒ partially mitigated (≤55);
  <70% ⇒ cap stands at 20. Reported per year, with the unrecovered tail named.
- Benchmark sanity gate before any scoring: synthetic equal-weight daily
  extremes must be within ±15% (the TIE/CFC lesson).

## Folds, trims, multiplicity

- Folds: pair-date 2016-07-01…2020-12-31 vs 2021-01-01…2026-06-30.
- Trims: drop-top-5 and drop-top-10 paired Δ; sign must hold.
- Cross-universe: no PIT R2K data exists — not runnable, recorded.
- Multiplicity: ~181 prior trials on this price history, and the tested rule
  was selected in-sample from 4 variants on this era. DSR reported at N=4 and
  N=20 framings; a marginal p is not a pass.

## Give-up criteria

One evaluation round (plus reruns only for actual code/data bugs, e.g. a
failed benchmark sanity gate). No parameter changes, no alias additions after
first results, no fold/trim redefinition. Whatever the outcome, it supersedes
the survivor-only 2016-2026 CSV evidence for the overlay and is recorded in
CLAUDE.md + memory + a merged PR.
