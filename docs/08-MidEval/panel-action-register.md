# Panel action register

**Decision:** Approved with Minor Modifications (proposal defence, F26-214).
**Source:** `DefenseResult.txt` (claude.ai project) — comments copied exactly below.
Supporting plan: *FlakeTrace – Post-Proposal-Defence Improvement and Execution Plan*
(`Mid Eval/FlakeTrace-Defense.pdf`).

> Every row stays here until closed — including the ones still open. The rubric caps progress
> marks if an action is missing from this register or has no evidence link.

Status values: `OPEN` · `IN PROGRESS` · `COMPLETE` · `BLOCKED`

## Exact panel comments

> Approved. Do more research to improve your proposed solution and implement the given
> suggestions. … students need to think more carefully about the proposed solution (e.g., in the
> case of a Flake Trace, how will the system detect it if no logs are available?). In the next
> presentation, students need to answer: 1) Will log trace instructions be injected into the
> code? 2) Will the code be modified? 3) How will the code block be isolated? 4) What are
> diverse scenarios where this approach is applicable?

## Register

| ID | Panel comment | Decision and rationale | Owner | Status | Evidence | Next action and date |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | How will the system detect it if **no logs** are available? | **Accepted.** Detection never depends on application logs. It uses test identities, execution order, pass/fail, exceptions and stack traces from controlled re-execution, plus resource reads/writes from compiled bytecode. Logs are optional evidence. | M2 | COMPLETE | Fixture F1–F3 contain no logging (`fixtures/od-fixture`). `py -m runner diagnose` reaches its verdicts from test order, pass/fail, exceptions and stack traces plus bytecode resource evidence: F1, F2 and F3 `VERIFIED`, N1 `UNRESOLVED(VICTIM_FAILS_ALONE)` (W9 PR #26, W10 PR #35; [[evidence-m2]]). CI on JDK 8 green (runner job, 104 tests on PR #35) | — (shown live in the Mid demo, F1 and F3) |
| A2 | Q1: Will **log/trace instructions be injected** into the code? | **Accepted, answer: no for Iteration 1.** Resource evidence is read from compiled bytecode with `javap`; nothing is injected. Runtime tracing (a Java agent, in memory only, on the already-reduced sequence) is an Iteration 2 option if static evidence proves insufficient. | M1 | COMPLETE | [[03-Design/decisions/ADR-001-iteration1-evidence-without-instrumentation]]; `evidence/extract.py` reads `.class` files with `javap` and writes nothing (PRs #9, #15). F1 and F2 reports are `VERIFIED` with a bytecode-level resource edge and `source_integrity.passed: true` (`eval/reports/f1.json`, `f2.json`). | Demo step 3 shows the `javap` evidence live. Runtime agent only if static evidence proves insufficient (Iteration 2, ADR-001) |
| A3 | Q2: Will the **code be modified**? | **Accepted, answer: no.** The analysed project's source is hashed before and after every diagnosis; a mismatch forces `UNRESOLVED(SOURCE_INTEGRITY_FAILED)`. | M2 | COMPLETE | `runner/integrity.py` hashes every project file (SHA-256, except `target/` and `.git/`) before and after each diagnosis (W7, PR #11); passed in every real fixture run (F1–N2). A changed file forces `UNRESOLVED(SOURCE_INTEGRITY_FAILED)` (`eval/outcome.py`; `eval/tests/test_report.py`). [[evidence-m2]], [[03-Design/decisions/ADR-004-w7-diagnosis-runs]] | — |
| A4 | Q3: How will the **code block be isolated**? | **Accepted.** Two isolations: (1) *sequence isolation* — victim run alone, polluter search, deletion minimisation to a 1-minimal order, repeated runs with a Wilson interval; (2) *cause localisation* — the shared resource with polluter write and victim read locations at method + bytecode-offset level. Statement-level accuracy is not claimed. | M2 (1), M1 (2) | COMPLETE | Schema fields `reduced_sequence`, `polluter_write_location`, `victim_read_location`; statistics in `eval/stats.py` (tested, verified against statsmodels). Part (2) done (M1): `report_fields` gives the shared resource with method + bytecode offset per side, e.g. F2 `FeatureFlags.isTurboEnabled@2` (PRs #15, #34; [[evidence-m1]]) Part (1) done (M2): victim alone ×20, one-by-one polluter search (W7, PR #11), `ddmin` to a 1-minimal polluter set when no single test is enough (W10, ADR-007, PR #35), repeated runs ×20 with a Wilson interval via `decide()`. F3: 12 earlier tests → `setFlagA` + `setFlagB`, 20/20, `VERIFIED` ([[evidence-m2]]) | — |
| A5 | Q4: What **diverse scenarios** is this applicable to? | **Accepted, scoped honestly.** Iteration 1: static-field and system-property pollution, single and multi-polluter (F3), order-needs-reshuffle (F4), and an externally-caused failure correctly reported as not reproduced (N3). Iteration 2: filesystem paths. Out of scope, recognised and reported as `UNRESOLVED` rather than forced: concurrency races, external services, time-dependent and always-failing tests. Negative controls N1/N2/N3 test exactly this. | M3 | **COMPLETE**: all 5 original fixture cases (F1–F3, N1–N2) run end to end through the real pipeline; F4/N3 (ADR-008) added and confirmed by hand, full automated reports pending M2's order-search/alone-check landing | `fixtures/od-fixture/ground_truth.json` (7 cases, each written before any run); scope: [[02-Requirements/scope-boundary]] | None — closed |
| A6 | Do more **research to improve the proposed solution** | **Accepted.** Research targets: runtime vs static evidence trade-off (iDFlakies, iFixFlakies, PolDet/ElectricTest already in `01-Literature/`); delta debugging for multi-polluter minimisation. | M1 | OPEN | `01-Literature/` (pre-defence) | Add one note on minimisation (ddmin vs one-by-one) and update ADR-001 references — date: *fill* |
| A7 | Plan §7: record the **controlled execution environment** for every run | **Accepted.** Each run records commit, test order, JDK, OS/container, seed, timestamps. | M2 | COMPLETE | Every diagnosis writes an execution record (`runner/recording.py`, W7): one JSON line per JVM run (step, test order, outcomes with signatures, start time, duration) and a header with victim, n, JDK, start time, the analysed project's git commit, whether it had uncommitted changes, and the OS (`runner/diagnose.environment()`, PR `m2/panel-actions`). Not applicable, stated rather than faked: container (none yet; Linux container is a committed target, claim E1) and seed (the runner never shuffles). [[evidence-m2]] | — |
| A8 | Plan §9: **reproduction confidence** — repeat, compare with victim alone, report uncertainty | **Accepted.** | M3 | COMPLETE (logic) | `eval/stats.py`, `eval/outcome.py`, 55 passing unit tests in CI | Real counts once runner exists |
| A9 | Plan §10: **evidence report** with victim, polluters, reduced sequence, frequency, resource, locations, signature, confidence, limitations | **Accepted.** | M3 (schema), all (fields) | COMPLETE (schema) | `eval/schema/report.schema.json`, [[contracts/report-schema]] | First real report on F1 |
| A10 | Plan §8 lists databases, ports, threads, caches | **Adapted.** Committed Iteration 1 families stay at static fields and system properties (filesystem in Iteration 2). Wider resources would repeat the over-scoping risk the defence warned about; they are reported as unsupported. | All | COMPLETE (decision) | [[07-Defense/decisions/resource-family-boundaries]], ADR-001 | Confirm with supervisor at Mid |

## Summary for the worksheet

| | |
| --- | --- |
| **Actions completed** | A1 (no logs needed; F1–F3 diagnosed end to end), A2 (no injection), A3 (source hashed before and after), A4 (sequence isolation and cause localisation), A5 (7 diverse fixture cases run end to end), A7 (execution record with commit and OS), A8, A9 (logic and schema), A10 (scope decision) |
| **Actions still open** | A6 (M1: research note on minimisation) |
| **Scope consequence** | Approved scope unchanged; runtime instrumentation explicitly moved to Iteration 2 (ADR-001) |
| **Supervisor-approved exceptions** | None yet — A10 to be confirmed |
