# Backtest Verification Report — pullback_oos (pre-2016 OOS replication of the MA20 pullback entry)

Evaluated: 2026-07-18 · backtest-analyst · **Round 3 — PIT replay (final; supersedes rounds 1-2)**
Chain: round 1 scored the survivor-only run; round 2 reproduced it with refinements
(pre-cap 71); round 3 executed the predeclared PIT protocol (`pit_addendum.md`,
frozen before any PIT result) on a delisted-inclusive universe. Per that
addendum, **this round's verdict supersedes the survivor-only result.**

## Backtest Score: 12 / 100 — Reject. **Failure to replicate on delisted-inclusive data.**

The survivor-only "first OOS pass" (paired Δ +0.69, t 2.50, n 196) does **not**
survive the PIT universe: Δ +0.22, t 0.58, fold sign-flip, trim sign-flips.
The round-1 pass is attributed to survivorship bias, exactly as the round-1
report's #1 red flag warned ("pullback entries buy weakness, and weakness in
survivors recovers more often"). The experiment closes as a null.

| Component | Score | Max |
|---|---|---|
| A. Statistical Validity & Significance | 4 | 30 |
| B. Risk-Adjusted Performance | n/a — redistributed | 25 |
| C. Robustness & Out-of-Sample | 2 | 25 |
| D. Trade Quality & Consistency | 6 | 20 |
| **Raw total (reduced basis A+C+D = 75)** | **12/75 → 16/100** | |
| Caps applied | residual survivorship (coverage 69.7% < declared 70%) → 20 | |
| **Final score** | **12** (raw already below cap) | 100 |

## The PIT dataset (what changed vs rounds 1-2)

- Universe: 735 tickers with S&P 500 membership overlapping 2006-2015
  (`scripts/data/sp500_membership.csv`, fja05680); 443 with usable prices.
- Recovered 175+ missing members via Yahoo (incl. genuinely delisted names,
  e.g. AET, TWX, ESRX-era) + 7 curated same-entity rename aliases (ANTM←ELV,
  BLL←BALL, HRS←LHX, UTX←RTX, CTL←LUMN, TMK←GL, ABC←COR). One wrong alias
  (CB = ACE Ltd, not old Chubb) caught and discarded. Stooq unusable
  (JS anti-bot wall — not circumvented, by policy).
- Quality gates (`scripts/build_pit_universe.py`, tested): per-interval trims
  (membership −730d/+130d) expelled wrong-entity reused tickers (new
  DELL/DOW/CEG, SUN LP…); ±150% scale-break screen dropped 8 corrupt series
  (TIE, CFC, BMC, BOL, CBE, CITGQ, CPWR, MEE) which had poisoned a first PIT
  attempt (equal-weight benchmark showed ±1900% days; that run was discarded
  and detection re-run on clean data — benchmark now: worst −10.2%/best
  +11.6%, plausible crisis extremes).
- **Member-day coverage: 69.74%** (2006: 60.7% → 2015: 77.4%). Unrecovered
  names concentrate in crisis-era corpses (LEH, WAMUQ, BSC, ABI…) and
  Yahoo-purged names (BK, CMA, WBA, MMC, SEE — persistent 404s).
- Detections membership-gated at `as_of_date`
  (`pullback_oos_experiment.py --membership-csv`, tested); 38 non-member
  detections dropped. Benchmark = equal-weight of the PIT universe
  (delisted-inclusive — more honest than rounds 1-2).

## Headline result (PIT, frozen rule unchanged)

| Metric | Survivor-only (r1-2) | **PIT (r3, final)** | Declared bar | Verdict |
|---|---|---|---|---|
| Paired Δ mean | +0.688 | **+0.224** | > 0 | sign ok |
| t | 2.50 | **0.58** | ≥ 2 | **FAIL** |
| Bootstrap P(mean≤0) | 0.6% | **27.5%** | — | no evidence |
| Fold 2006-2010 | +0.23 | **−0.71 (t −1.05)** | same sign | **FAIL (flip)** |
| Fold 2011-2015 | +1.08 | +0.96 (t 2.04) | same sign | ok |
| Drop-top-5 / 10 | +0.41 / +0.22 | **−0.20 / −0.42** | sign holds | **FAIL (flip)** |
| Δ profit factor | 1.65 | 1.16 | — | marginal |
| Win% / median | 63.8 / +1.02 | 59.4 / +0.76 | — | positive but weak |
| n pairs | 196 | 133 | ≥30 | ok |

## Attribution (why the effect died)

Shared-detection decomposition (105 detections appear in both runs):

- On **shared** detections, Δ is nearly identical: +0.45 (survivor benchmark)
  vs +0.40 (PIT benchmark) — benchmark choice is not the story.
- The **28 new pairs on recovered/delisted names average ≈ −0.43** — the
  adverse selection the paired design was supposed to be immune to shows up
  exactly where the missing names return.
- The **91 survivor-run pairs absent under PIT** construction (bars trimmed
  to membership, detections shifted by delisted-inclusive RS) averaged
  ≈ +0.96 — the survivor run's strongest pairs lived disproportionately in
  data that PIT discipline removes.

Yearly pattern persists in weaker form (2012-2014 positive, choppy/bear years
negative) — consistent with rounds 1-2's fold asymmetry: whatever residual
effect exists is regime-local (trending tape), not a general property.

## Bias assessment (delta vs rounds 1-2)

| Bias | Status | Note |
|---|---|---|
| Survivorship | **Partially resolved, and decisive** | Coverage 69.7% just misses the predeclared 70% "partially mitigated" line, so the residual-bias cap (20) formally stands — but the raw score (12) is below the cap anyway; the question answered itself. |
| Lookahead | Absent | Unchanged (truncation-invariance test; membership gate uses only as-of-date public info). |
| Data quality | **Handled, material** | First PIT attempt was invalidated by corrupt Yahoo series (TIE/CFC…); scale-break screen + rebuild + detection re-run fixed it. This failure mode is now codified in `build_pit_universe.py`. |
| Snooping | Absent | PIT protocol frozen in `pit_addendum.md` before results; zero rule changes; supersession rule declared in advance. |

## Verdict

**12/100 — Reject. The pre-2016 replication of the MA20 pullback entry fails
on delisted-inclusive data.** Per the predeclared addendum, this supersedes
the survivor-only pass: the +0.69 pp / t 2.50 result was substantially a
survivorship artifact, with the residual (+0.22, ns) too weak and too
fold/trim-fragile to count as evidence. Programme implications:

1. The 2006-2015 decade is closed as a confirmation set; result: null.
2. The shipped overlay's 2016-2026 evidence (own-era validation, R2K
   replication) stands on its own but should be read more cautiously — its
   era's CSV is also survivors-only, though bias is smaller nearer the
   snapshot date. A 2016-2026 PIT rebuild via `build_pit_universe.py` is the
   natural follow-up if the user wants one.
3. Positive residue: the repo now has reproducible PIT tooling
   (`build_pit_universe.py`, membership gate in the experiment CLI, coverage
   accounting) that any future experiment can use from day one.
