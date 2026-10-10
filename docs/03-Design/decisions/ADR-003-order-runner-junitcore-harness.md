# ADR-003 — Order runner: Python `OrderRunner` + small JUnitCore harness

**Date:** 2026-10-09 · **Status:** `PROPOSED` — chosen by M2; needs M1, M3 agreement because it
answers open question I1 in [[contracts/interfaces]] · **Owner:** M2 · **Work package:** W6

## Context

W6 must implement `OrderRunner.run_ordered(order)` from `eval/baseline.py` for JUnit 4. The
contract ([[contracts/interfaces]], Interface 1) requires: all tests in **one JVM, in exactly
the given order**; a **fresh JVM per call**; **every** test in the result (a crash is a
failure); a `FailureSignature` (exception type + normalised stack trace) per failed test; the
target project's source never written to. It must work on Windows (Git Bash), WSL and GitHub
Actions (Ubuntu, JDK 8), without adding dependencies to the analysed project.

## Decision

A Python class `runner.order_runner.OrderRunner` launches a ~60-line Java program,
`runner/harness/FtHarness.java`, once per `run_ordered` call. The harness runs each test with
JUnit's own `JUnitCore.run(Request.method(cls, method))`, one after another, in that one JVM.

### Data flow for one call

```
run_ordered([A#x, B#y])
  │ subprocess.run([java, FtHarness, <result-file>], stdin="A#x\nB#y\n",
  │                env CLASSPATH=<harness dir>, test-classes, classes, jars; timeout)
  ▼
FtHarness (one fresh JVM): for each line → Request.method → JUnitCore.run
  │ appends one line per test to <result-file>, flushed after each test
  ▼
Python parses the file → Dict[TestIdentifier, RunOutcome] (eval.baseline types)
```

### Units

