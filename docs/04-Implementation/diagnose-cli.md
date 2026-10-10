# Diagnose command — `runner/cli.py` (Member 2, W9)

*Status (2026-10-10): built and run on the fixture locally (JDK 21): F1 and F2 `VERIFIED`, N1
`UNRESOLVED(VICTIM_FAILS_ALONE)`; since W10 (ADR-007) F3 `VERIFIED` with two polluters. CI on JDK 8: see
[[evidence-m2]].
Four-point ownership note per [[04-Implementation/README]]. Design:
[[03-Design/decisions/ADR-005-w9-diagnose-cli]].*

## 1. What it does and why it is there

```
py -m runner diagnose --project fixtures/od-fixture --victim odfixture.ConfigVictimTest#expectsDefaultMode
```

One command from a failing test to a schema-validated report. It joins the three members' parts
in-process and decides nothing itself:

1. checks the options (`--victim` is `Class#method`, `--project` has `pom.xml`);
2. `runner.diagnose.diagnose()` (M2) — every JVM run, recorded;
3. only for `POLLUTER_FOUND`: `evidence.extract` (M1) — `analyse_pair` per polluter (starts at
   depth 2 and deepens on its own when nothing is found, ADR-006), then `report_fields`;
4. `eval.report.assemble_report()` (M3) — `decide()` and schema validation;
5. writes `<record>.report.json` next to the execution record and prints a summary.

| Exit | Meaning |
| --- | --- |
| 0 | report written (any outcome, including `UNRESOLVED`) |
| 2 | input wrong (`--victim` not Java `Class#method`, no `pom.xml`, `--n` < 1, records folder inside the project or a file, victim not a test of the project) |
| 1 | a tool failed (Maven, `java`/`javac`/`mvn` missing, test discovery timed out, the extractor, javap) |
| 3 | diagnosis ran but no report can be built yet (`NO_SINGLE_POLLUTER`, `NOT_REPRODUCED`) |

## 2. Why it is built this way

- **A module, not an installed command** (ADR-005): an installable `flaketrace` command needs the
  packages renamed to `flaketrace.*` (all members' imports) and the Java harness shipped as package
  data; deferred to a later iteration. `main(argv) -> int` is ready for that one-line entry point.
- **In-process calls**, not M1's command line: one Python program, no JSON parsing or exit-code
  mapping between processes; the contract lists both as supported.
- **Catches M3's `UnhandledStatus`** instead of listing supported statuses itself, so when M3
  supports `NOT_REPRODUCED` reports the command produces them unchanged.
- **Minimisation in the summary** (W10): when `ddmin` found the polluters, one line says how many
  earlier tests were shrunk to how many polluters in how many runs, and that the set is 1-minimal,
  not necessarily the minimum. The report has no field for it.
- **Several polluters** (W10): evidence per polluter, combined by `combine_fields`: the first
  polluter's edge is shown, the others named in `limitations`, and only if **every** polluter has an
  edge — otherwise no resource is shown (`UNRESOLVED(NO_SUPPORTED_RESOURCE_EVIDENCE)`).
- **Report next to its record**: each report sits with the raw runs that back it, and the record
  path in it is relative when `--records` is (the default).

## 3. What breaks

- Must run from the repository root, or with it on `PYTHONPATH` (`No module named runner` otherwise).
- On Windows the record path in the report uses `\`; it is relative, but not OS-neutral.
- One victim per run. With several polluters the report shows one resource; the others are only
  named in `limitations` until the schema allows one edge per polluter.
- Unexpected exceptions are deliberately not caught: Python prints the traceback (exit 1).
- Inherits ADR-003/004 limits (JUnit 4, alphabetical discovered order, single polluters).

## 4. How to modify it

- New option: add it in `main()`, pass it through `run_diagnose`, add a fast test in
  `runner/tests/test_cli.py` (`TestInputErrors` style).
- New known error: give it its own exception class (like `DiagnoseInputError`, `ToolError`), catch
  it **only** around the call that raises it, map it to 1 or 2, and add a `TestToolErrors.check(...)`
  test. Never catch a broad `ValueError`/`RuntimeError`: internal bugs would look like user errors.
- Tests: `py -m unittest -v runner.tests.test_cli` — 15 fast tests (no JVM) and 5 real runs on the
  fixture (skipped without JDK/Maven unless `FLAKETRACE_REQUIRE_JVM` is set).

## ADR-008 additions (2026-10-11)

- `--order <file>` (the real failing order), `--shuffles N` (default 31), `--seed S` (default 0). A bad
  `--order` file, a duplicate, a missing victim or a test the project does not have → exit 2.
- When the starting order never fails, the diagnosis tries distinct class-first shuffled orders; the
  summary names the reproducing seed (`orders: reproduced in shuffled order (seed 1) after 2 …`).
- `NOT_REPRODUCED` is now a report (exit 0) with `failure_signature: null`, `order_exploration`, and the
  summary lines `orders:` (which order — "given" only with `--order`, else "discovered") and `bound:`
  (Wilson upper bound, "not proof of reliability").
