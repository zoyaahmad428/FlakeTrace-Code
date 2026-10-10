# ADR-008 — When the failure does not reproduce: a given order, valid shuffled orders, and an honest report

**Date:** 2026-10-10 · **Status:** `PROPOSED` — chosen by M2; it **changes the report contract**
(`eval/schema/report.schema.json`, Member 3's file) and asks Member 3 for two fixture cases, so it
needs M3's agreement before any of that code is written, and M1's for information · **Owner:** M2
(runner, CLI) with M3 (schema, report assembly, decision table, fixtures) · **Builds on:**
[[03-Design/decisions/ADR-004-w7-diagnosis-runs]], [[03-Design/decisions/ADR-005-w9-diagnose-cli]],
[[03-Design/decisions/ADR-007-w10-ddmin-minimisation]] · **Research basis:**
[[01-Literature/parameter-provenance]], [[01-Literature/references]]

## Context

`diagnose()` runs the original order up to n = 20 times. If the victim never fails for a real reason,
it returns `NOT_REPRODUCED` and stops: it never runs the victim alone, so `decide()` rejects it
(`isolation_n > 0`), and the schema requires a `failure_signature` that a non-reproduced failure does
not have. The command exits 3 with no report.

On real projects "it failed in CI and I cannot reproduce it" is common, and two things make our
current answer weak:

1. **The order we repeat may be the wrong one.** It is the order we discovered (alphabetical), not
   the order CI ran. If the failure needs another order, 20 repetitions of ours can never find it.
   The research tools start from the actual failing order and detect order dependence by reordering
   (iDFlakies [3]; Shi et al. define a victim by running the failing order and running it alone [4]).
2. **No number of reruns proves a test reliable.** Alshammari et al. found new non-order-dependent
   flaky tests after 10,000 reruns [14] (as recorded in `parameter-provenance.md`). A report must state
   what was tried and the statistical bound, never "this test is fine".

## Decision

### Flow (`run_steps`)

| # | Step | Change |
| --- | --- | --- |
| 0 | Starting order | discovered as today, **or given by the user** (`--order <file>`, the real failing order) |
| 1 | Reproduce: the starting order up to n times, stop at the first real failure | unchanged |
| 2 | **Find a failing order** — only if step 1 saw no real failure | up to **31 distinct valid shuffled orders**, one run each; the first real victim failure makes that order the failing order and becomes the reference signature |
| 3 | Victim alone ×n | runs **always**. Without a reference (nothing reproduced), any real failure counts, and the first one becomes the reference |
| 4 | One-by-one search, `ddmin`, verify ×n | unchanged, on the failing order from step 1 or 2 |

Results: reproduced in step 1 or 2 → exactly today's pipeline and outcomes, with
`original_failing_order` = the order that actually failed. Not reproduced but fails alone (real
failure) → `VICTIM_FAILS_ALONE` with that signature (ordinary flakiness, not order dependence [4]).
Nothing failed anywhere → `NOT_REPRODUCED` with every count.

Step 2 shuffles the **whole** order (all tests, also those after the victim in the starting order):
in another order a test that originally ran after the victim may pollute it. The pipeline then cuts
the failing order after the victim, as today.

### Valid shuffled orders (`runner/orders.py`)

- From seed `s`: group the full order by class (methods stay together), shuffle the classes, then the
  methods inside each class, with `random.Random(s)`; join; cut after the victim. **Methods of different
  classes are never interleaved** — JUnit cannot produce such an order, and iDFlakies' class-first
  shuffling detected the most flaky tests [3] (both recorded in `parameter-provenance.md`).
- Seeds `base, base+1, …` (`--seed`, default 0). Every seed tried is in the execution record with its
  order and outcome, so any shuffle can be replayed.
- **Distinct orders only.** A seed that yields an order already tried is skipped, not counted. The
  phase stops at the budget or when no new order appears within 10 × budget seeds, and reports the real
  number (e.g. "2 distinct orders, all possible").
- During shuffling a run "reproduces" only with a real exception; a crash, timeout or skip is counted
  as an infrastructure failure, never as a reproduction.
- Execution-record step label `"shuffle"`, with a `seed` field on those lines.

### Budget: 31 shuffled orders

Gruber et al. report about 31 random-order executions for 95% confidence that a test is not
order-dependently flaky, versus about 170 same-order runs for the non-order-dependent case [12]. This
is the only published confidence figure for this question in our research notes, so it is the
default (`--shuffles N`, `0` turns the phase off). **Assumption, stated as such:** [12] studies
**Python** projects; that the figure carries over to JUnit is not shown, and the ADR, the report text
and the claims ledger say so. Shuffled orders used as a comparison baseline elsewhere (10, Rahman et
al. [5]) do not carry a confidence claim and are not used here.

Worst case per non-reproduced diagnosis: 20 + 31 + 20 = 71 JVM runs. F1, F2, F3, N1, N2 reproduce in
step 1 or fail alone and never reach step 2, so their run counts do not change.

### `DiagnosisRuns` (ours; all new fields have defaults)

`order_given: bool = False`, `shuffled_orders: int = 0`, `orders_exhausted: bool = False`,
`shuffle_seed_base: int = 0`, `reproducing_seed: Optional[int] = None`,
`infrastructure_failures: int = 0` (victim runs that only crashed or timed out).

### Report contract — proposal to Member 3 (needs all three members)

| Change | Rule | Reason |
| --- | --- | --- |
| `failure_signature` may be `null` | only with `outcome = UNRESOLVED` and `unresolved_reason = NOT_REPRODUCED` (same conditional pattern the schema uses for `unresolved_reason`) | a signature for a failure that never reproduced would be invented |
| new optional field `order_exploration` | `{order_given, shuffled_orders_tried, orders_exhausted, seed_base, reproducing_seed}`; optional, so every existing report stays valid | the `NOT_REPRODUCED` claim rests on how many orders were tried; when a shuffle reproduced, `reproducing_seed` lets anyone replay that order |
| new reason `INFRASTRUCTURE_FAILURE` | the victim never failed for a real reason, only crashed or timed out (one new row in `decide()`) | today such runs read as `SIGNATURE_MISMATCH`, which suggests a different real bug (M3's own earlier point) |
| `assemble_report` accepts `NOT_REPRODUCED` | `polluters = []`, `reduced_sequence` = the repeated order, `reproduction` = 0/n, `victim_alone` = 0/n | — |

Proposed `limitations` text for `NOT_REPRODUCED` (written by M3's `assemble_report`; numbers computed
with `eval.stats.wilson_interval`, never typed): *"Not reproduced: 20 runs of the given order, 31
distinct shuffled orders, 20 runs alone. In the given order the failure rate is below 0.161 with 95%
confidence (Wilson). This is not evidence that the test is reliable: flaky tests have been found only
after thousands of reruns."* (0/20 → upper bound 0.161; 0/31 → 0.110, measured 2026-10-10.)

### Command (`runner/cli.py`)

- `--order <file>`: one `Class#method` per line; blank lines and `#` lines ignored. Exit 2 if the file
  is missing or empty, a line is not `Class#method`, a test repeats, the victim is absent, or **a listed
  test is not one of the project's tests** (checked against discovery, one listing run; otherwise a typo
  would fail with `ClassNotFoundException` and could be mistaken for a reproduction).
- `--shuffles N` (default 31), `--seed S` (default 0).
- Summary lines when relevant, e.g. `orders: reproduced in shuffled order (seed 17) after 9 of 31
  orders`, or for `NOT_REPRODUCED` the counts and the bound with "not proof of reliability".
- `NOT_REPRODUCED` becomes a report with exit 0 once M3's change lands. Until then the command keeps
  today's exit 3, because it already catches `UnhandledStatus` (ADR-005) — so M2's part can land first.

## Alternatives considered

| Alternative | Why not |
| --- | --- |
| Report honestly, no order search | Cannot find failures that need another order; the user's real CI order is ignored |
| Order search without `--order` | The research tools start from the real failing order; `diagnose()` already accepts one |
| A separate `explore` command | Two commands and a manual hand-off; `diagnose` alone would still never try other orders |
| Reuse M3's `run_random_order_baseline` for shuffling | It is the comparison the evaluation measures FlakeTrace against — using it inside the product breaks that independence; it also interleaves classes, which JUnit cannot produce [3] |
| 10 or 20 shuffles | 10 is a comparison-baseline convention [5] with no confidence claim; 20 has no published basis for this purpose |
| Unlimited shuffling | No published stopping point; cost without a stated confidence |

## Consequences and limitations

- The 31-order budget is transferred from a Python study [12] (assumption, labelled).
- Random valid orders are not a systematic search; systematic order generation [29] and pair-coverage
  analysis of random orders [28] are listed in our references and are candidates for Iteration 2, after
  a member has read them.
- The user writes the `--order` file (e.g. from the CI log's "Running …" lines); parsing Maven or
  Surefire logs automatically is a separate future change.
- A non-reproduced diagnosis costs up to 71 JVM runs; measured on N3 when it exists.
- Inherits ADR-003/004/005/007 limits.

## Verification plan

1. Fake-runner tests (`runner/tests/test_orders.py`, `test_diagnose.py`): methods of one class stay
   together; same seed → same order; duplicates skipped and counted honestly; a two-order suite stops
   at 2; the victim is present and the order cut after it; a shuffle that reproduces → the pipeline
   continues on it with `reproducing_seed` set; nothing reproduces → `NOT_REPRODUCED`, alone 0/n, all
   counts; a real alone failure without reference → `VICTIM_FAILS_ALONE`; crash-only runs → counted as
   infrastructure failures.
2. CLI tests: every `--order` check (especially an unknown test) exits 2 before tests run.
3. **New fixture cases requested from M3**, ground truth written before any run:
   **F4** (polluter class sorts after the victim, so only a shuffle reproduces; expected `VERIFIED`,
   seed recorded) and **N3** (fails only when an environment variable such as `CI=true` is set, which
   FlakeTrace never sets; expected `UNRESOLVED(NOT_REPRODUCED)`).
4. Real runs: F4 via a shuffle → `VERIFIED`; N3 → `NOT_REPRODUCED` report with the bound (after M3's
   schema change); F1, F2, F3, N1, N2 unchanged with the same run counts.
5. Mutation checks (cross-class interleaving allowed; duplicate orders counted) must fail the tests; a
   fresh reviewer reviews the branch before the PR.

## Order of work

| # | Step | Who | Depends on |
| --- | --- | --- | --- |
| 1 | This ADR approved | M2 | — |
| 2 | ADR-008 PR — M3 agrees (schema, report text, fixtures); M1 informed | M2 opens | 1 |
| 3 | F4, N3 + ground truth; schema; `assemble_report`; `decide()` row | M3 | 2 |
| 4 | `orders.py`, `run_steps` phases, `DiagnosisRuns` fields, CLI options (fake runner first) | M2 | 2 |
| 5 | Real runs on F4/N3, review, CI | M2 | 3, 4 |
| 6 | Docs: claims, demo plan, iteration plan (new work package), note to M3 on panel action A5 | M2 | 5 |

## Agreement

| Member | Agree? | Comment |
| --- | --- | --- |
| M1 | ☐ | for information: no change to `evidence/` |
| M2 | ☑ | Chose a given order + 31 valid shuffles + the honest report, one diagnosis flow, on 2026-10-10 |
| M3 | ☐ | schema change (`failure_signature` null for NOT_REPRODUCED, `order_exploration`, `INFRASTRUCTURE_FAILURE`), `assemble_report`, `decide()` row, fixtures F4 and N3 |
