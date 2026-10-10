# ADR-004 — W7: victim-alone check, polluter search, repeated runs, integrity, execution record

**Date:** 2026-10-09 · **Status:** `PROPOSED` — chosen by M2; the default `n = 20` answers open
question I3 in [[contracts/interfaces]] and needs M3's agreement · **Owner:** M2 ·
**Work package:** W7 · **Builds on:** [[03-Design/decisions/ADR-003-order-runner-junitcore-harness]]

## Context

W6 gives one primitive: `OrderRunner.run_ordered(order)` — one fresh JVM, exact order, a
`RunOutcome` per test. W7 turns that into the raw evidence the diagnosis report needs
([[contracts/report-schema]]): the original failing order and its reference failure signature,
how often the victim fails alone, which earlier test pollutes it, how often the polluter→victim
sequence reproduces the failure, whether the analysed source stayed unchanged, and a record of
every run. The verdict itself stays with M3's `eval.outcome.decide()`; W9 assembles the report.

## Decision

Six small modules in `runner/`, one job each:

| Module | Job |
| --- | --- |
| `discovery.py` | List test methods like Surefire: classes from `target/test-classes`, methods from JUnit |
| `recording.py` | `RecordingRunner` — wraps an `OrderRunner`; appends every run to a JSON-lines execution record |
| `integrity.py` | Hash the project's files before and after; report changed/added/removed paths |
| `search.py` | Reproduce the original failure; victim-alone ×n; one-by-one polluter search |
| `verify.py` | Repeat a sequence ×n; count matching and any-signature victim failures |
| `diagnose.py` | `diagnose(...)` — run the steps in order and return one `DiagnosisRuns` |

Rejected: one `diagnosis.py` doing everything (hard to test and defend piece by piece); each step
writing its own log lines instead of a recording wrapper (one forgotten call makes the execution
record silently incomplete).

### Entry point and flow

`diagnose(project_dir, victim, n=20, original_order=None, priority=None, record_dir="flaketrace-records", timeout_s=120)`

Every JVM run goes through `RecordingRunner`, created with `working_dir=project_dir`.

| # | Step | What happens | Early stop → `status` |
| --- | --- | --- | --- |
| 0 | Hash before | `integrity.snapshot(project_dir)` | — |
| 1 | Classpath | `maven_test_classpath(project_dir)` (W6; compiles, writes only `target/`) | — |
| 2 | Original order | `original_order` if given, else `discovery.discover_order(...)`; cut right after the victim | victim absent → `ValueError` |
| 3 | Reproduce | Run the original order up to `n` times, stopping at the first run where the victim fails with a real failure (a `flaketrace.*` crash/timeout/skip is not taken); that failure is the **reference signature** | never fails → `NOT_REPRODUCED` |
| 4 | Victim alone ×n | Count runs where the victim fails with a signature that `matches()` the reference | ≥ 1 → `VICTIM_FAILS_ALONE` |
| 5 | Polluter search | For each test before the victim — in `priority` order if given, else original order — run `[candidate, victim]` once; the first where the victim's signature matches the reference is the polluter | none → `NO_SINGLE_POLLUTER` |
| 6 | Verify ×n | Run `[polluter, victim]` `n` times | — → `POLLUTER_FOUND` |
| 7 | Hash after | Compare with step 0 → `source_integrity` | — |

"Matches" is always `FailureSignature.matches()` from `eval/baseline.py` (exception type +
normalised stack; message ignored). A crashed or timed-out run fails with `flaketrace.JvmCrash` /
`flaketrace.Timeout`, so it counts as a failure of any kind but never as a match.

