# ADR-007 — W10: find several polluters by delta-debugging the failing order

**Date:** 2026-10-10 · **Status:** `PROPOSED` — chosen by M2; the multi-polluter report rule
(§ Evidence and report) applies agreed rules to a new case and needs M1's and M3's confirmation ·
**Owner:** M2 · **Work package:** W10 · **Builds on:**
[[03-Design/decisions/ADR-004-w7-diagnosis-runs]], [[03-Design/decisions/ADR-005-w9-diagnose-cli]]

## Context

W7's polluter search runs `[candidate, victim]` once per earlier test. It finds a **single**
polluter. Fixture F3's victim fails only when **both** `ToggleAPolluterTest#setFlagA` and
`ToggleBPolluterTest#setFlagB` ran before it (in either order), so the search ends
`NO_SINGLE_POLLUTER` after 12 runs and the W9 command exits 3 with no report.

FR-5 asks for minimisation "with 1-minimality deletion checks and counterfactual checks",
preserving multi-test candidates. `parameter-provenance.md` fixes the claim: **1-minimal, never
"minimum"**: delta debugging returns a 1-minimal set and may miss other polluter combinations.

Real projects have hundreds of tests before a victim and do have multi-polluter cases, so the
product has to find and report them. (The one-by-one search before it already costs one run per
earlier test; `ddmin` itself shrinks a long prefix in far fewer runs than that.)

## Decision

**Delta debugging (`ddmin`, Zeller) over the tests before the victim, only when W7's one-by-one
search finds nothing.** F1/F2 cost exactly what they cost today.

### Flow in `run_steps` (steps 1–3 unchanged)

| # | Step | Result |
| --- | --- | --- |
| 1 | Reproduce the original order | reference signature, or `NOT_REPRODUCED` |
| 2 | Victim alone ×n | `VICTIM_FAILS_ALONE` if it fails ≥ 1 time |
| 3 | One-by-one search | `POLLUTER_FOUND` with one polluter |
| 4 | **New: `ddmin`** over the tests before the victim | a 1-minimal set, e.g. `[setFlagA, setFlagB]` |
| 5 | Verify ×n on `minimal set + victim`, original relative order | counts for `decide()` |

### `DiagnosisRuns`

- Step 4 succeeding gives `status = POLLUTER_FOUND` with **one or more** `polluters` (F3:
  `[setFlagA, setFlagB]`) and `sequence = polluters + [victim]`. The status is reused because M3's
  `assemble_report` already accepts it: F3 gets a report with no change in `eval/`, and the
  command's exit 3 for F3 disappears. "Polluter found" now means "one or more polluters found".
- New field `minimise_runs: int = 0`: the JVM runs `ddmin` made. The default keeps every existing
  `DiagnosisRuns(...)` call (M3's tests, our fakes) working.
- **The full order is run once more before `ddmin`** (counted in `minimise_runs`). Only if it fails
  again with the reference signature is it minimised; otherwise the failure was flaky. With one
  earlier test, `ddmin` is skipped: the search already ran exactly `[test, victim]` and saw it pass.
  *(Added after the final review: without it, a failure seen only once blamed every earlier test.)*
- `NO_SINGLE_POLLUTER` remains for: the victim first in the order; one earlier test that did not
  reproduce; or a full order that did not fail again. No polluter is invented.
- `ddmin` runs go through `RecordingRunner` with the step label `"minimise"`.

### `ddmin` (`runner/minimise.py`)

`ddmin(runner, prefix, victim, reference) -> (minimal: List[TestIdentifier], runs: int)`

- **Check** (one JVM run): `subset + [victim]` in original relative order "still fails" only if the
  victim fails with the **reference signature**. A crash, timeout, skip or other exception counts
  as "does not fail" — W7's rule — so a broken run never drops a needed test.
- **Loop:** start from the whole prefix (known to fail from step 1, not re-run) with `k = 2`
  chunks. Try each chunk alone; if one fails, keep only it (`k = 2`). Else try each complement; if
  one fails, keep it (`k = max(k − 1, 2)`). Else, if `k` equals the set size, stop; otherwise
  `k = min(2k, size)`. A set of size 1 is final (the victim alone passed in step 2).
- **1-minimal by construction:** the last round, at `k` = size, tried removing each test alone.
- **Cache:** a subset is run at most once per diagnosis.
- Written against any `OrderRunner`, so it is tested with `FakeOrderRunner` like `search.py`.

### Evidence and report for several polluters (`runner/cli.py`)

M1's pair mode per polluter (`analyse_test` for each polluter, the victim once, `find_edges`,
depth 2), combined by a small pure function:

| Case | Report fields |
| --- | --- |
| One polluter | exactly as today (`report_fields(pair)`) |
| Every polluter has ≥ 1 edge | the first polluter's `report_fields`; one `limitations` line per other polluter naming its resource ("Polluter X: shared resource R is not shown in this report"); M1's fixed limitation lines once → F3 `VERIFIED` with `flagA` shown and `flagB` named |
| Some polluter has no edge | no resource fields → `UNRESOLVED(NO_SUPPORTED_RESOURCE_EVIDENCE)`; `limitations` lists the edges found and names the polluter(s) without one |

