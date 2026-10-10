# runner/ — bounded search and verification (Member 2)

**Owner:** Member 2 · **State:** W6 complete; W7 complete (2026-10-09) — `diagnose()` on all five fixture cases
locally (JDK 21) and in CI (JDK 8, run `37971869749`). W10 `ddmin` finds several polluters (F3, 2026-10-10, ADR-007). W9 command `py -m runner diagnose` built (2026-10-10,
ADR-005); W10 (multi-polluter minimisation) next.

Implements the `OrderRunner` interface in [`eval/baseline.py`](../eval/baseline.py) and
everything built on it. Contract: [docs/contracts/interfaces.md](../docs/contracts/interfaces.md).
Design: [ADR-003](../docs/03-Design/decisions/ADR-003-order-runner-junitcore-harness.md).

## Order runner (W6)

```python
from runner.order_runner import OrderRunner, maven_test_classpath
from eval.baseline import TestIdentifier

runner = OrderRunner(maven_test_classpath("fixtures/od-fixture"), working_dir="fixtures/od-fixture")
results = runner.run_ordered([
    TestIdentifier("odfixture.ConfigPolluterTest", "pollute"),
    TestIdentifier("odfixture.ConfigVictimTest", "expectsDefaultMode"),
])   # {TestIdentifier: RunOutcome(passed, failure_signature)}
```

- `maven_test_classpath(project)` runs `mvn test-compile dependency:build-classpath` on the
  target project and returns `target/test-classes`, `target/classes` and the project's own jars.
  No dependency is added; only the git-ignored `target/` is written.
- `OrderRunner` compiles `harness/FtHarness.java` once into a temp directory. Pass the project
  directory as `working_dir` so tests using relative paths behave as under Maven. Each
  `run_ordered` call starts **one fresh JVM** that runs the tests **in exactly the given order**
  with JUnit's `JUnitCore` + `Request.method`.
- A failed test carries `FailureSignature(exception_type, stack_trace, message)`. `stack_trace`
  is the frames from the throw point down to the test, cut at the first JUnit-runner/reflection/
  harness frame, so an assertion failure gets the same signature on JDK 8 and JDK 21 (a JDK-internal
  frame *above* the cut keeps JDK-specific line numbers — compare signatures within one JDK). `message` is the first line with
  numbers, hex ids, paths and timestamps masked.

### Harness protocol

`java FtHarness <result-file>` with the classpath in `CLASSPATH`; stdin: one `Class#method` per
line. Result file, one line per test (tabs/newlines/backslashes escaped):

```
index<TAB>Class#method<TAB>PASS|FAIL|SKIP<TAB>exceptionClass<TAB>message<TAB>frame|frame|…
```

### Run the tests

Prerequisites: JDK 8+ (`java`, `javac`) and Maven on `PATH`. From the repo root:

```bash
py -m unittest -v runner.tests.test_order_runner        # Windows
python3 -m unittest -v runner.tests.test_order_runner   # Linux / WSL / CI
```

Without `java`/`javac`/`mvn` the real-JVM tests are skipped with a reason, unless
`FLAKETRACE_REQUIRE_JVM` is set (CI), in which case they fail.

### Portability

Processes are launched with argument lists (no shell), so paths with spaces work. The classpath
is joined with the running Python's `os.pathsep` and passed through `CLASSPATH`, avoiding
Windows' command-line length limit. Windows Python + Windows Java (Git Bash, PowerShell) and
Linux Python + Linux Java (WSL, CI) are supported; an MSYS/Cygwin Python driving a Windows JDK is
not.

### Every test is always reported

| Situation | Result for the affected tests |
| --- | --- |
| JVM exceeds `timeout_s` (default 120 s) | FAIL, `flaketrace.Timeout` |
| JVM exits before reporting a test (crash, `System.exit`) | FAIL, `flaketrace.JvmCrash` (exit code in the message) |
| Class or method not found | FAIL with the JVM's/JUnit's exception (`ClassNotFoundException`, `java.lang.Exception: No tests found matching …`) |
| `@Ignore` or failed `Assume` | FAIL, `flaketrace.NotExecuted` — a skip must never count as a pass |
| Same test twice in one order | `ValueError` before any JVM starts |
| Empty order | `{}`, no JVM started |