| Unit | Does | Depends on |
| --- | --- | --- |
| `FtHarness.java` | Runs the listed tests in order; writes raw results (status, exception class, message, stack frames) | JUnit 4 from the *target's* classpath |
| `maven_test_classpath(project_dir)` | Returns the target's test classpath: `target/test-classes`, `target/classes`, then the jars from `mvn dependency:build-classpath` | Maven on PATH (found with `shutil.which`, so `mvn.cmd` works on Windows) |
| `OrderRunner(classpath, working_dir=None, timeout_s=120)` | Compiles the harness once into a temp dir (`javac -source 8 -target 8`, accepted by JDK 8 through 21); `run_ordered` launches it in `working_dir` (pass the target project's directory, as Maven would) and builds the result | `java`, `javac`; `eval.baseline` types |
| `normalise_*` / `parse_results` functions | Turn raw harness output into `FailureSignature`s; fill in missing tests | nothing (pure, unit-tested without a JVM) |

### Harness result line

One line per test, tab-separated, tabs/newlines/backslashes escaped:
`index  Class#method  PASS|FAIL|SKIP  exceptionClass  message  frame|frame|…`
(frame = `class.method:line`). Raw frames are sent; normalisation happens in Python so it can
be unit-tested without a JVM. Results go to a file, not stdout, so a test that prints cannot
corrupt them.

### Failure signature

- `exception_type`: fully-qualified class of the thrown exception (top-level, not its cause).
- `stack_trace`: frames from the top **until the first frame of the test framework or
  reflection** (`org.junit.runner.`, `org.junit.runners.`, `org.junit.internal.runners.`, `sun.reflect.`,
  `jdk.internal.reflect.`, `java.lang.reflect.`, the harness), joined with `\n`. Assertion
  frames such as `org.junit.Assert.assertEquals` stay — they sit above the cut. This removes
  the reflection frames that differ between JDK 8 (CI) and JDK 21 (local), so an assertion
  failure gets one signature on both. Limit (found in the final review): JDK-internal frames *above* the cut (e.g. `java.lang.Integer.parseInt` when a test passes bad input) keep their line numbers, which differ between JDKs, so such signatures match only within one JDK. Every run of one diagnosis uses the same JDK, so this does not affect a diagnosis; it does mean signatures from different machines are not always comparable.
- `message`: first line, digits/hex/paths/timestamps masked (same masks as the POC's frozen
  definition). Stored but not compared — `FailureSignature.matches()` ignores it by contract.

### Errors — every test in `order` always appears in the result

| Situation | Reported as |
| --- | --- |
| JVM exceeds `timeout_s` | every test without a result line → FAIL, `flaketrace.Timeout` |
| JVM exits without results for some tests (crash, `System.exit`) | those tests → FAIL, `flaketrace.JvmCrash` (exit code in message) |
| Class or method not found | FAIL with the exception JUnit/the harness reports |
| `@Ignore` or failed `Assume` (harness says SKIP) | FAIL, `flaketrace.NotExecuted` — the contract has no "skipped" state; a skip must not count as a pass |
| `order` contains the same test twice | `ValueError` — the result is a dict keyed by test, so a duplicate cannot be reported |

### Portability

- Every process is launched with an **argument list**, never `shell=True`, so paths with spaces
  (`Semester 7`) are never split.
- Classpath entries are joined with **`os.pathsep`** of the Python that runs the runner:
  `;` for Windows Python + Windows `java` (Git Bash, PowerShell), `:` on WSL and CI. Mixing an
  MSYS/Cygwin Python with Windows Java is unsupported (documented in `runner/README.md`).
- The classpath is passed in the **`CLASSPATH` environment variable** and the test list on
  **stdin**, avoiding Windows' ~32k-character command-line limit (Java 8 has no `@argfiles`).

## Alternatives considered

| Option | Why not |
| --- | --- |
| Maven Surefire, `mvn -Dtest=A#x,B#y test` | Surefire orders by class (`runOrder`) and groups methods within their class — it cannot run an arbitrary method-level order such as `[A#x, B#y, A#z]`, which breaks the contract's first rule. Also Maven start-up on every call and XML report parsing. |
| All-Java runner with a JSON boundary | Evaluation (`eval/baseline.py`, `eval/outcome.py`) is Python; every integration would cross a JSON boundary and a second build. More code to defend, no gain at Mid. |
| JUnit Platform console launcher | Needs the JUnit Vintage engine — a dependency the target project does not have. |

## Consequences and limitations

- **No dependency is added:** the harness uses the JUnit the target already declares; it is
  compiled outside the target's source tree, so source integrity holds.
- **Each method is its own `Request`**, so `@BeforeClass`/`@AfterClass` run once per method,
  not once per class as under Surefire. Irrelevant for the fixture (one method per class);
  a known difference on real projects, revisit in Iteration 2.
- JUnit 4 only; parameterised tests and JUnit 5 are out of scope for Iteration 1.
- Only the top-level exception is signed; a wrapped cause is not compared.

## Verification plan

1. Unit tests (no JVM): normalisation, result-line parsing/escaping, missing-test → crash,
   timeout handling, duplicate rejection.
2. Integration test on fixture F1 (needs `java` + `mvn`; skipped with a stated reason if absent):
   `[ConfigVictimTest#expectsDefaultMode]` → PASS;
   `[ConfigPolluterTest#pollute, ConfigVictimTest#expectsDefaultMode]` → victim FAIL,
   `java.lang.AssertionError`. Then the reverse order → victim PASS (proves order is honoured).
3. CI: a `runner` job in `.github/workflows/ci.yml` (JDK 8, Python 3.11) compiles the fixture
   and runs `runner/tests/test_*.py`; its log must show the integration test **ran**, not skipped.

## Agreement

| Member | Agree? | Comment |
| --- | --- | --- |
| M1 | ☑ | Agree; read and understood the Python runner + JUnitCore harness design |
| M2 | ☑ | Chose option A on 2026-10-09 |
| M3 | ☑ | Agree 2026-10-10 — read and understood the JUnitCore harness design; `eval/`'s report assembly consumes the `DiagnosisRuns` this harness ultimately produces without needing its internals |
