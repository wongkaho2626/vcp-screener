---
name: quant-experiment
description: >
  Autonomous quant research loop for the vcp-screener repo: generate a predeclared
  trading-strategy hypothesis, implement it as a TDD experiment CLI, run it on offline
  CSV data, then evaluate with the backtest-analyst skill and iterate until the
  Backtest Score reaches 80 ("Tradeable") or the experiment is formally abandoned and
  its null result recorded. Use this skill whenever the user wants to "run a new
  experiment", "test a new entry/exit idea", "find an edge", "try a new signal or
  overlay", "improve the strategy", or names any candidate rule (pocket pivot,
  gap-up entry, RSI filter, earnings drift, sector rotation, etc.) to backtest in
  this repo — even if they don't say the word "experiment". Also use it when the
  user asks "what should we test next" or "figure out an idea and test it".
---

# Quant Experiment Loop

You are running one full cycle of the research programme this repo was built around:
**hypothesis → frozen spec → TDD implementation → offline backtest → robustness bar →
backtest-analyst score → iterate or bury it**. Roughly 20 experiments have run before
this one; almost all died. That is not failure — a cleanly recorded null is the
normal, successful output of this loop. Your job is to make the *next* experiment
just as honest, whatever the result.

Read `references/playbook.md` before implementing — it has the concrete script/test
templates, commands, data caveats, and report conventions this repo uses.

## The mindset (why the rules below exist)

1. **The graveyard is load-bearing.** CLAUDE.md's "Established results" section lists
   every idea already tested to a null (entry gates, exit rules, regime gates,
   valuation, fib fills, rebreaks, pocket pivots…). Never re-run a buried idea
   without genuinely new data or a genuinely different mechanism — the same history
   will give the same answer, and each extra trial deepens the multiple-testing
   penalty for every future experiment.

2. **Prespecify, then freeze.** Decide the exact rule, parameters, entry/exit,
   costs, and success metric *before* looking at any results, and write them down in
   the report header as the "frozen spec". If a later sensitivity scan finds a better
   cell, note it for prospective validation on future data — never swap it in. This
   repo has already killed several shiny numbers (edges==3 gate, MA-break exits,
   stop-only +24% mean) that existed only because someone peeked first.

3. **The metric is excess, not raw return.** 2016–2026 is a bull tape; raw returns
   are mostly beta. Judge every effect on per-trade excess vs SPY over the trade's
   own holding dates (or exposure-matched excess for portfolio-level runs). Present
   raw returns only as context, clearly labelled.

4. **The robustness bar is mandatory, not optional.** Any claimed effect must
   survive all three prongs before you believe the mean:
   - time-fold split: 2016–2020 vs 2021–2026 (same sign, comparable size);
   - outlier trim: drop-top-5 and drop-top-10 trades (effect shouldn't flip);
   - cross-universe: replicate on the Russell 2000 set where data exists.
   Most prior "edges" died on exactly one of these prongs. Run them before writing
   any conclusion.

5. **Multiplicity is cumulative.** ~180+ strategy trials have already touched this
   same price history. backtest-analyst's Deflated Sharpe Ratio will (correctly)
   punish that. State the approximate trial count honestly in the report; do not
   reset the counter because "this idea is different".

6. **Causality discipline.** Signals may use only as-of and prior data
   (`as_of_date` fields, windows ending on the signal bar); fills are next-session
   open; `forward_outcome` fields are never consulted by the rule. Costs: 10 bps
   per side baseline with a 20/50/100 bps stress table.

## The loop

### Step 1 — Hypothesis

If the user supplied an idea, check it against CLAUDE.md "Established results" and
the memory index first. If it (or a close cousin) is already buried, say so, cite
the prior result, and either stop or propose the nearest genuinely-untested variant.

If no idea was supplied, generate 2–3 candidates that are *not* in the graveyard,
say which you're picking and why, and proceed with the best one. Prefer ideas that
test a **new mechanism or new data**, not a re-parameterisation of a dead one.

Then write the **frozen spec** — rule, parameters, universe, entry/exit, costs,
metric, robustness bar, and the give-up criteria from Step 5 — into the report file
*before* running anything.

### Step 2 — Implement (TDD)

One CLI file: `scripts/<name>_experiment.py`, taking a backtest/trades JSON +
`--price-csv`, writing a timestamped markdown report (and JSON) under
`backtests/<name>/`. Pure decision logic goes in importable functions; write
synthetic-bars pytest tests in `tests/test_<name>_experiment.py` **first** (red),
then implement (green). The full suite (`python3 -m pytest tests/ -q`) must stay
green. See the playbook for the standard script skeleton and segment definitions.

### Step 3 — Run

Run offline against `SP500_Historical_Data.csv`. **Always verify
`api_stats.data_source == "csv"` in the output metadata** — a silent yfinance
fallback once produced garbage results here. Then run the three robustness prongs
and the cost-stress table.

### Step 4 — Evaluate with backtest-analyst

Invoke the **backtest-analyst** skill (Skill tool, `backtest-analyst` — do not
reimplement its rubric ad hoc) on the experiment's outputs. Produce its full
verification report, ending in the component-scored 0–100 Backtest Score, and save
it as `backtests/<name>/verification_report.md`.

### Step 5 — Iterate or give up (the honest part)

Target: **score ≥ 80 (Tradeable)**. After each evaluation, classify what is holding
the score down, and act accordingly:

- **Fixable methodology gaps** — missing OOS split, missing cost stress, missing
  bootstrap/Monte-Carlo, unverified bias, wrong metric: fix the *analysis*, rerun
  the evaluation. These are legitimate iterations.
- **"The rule just doesn't work"** — weak t-stat, fold sign-flip, trim-fragile
  mean, negative excess: this is a **result, not a bug**. Do NOT tune parameters,
  swap in a better sensitivity cell, relax costs, or change the metric to chase the
  score — that is data snooping and it invalidates the experiment. Give up.
- **Structural data caps** — know these upfront: the current CSV universe is
  survivorship-biased, which hard-caps ANY score at **20** in the analyst's rubric;
  no true walk-forward caps at 55. On the current data, 80 is unreachable no matter
  how good the rule is. If the raw (pre-cap) component score would clear ~65 and
  the *only* remaining blockers are data caps, stop iterating and report exactly
  that: "promising rule, blocked on survivorship-safe data" — and tell the user
  what data would lift the cap. Do not pretend more iterations can fix a data cap.

Hard limits: at most **3 evaluation rounds**, and stop immediately once the only
blockers are structural. Reaching 80 in this repo is *supposed* to be nearly
impossible — the score protects the user's capital; do not negotiate with it.

### Step 6 — Record (always, win or lose)

Whatever the outcome:
1. Save the final `verification_report.md` under `backtests/<name>/`.
2. Add the result (score, verdict, one-paragraph mechanism + failure mode) to the
   **Established results** section of CLAUDE.md, dated, so it enters the graveyard.
3. Write a memory file summarising the null/finding (follow the existing pattern,
   e.g. `fib-pocket-pivot-null.md`) and index it in MEMORY.md.
4. Commit with a conventional message (`feat:`/`docs:`) whose body records the
   experimental result — `git log` doubles as the lab notebook here. Ask before
   pushing.

### Final message to the user

Lead with the verdict: score, band, and the one-sentence reason. Then: what was
frozen, what survived/died on the robustness bar, which caps applied, and — if
abandoned — what (if anything) would justify revisiting it. Never lead with a raw
return number.