### Known limitations

- Each method is its own JUnit `Request`: `@BeforeClass`/`@AfterClass` run once per method,
  not once per class as under Maven Surefire.
- JUnit 4, and JUnit 3 `TestCase` classes through JUnit's own JUnit38 adapter (tested with
  `resources/LegacyJUnit3Test.java`). JUnit 5 is not supported.
- Only the top-level exception is part of the signature; a wrapped cause is not compared.

## Diagnosis runs (W7)

Design: [ADR-004](../docs/03-Design/decisions/ADR-004-w7-diagnosis-runs.md). Modules land one by
one; each has its own tests in `runner/tests/`.

| Module | Job | State |
| --- | --- | --- |
| `integrity.py` | `snapshot(project)` hashes every file (SHA-256) except top-level `target/` and `.git/`; `compare(before, after)` → `SourceIntegrity(passed, details)` naming changed/added/removed files | done |
| `recording.py` | `RecordingRunner(runner, path, header)` wraps any runner; set `.step` before a phase; every JVM run is appended as one JSON line (step, order, outcomes with signatures, start, seconds) — line 1 is the header: victim, n, project, `java_version`, `started`, and (panel action A7) `project_commit`, `project_dirty` (uncommitted changes) and `os` from `diagnose.environment()`; commit/dirty are `null` when the project is not in a git repository. Records go to `flaketrace-records/` (git-ignored) | done |
| `discovery.py` | `discover_order(runner, target/test-classes)`: classes matching Surefire's default includes (`Test*`, `*Test`, `*Tests`, `*TestCase`, no `$`), sorted by full name; methods from JUnit via `java FtHarness --list <file>` (stdin: class names; file: `Class#method` lines). Surefire's default `runOrder` is `filesystem` — pass an explicit order for such projects | done |
| `search.py`, `verify.py` | `reproduce` — run the original order until the victim fails; that failure is the reference signature (a `flaketrace.*` crash/timeout/skip never is). `find_polluter` — `[candidate, victim]` once per earlier test, `priority` first; first match wins. `repeat` — n runs → (matching, any-signature) victim failures | done |
| `minimise.py` | `ddmin(runner, prefix, victim, reference)` → 1-minimal subset of the tests before the victim and the runs used; only the reference failure counts, each subset runs at most once (W10, ADR-007) | done |
| `orders.py` | When the starting order never fails for real: up to 31 distinct valid shuffled orders (classes shuffled, then methods within each class; never interleaved), one run each, seeds recorded; the first real failure becomes the failing order (ADR-008) | done |
| `diagnose.py` | `diagnose(project, victim, n=20)` → `DiagnosisRuns` (raw counts, no verdict); `run_steps(runner, order, victim, n)` is the same logic on any runner | done |

```python
from pathlib import Path
from eval.baseline import TestIdentifier
from runner.diagnose import diagnose

runs = diagnose(Path("fixtures/od-fixture"),
                TestIdentifier("odfixture.ConfigVictimTest", "expectsDefaultMode"), n=20)
runs.status, runs.polluters, runs.sequence_successes, runs.alone_successes
runs.source_integrity.passed, runs.execution_record   # flaketrace-records/<time>-<victim>.jsonl
```

| `status` | Meaning | `sequence` that was repeated |
| --- | --- | --- |
| `POLLUTER_FOUND` | one earlier test makes the victim fail with the reference signature — or, when none does alone, `ddmin` found a 1-minimal set of earlier tests that does (F3) | `polluters + [victim]` |
| `VICTIM_FAILS_ALONE` | the victim reproduced its failure with nothing before it — no polluter is blamed | `[victim]` (counts = alone counts) |
| `NO_SINGLE_POLLUTER` | the victim is first in the order, so there is nothing before it to minimise (only with flakiness) | the original order |
| `NOT_REPRODUCED` | the victim never failed for real in `n` runs of the starting order, in up to 31 distinct class-first shuffled orders (ADR-008), or in `n` runs alone; crashes/timeouts are counted in `sequence_any_failures` and `infrastructure_failures` | the starting order |