`priority` is a list of tests to try first, in that order; the remaining candidates follow in
original order. Entries that are not before the victim in the original order are ignored. It is the hook through which W9 can put M1's evidence-backed candidates first
(FR-4's ranked one-by-one policy) without W7 changing.

### Result — `DiagnosisRuns` (plain data, no verdict)

| Field | Meaning |
| --- | --- |
| `status` | `POLLUTER_FOUND` · `VICTIM_FAILS_ALONE` · `NO_SINGLE_POLLUTER` · `NOT_REPRODUCED` |
| `victim`, `original_order` | as run (order ends with the victim) |
| `reference_signature` | victim's failure in the original order; `None` if never reproduced |
| `polluters` | `[polluter]` or `[]` |
| `sequence`, `sequence_n`, `sequence_successes`, `sequence_any_failures` | the sequence that was repeated, and its counts |
| `alone_n`, `alone_successes` | victim-alone counts (matching the reference) |
| `source_integrity` | `passed` + `details` |
| `execution_record` | path of the JSON-lines record |
| `search_runs` | number of polluter-search runs (cost reporting) |

How each status fills the counts (follows M3's examples in `eval/examples/`):

| Status | `sequence` | Counts |
| --- | --- | --- |
| `POLLUTER_FOUND` | `[polluter, victim]` | from step 6 |
| `VICTIM_FAILS_ALONE` | `[victim]` | sequence counts = alone counts; `polluters = []` |
| `NO_SINGLE_POLLUTER` | the full original order (unminimised; W10 minimises) | original order repeated ×n |
| `NOT_REPRODUCED` | the original order | `sequence_n = n` (attempts made), `sequence_successes = 0`, `sequence_any_failures` = attempts where the victim crashed, timed out or was skipped (usually 0 — then `decide()` gives `NOT_REPRODUCED`; if > 0 it gives `SIGNATURE_MISMATCH`, which is the honest reading of a sequence that only ever crashed); the alone check is not run (there is no reference to match), so `alone_n = 0`, `alone_successes = 0` — see Limitations |

### Discovery

1. Classes: every `.class` under `target/test-classes` whose simple name matches Surefire's
   default includes (`Test*`, `*Test`, `*Tests`, `*TestCase`), skipping names containing `$`,
   sorted alphabetically by fully-qualified name.
2. Methods: a new `--list` mode in `FtHarness` asks JUnit for each class's runner description
   (`Request.aClass(cls).getRunner().getDescription().getChildren()`), i.e. the methods in the
   order JUnit would run them. Classes that yield no runnable methods (abstract classes, no
   `@Test`) are dropped.

### Source integrity

SHA-256 of every file under `project_dir` except `target/` and `.git/`, keyed by relative path
(`/`-separated). `passed` ⇔ the before and after maps are equal; `details` lists changed, added
and removed paths (or the file count when unchanged).

### Execution record

JSON lines in `record_dir/<UTC timestamp>-<victim class>#<method>.jsonl`, outside the analysed
project (`flaketrace-records/` is git-ignored). Line 1: header (victim, `n`, project path,
`java -version` output, start time). One line per JVM run, written immediately: step name
(`reproduce` / `alone` / `search` / `verify`), the order, each test's outcome and signature,
duration, timestamp.

### Errors

| Situation | Behaviour |
| --- | --- |
| Victim not in the order; `n < 1`; `record_dir` inside the project (a record there would itself fail the integrity check — found in the final review) | `ValueError` before any JVM runs |
| Project does not compile | Maven's `CalledProcessError` propagates |
| A run crashes or times out | counted as an any-signature failure, never as a match |

## Consequences and limitations

- **Default `n = 20`** (configurable). Wilson 95% lower bounds from `eval.stats.wilson_interval`
  (computed 2026-10-09): 20/20 → 0.839, 19/20 → 0.764 (both ≥ 0.70, `VERIFIED` if an edge
  exists); 10/10 → 0.722, 9/10 → 0.596. Twenty keeps one noisy run from flipping a verdict and
  matches M3's real F1 measurements (20 each way).
- **One-by-one search finds single polluters only.** A case that needs two polluters (fixture F3)
  ends `NO_SINGLE_POLLUTER`; W10's deletion minimiser takes it from there. Cost is at most one
  JVM per earlier test.
- **Discovered order is Surefire's alphabetical order.** Surefire 2.22's default `runOrder` is
  `filesystem` (not deterministic); the fixture sets `alphabetical`. For a project whose CI order
  differs, pass `original_order` explicitly.
- **`NOT_REPRODUCED` stops before the alone check**, so its `alone_n` is 0. `decide()` rejects
  `isolation_n = 0`; W9 must handle this status (e.g. by running the alone check without a
  reference) before calling `decide()`. Recorded here so it is not discovered late.
- **A rarely-failing flaky victim can produce a spurious polluter.** If the victim fails in the
  original order but happens to pass all `n` alone runs, the search may hit a candidate run
  where it fails by chance. The repeated-run counts then expose it (few matches out of `n`), so
  `decide()` gives at most `CANDIDATE` — never `VERIFIED` — but `polluters` is not empty.
  Raising `n` lowers the risk; W10/W9 should treat a low verify rate as a warning.
- Inherits ADR-003's limits (`@BeforeClass` per method; JUnit 4 only).

## Verification plan

1. Unit tests with a `FakeOrderRunner` (under `runner/tests/` only): every status, the counting
   rules, `priority`, early stops, `ValueError`s; discovery filtering and integrity on temp
   folders; record lines written per run.
2. Real runs on `fixtures/od-fixture` against `ground_truth.json`:

| Case | Expected `status` | Key checks |
| --- | --- | --- |
| F1 | `POLLUTER_FOUND` | polluter `ConfigPolluterTest#pollute`; sequence 20/20; alone 0/20; integrity passed |
| F2 | `POLLUTER_FOUND` | polluter `FeaturePolluterTest#enableTurbo` |
| F3 | `NO_SINGLE_POLLUTER` | 12 earlier tests searched |
| N1 | `VICTIM_FAILS_ALONE` | alone 20/20 |
| N2 | `VICTIM_FAILS_ALONE` | alone ≥ 1/20; never blames a polluter (see below) |

N2 fails on `System.nanoTime() % 2`, so its rate depends on the platform's timer. On this
Windows laptop (`Stopwatch.Frequency` = 10 MHz) `nanoTime` was later observed to be a multiple of
100 on every call and N2 failed 0/80 times — although the design spike earlier the same day saw
18/60 failures (cause of that drift not established). On Linux ~50% is expected. The N2 test
therefore checked only that no polluter is ever blamed, and accepted `NOT_REPRODUCED`.

**Update 2026-10-10:** Member 3 replaced the mechanism with `new Random().nextBoolean()` (PR #14),
which fails ~50% on Windows and Linux. The N2 test now expects `VICTIM_FAILS_ALONE` with at least
one alone failure and no polluter (20 runs with no failure has probability ~1e-6).

3. CI: the existing `runner` job picks up the new `runner/tests/test_*.py`; its real duration is
   recorded in [[evidence-m2]].

## Agreement

| Member | Agree? | Comment |
| --- | --- | --- |
| M1 | ☑ | Agree with the `priority` hook for evidence-ranked candidates; the ranking rule must be fixed before any ground truth is used |
| M2 | ☑ | Chose these options on 2026-10-09 |
| M3 | ☑ | Agree 2026-10-10 — default `n = 20` (I3, already used throughout `eval/benchmark/` and the real W9 reports); the `DiagnosisRuns` → `DecisionInput` mapping built in `eval/report.py` (W9) matches this ADR's fields exactly |