`VERIFIED` must mean every blamed test has a found mechanism. This reuses two agreed rules ("first
edge shown, the rest in `limitations`"; "no edge → `NO_SUPPORTED_RESOURCE_EVIDENCE`") on a new
case, so M1 and M3 confirm it here. **Long-term shape:** one evidence edge per polluter in the
report — proposed for the schema change already under discussion with M3. Since M1's ADR-006 landed
(PR #34), the per-polluter loop calls `analyse_pair` once per polluter, so each pair deepens on its
own; a named (not shown) edge above depth 2 carries its depth in its `limitations` line, measured like
`report_fields` does for the shown edge. In the mixed case the fields carry `any_edge_found`, which
M3's `assemble_report` uses (PR #38) to leave out its generic "no edge" line.

## Alternatives considered

| Alternative | Why not |
| --- | --- |
| One-at-a-time deletion to a fixpoint | Simplest, also 1-minimal, but at least one JVM run per earlier test — slow on a 500-test prefix |
| Bisection (iFixFlakies' fast path) | Fast for one polluter (already W7's job); two polluters in different halves make neither half fail, and repairing that is `ddmin` |
| A new status (e.g. `POLLUTERS_FOUND`) | M3's `assemble_report` would need a change to accept it; `POLLUTER_FOUND` with a list says the same |
| Report the two polluters only, keep exit 3 for F3 | Leaves the product silent on real multi-polluter cases although an agreed rule can report them honestly |

## Consequences and limitations

- **One run per `ddmin` check.** A flaky check can keep an unneeded test (blaming a bystander).
  Verify ×n exposes a sequence that does not really reproduce (it cannot reach `VERIFIED`), and the
  last round's per-test removal is a single-run counterfactual check. **Repeated** counterfactual
  checks (each polluter removed ×n) are left for the next iteration: they cost n runs per polluter
  and need a report field.
- **Mixed evidence wording** — resolved: M3's `assemble_report` (PR #38) leaves out its generic
  "no edge" line when the fields carry `any_edge_found`, which `combine_fields` sets.
- **`minimise_runs`** is in `DiagnosisRuns` and the execution record, not in the report (no schema
  field); the command's summary shows it when `ddmin` found the polluters, e.g. `minimised:  12
  earlier tests -> 2 polluters in 10 runs (1-minimal, not necessarily the minimum)`.
- **No run budget.** `ddmin`'s worst case is many runs on a long prefix; FR-1's execution budget
  belongs with the planner. Each JVM run keeps its 120 s timeout.
- **1-minimal, not minimum**; other polluter combinations may exist.
- The report still shows one resource; other polluters' resources are in `limitations` until the
  schema allows one edge per polluter.
- Inherits ADR-003/004/005 limits.

## Verification plan

1. `runner/tests/test_minimise.py` (`FakeOrderRunner`): F3's shape (two required polluters in a
   12-test prefix) → exactly `[A, B]` in order; three required polluters; polluters first and last;
   far apart; a single polluter; crash and other-signature runs count as "does not fail"; no subset
   run twice; removing any one result test makes the fake pass; every run keeps relative order.
2. `runner/tests/test_diagnose.py` (`run_steps`): two-polluter fake → `POLLUTER_FOUND`,
   `[A, B]`, `sequence [A, B, V]`, `minimise_runs > 0`; victim first → `NO_SINGLE_POLLUTER`; the
   existing two-polluter test now expects the polluters.
3. `runner/tests/test_cli.py`: the combining function on hand-built pairs in M1's shape (all
   polluters have edges; one has none; one polluter unchanged).
4. Real runs on `fixtures/od-fixture`: `diagnose` F3 → `POLLUTER_FOUND` with exactly the
   ground-truth polluters; the command on F3 (n = 20) → exit 0, `VERIFIED`, polluters A and B,
   resource `odfixture.Toggles#flagA`, a limitation naming `flagB`. F1, F2, N1, N2 unchanged.
5. Each new test seen failing first; mutations (ddmin without the complement step; evidence for the
   first polluter only) must make the F3 tests fail.
6. A fresh reviewer agent reviews the whole branch before the PR.

## Agreement

| Member | Agree? | Comment |
| --- | --- | --- |
| M1 | ☑ | Agreed 2026-10-10: `analyse_pair` once per polluter and the combining rule for several polluters (first edge shown, others named with their depth; any polluter without an edge → no resource fields). Checked on F3 with the real command: `VERIFIED`, `flagA` shown, `flagB` named ([[evidence-m1]]). Note: this section's first line still says `analyse_test` + `find_edges` at depth 2; the code uses `analyse_pair`. M1 will propose the multi-polluter rule for the contract's Projection table |
| M2 | ☑ | Chose ddmin, reusing `POLLUTER_FOUND`, and the strict evidence rule on 2026-10-10 |
| M3 | ☑ | Agree 2026-10-10 — the per-polluter report rule (first polluter's resource shown, others named in `limitations`, `VERIFIED` only if every polluter has an edge) and `POLLUTER_FOUND` with several polluters flowing into `assemble_report` unchanged (`diagnosis.polluters` was already a list) |