## Command line (W9)

Design: [ADR-005](../docs/03-Design/decisions/ADR-005-w9-diagnose-cli.md). From the repository root:

```
py -m runner diagnose --project fixtures/od-fixture --victim odfixture.ConfigVictimTest#expectsDefaultMode
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--project` | required | Maven project folder (contains `pom.xml`) |
| `--victim` | required | failing test, `Class#method` |
| `--n` | `20` | repeat count |
| `--records` | `flaketrace-records` | folder for the execution record and the report (outside the project) |
| `--order` | none | file with the real failing order, one `Class#method` per line (`#` comments and blank lines ignored); without it the discovered order is used (ADR-008) |
| `--shuffles` | `31` | distinct class-first shuffled orders to try when the starting order never fails (Gruber et al. [12], a Python study — assumption for JUnit); `0` turns it off |
| `--seed` | `0` | first shuffle seed; every seed tried is in the execution record |

It runs `diagnose()`, Member 1's `find_edges`/`report_fields` at depth 2 when a polluter is found,
and Member 3's `assemble_report()`, then writes `<record>.report.json` next to the record. Real
output on F1 (local, JDK 21):

```
VERIFIED  odfixture.ConfigVictimTest#expectsDefaultMode
  polluter:   odfixture.ConfigPolluterTest#pollute
  resource:   static-field odfixture.Config mode (write odfixture.ConfigPolluterTest#pollute@1 -> read odfixture.ConfigVictimTest#expectsDefaultMode@1)
  reproduced: 20/20 (lower bound 0.839)   alone: 0/20
  report:     flaketrace-records\20261009T213516Z-odfixture.ConfigVictimTest#expectsDefaultMode.report.json
  record:     flaketrace-records\20261009T213516Z-odfixture.ConfigVictimTest#expectsDefaultMode.jsonl
```

| Exit | Meaning |
| --- | --- |
| 0 | report written — any outcome, including `UNRESOLVED` |
| 2 | input wrong (`--victim` not Java `Class#method`, no `pom.xml`, `--n` < 1, records inside the project or a file, unknown victim) |
| 1 | a tool failed (Maven, `java`/`javac`/`mvn`, discovery timeout, the extractor/javap) |
| 3 | no report can be built yet (`NO_SINGLE_POLLUTER` — the victim is first in the order and the failure did not come back). Since ADR-008, `NOT_REPRODUCED` gives a report and exit 0 |

## Planned components, in build order

| # | Component | Produces (report-schema fields) | Needed for Mid demo |
| --- | --- | --- | --- |
| 1 | Ordered single-JVM runner for JUnit 4 — **done (W6)** | per-test outcomes, `failure_signature` | Yes |
| 2 | Victim-alone check, repeated `n` times — **done (W7)** | `victim_alone` raw counts | Yes |
| 3 | Polluter search over preceding tests — **done (W7, single polluters)** | `polluters`, `original_failing_order` | Yes |
| 4 | Deletion minimisation — **done (W10)**: `ddmin`, F3 found (`setFlagA`, `setFlagB`) | `polluters`, `reduced_sequence` | Yes |
| 5 | Repeated-run verification of the reduced sequence — **done (W7)** | `reproduction` raw counts | Yes |
| 6 | Source-integrity check (hash target source before/after) — **done (W7)** | `source_integrity` | Yes |
| 7 | Execution record (JDK, order, timestamps) — **done (W7)** | `execution_record_reference` | Yes |
| 8 | CLI entry point — **done (W9)**: `py -m runner diagnose` | the whole report | Yes |

Test against `fixtures/od-fixture` (F1, F2, F3, N1, N2) — the expected outcomes are in
`fixtures/od-fixture/ground_truth.json`, written before any run.
