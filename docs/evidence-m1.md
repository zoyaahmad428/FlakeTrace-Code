# Evidence log — Member 1 (Resource Evidence)

Each entry: requirement addressed, file/function, test, command, result,
limitation discovered. Commands were run for real; no number in this file is
invented.

## Phase 1 — Output contract

**Requirement:** agree the resource-evidence output format (per-test accesses
and per-pair edges) before writing extraction code, aligned with Member 3's
report schema.

- File: `docs/contracts/resource-evidence.md` (status: DRAFT, awaiting
  Member 3's confirmation).
- Input evidence: `evidence/javap-dumps/phase1-f1-f2.txt`.
- Command (fixture build, unmodified `fixtures/od-fixture`, image
  `maven@sha256:15522857a08bc468b05f4284d4a5a6c49eff7af7abfe16dc7770609484a67b8b`):
  `mvn -B -q test-compile` → exit 0.
- Command: `javap -c -p -cp classes:test-classes odfixture.ConfigPolluterTest
  odfixture.ConfigVictimTest odfixture.FeaturePolluterTest
  odfixture.FeatureVictimTest odfixture.FeatureFlags odfixture.Config`
  (JDK 1.8.0_502) → exit 0.
- Result (real offsets):
  - F1 write: `ConfigPolluterTest.pollute@1` (`putstatic odfixture/Config.mode`).
  - F1 read: `ConfigVictimTest.expectsDefaultMode@1` (`getstatic`).
  - F2 write: `FeaturePolluterTest.enableTurbo@4` (`System.setProperty`, key from `ldc` at offset 0).
  - F2 read: `FeatureFlags.isTurboEnabled@2` (`System.getProperty`), reached from
    `FeatureVictimTest.expectsTurboDisabled@0`, i.e. depth 2.
- Test: inline Python check that the contract's example JSON parses, every
  offset/call frame resolves to the expected instruction in the saved javap
  output, and the projected fields validate against
  `eval/schema/report.schema.json` `$defs/sharedResource` and
  `$defs/codeLocation`. Result: all passed. An extra key (`depth`) in a
  `codeLocation` is rejected by the schema, as expected (so projection must
  copy only `class`, `method`, `bytecode_offset`).
- Limitations discovered:
  - F2's victim read is only visible at depth ≥ 2. At the default depth 1
    the F2 pair will have no edge.
  - `Config.<clinit>` writes `Config.mode` (offset 1) and runs implicitly. It is
    not reachable by following calls and is reported as `IMPLICIT_CLINIT`.
  - Member 3's report has singular location fields. Multi-edge information is
    lost on projection (open question 1 in the contract).

## Contract revision — consumers and invocation (2026-10-09)

**Requirement:** the contract must name all its consumers (Member 2's CLI calls
the extractor end-to-end) and define how the extractor is invoked, so Member 2
can code against it. Also record the language and entry point in
`docs/contracts/interfaces.md` Interface 2.

- File: `docs/contracts/resource-evidence.md`. Status paragraph corrected (Member
  2 is a consumer, so later changes need all three members). New section
  "Invocation": command, flags, pair and single modes, JSON on stdout, exit
  codes 0/1/2. Status: **planned, not yet implemented**.
- File: `docs/contracts/interfaces.md`, the one line under Interface 2 about
  function name and language, now points to the Invocation section. No other
  line changed.
- Check (inline Python script, run in the scratch checkout): the example JSON
  still parses; its 3 `call_path` frames still resolve to `invokestatic` in
  `evidence/javap-dumps/phase1-f1-f2.txt`; the projected `codeLocation`s
  validate against `eval/schema/report.schema.json`; every in-document link
  anchor (`#invocation`, `#terms`, `#example--fixture-f2-at---depth-2`) exists.
  Result: all passed.
- Command: `git diff --numstat -- docs/contracts/interfaces.md` → `1 1`
  (exactly one line changed).
- Command: `python3 -m unittest` over every `eval/tests/test_*.py` → `Ran 58
  tests ... OK` (docs-only change; run to confirm nothing else broke).
- Not yet run: the extractor itself (no code exists yet).
- Limitations / open items:
  - Default `--depth` decided as **2** (Member 1, 2026-10-09; ADR-002). At
    depth 1, fixture F2 has no edge (its read sits one call below the test
    method).
  - Phase 1 cleanup (`.gitignore` and the removal of 45 junk files) was merged
    separately as PR #4 (`dfcaa88`). Its check: 45 matching files before, `git
    ls-files` count 0 after, status showed 45 deletions plus `.gitignore`.

## Decision record — extractor approach and default depth (2026-10-09)

**Requirement:** record Member 1's two design decisions (fresh Python/javap
extractor, default `--depth 2`) where the team can agree to them.

- Files: `docs/03-Design/decisions/ADR-002-evidence-extractor-implementation.md`
  (new, PROPOSED); `docs/contracts/resource-evidence.md` (default 2 in Terms
  and the Invocation table; numbering note; open question 5 marked resolved).
- Check: `git show origin/main:POC/src/extract_static.py`, lines 29 and 132:
  `HOPS = int(os.environ.get("FT_HOPS", "1"))` and `for _depth in range(HOPS + 1):`.
  The POC explores the root plus HOPS levels of callees, so POC depth N =
  contract depth N + 1. `POC/results/depth_sweep.csv` uses the POC numbering.
- Limitation discovered: POC records disagree on FJ-02. `ranking.csv` gives
  first rank 39 at the frozen scope, but `depth_sweep.csv` gives rank 1 at POC
  depth 1 (W_R). Not resolved here; Phase 5 re-measures with this extractor.
- Open question 5 (F1 offsets) resolved by Member 3 in PR #7 (`af70048`),
  verified independently with `javap -c -p`: offsets 1/1.

## Phase 2 — Depth-1 extraction with lifecycle attribution (2026-10-09)

**Requirement:** given compiled classes and one test method, report its static-field and
constant-key system-property accesses, from the test method **and** its lifecycle code
(JUnit 4 `@Before/@After/@BeforeClass/@AfterClass`, JUnit 3 `setUp/tearDown`, the test
class's `<clinit>`, inherited lifecycle methods), with the lifecycle method each came from.

- Files: `evidence/extract.py` (`parse_class`, `find_roots`, `scan_method`, `scan_call`,
  `constant_key`, `analyse_test`, `main`); `evidence/tests/test_extract.py`; Member 1's own
  test input `evidence/tests/resources/m1-selftest/` (not a project fixture).
- Build (POC-frozen JDK 8 image `maven@sha256:15522857…`):
  `mvn -B -q -f evidence/tests/resources/m1-selftest/pom.xml test-compile` → exit 0.
- Manual cross-check, acceptance case `m1selftest.M1SelfTest#writesAndReads`
  (JDK 8 `javap -c -p`, saved in `evidence/javap-dumps/phase2-m1selftest.txt`):

  | javap -c -p (JDK 1.8.0_502) | extractor output (`--depth 1`, JDK 8 javap) |
  | --- | --- |
  | `1: putstatic … SelfTestState.counter:I` | `WRITE m1selftest.SelfTestState#counter @1 via=TEST_METHOD` |
  | `4: getstatic … SelfTestState.counter:I` | `READ  m1selftest.SelfTestState#counter @4` |
  | `8: ldc "m1.selftest.key"`, `12: invokestatic System.setProperty` | `WRITE sysprop:m1.selftest.key @12` |
  | `16: ldc "m1.selftest.key"`, `18: invokestatic System.getProperty` | `READ  sysprop:m1.selftest.key @18` |

  Exactly these 4 accesses, no unsupported observations.
- Lifecycle (`M1LifecycleSelfTest#emptyBody`, empty test body): CLINIT `<clinit>@4`
  (setProperty), BEFORE_CLASS `beforeAll@1`, BEFORE `M1LifecycleBase.baseBefore@1`
  (inherited), AFTER `after@2` (clearProperty), AFTER_CLASS `afterAll@0`. All offsets match
  the JDK 8 javap dump. JUnit 3 (`M1Junit3SelfTest#testNothing`): SETUP `setUp@1`,
  TEARDOWN `tearDown@2` (`Boolean.getBoolean`).
- Unsupported (`M1UnsupportedSelfTest#tricky`): `SYSPROP_NON_CONSTANT_KEY@23`,
  `REFLECTION@37` (`Field.setInt`), `DEPTH_LIMIT@40` (`helper()` not followed); no accesses
  reported. Offsets match the dump.
- Command: `python3 -m unittest evidence.tests.test_extract -v` → `Ran 9 tests … OK` with
  host javap 21.0.12.1, and `Ran 9 tests … OK` with JDK 8 javap
  (`FLAKETRACE_JAVAP` pointing at the JDK 8 image's javap).
- Fixture sanity run (`--depth 1`, JDK 8 javap, fixture compiled unmodified):
  `ConfigPolluterTest#pollute` WRITE `odfixture.Config#mode @1`; `ConfigVictimTest#expectsDefaultMode`
  READ `@1`; `FeaturePolluterTest#enableTurbo` WRITE `sysprop:odfixture.turbo @4`;
  `FeatureVictimTest#expectsTurboDisabled` no access, `DEPTH_LIMIT @0`
  (`FeatureFlags#isTurboEnabled`). Both F1 tests also get `IMPLICIT_CLINIT` (`Config.<clinit>`).
  This matches the Phase 1 javap evidence. It is not the Phase 5 validation.
- Error found and fixed: on JDK 8 javap, the lifecycle case first returned only the CLINIT
  access. Cause: `RX_CONSTANT` captured javap's padding before the annotation descriptor
  (`'              Lorg/junit/BeforeClass;'`), so no annotation matched. Fix: `\s?` → `\s*`.
  Mutation check: restoring the old regex makes
  `test_junit4_lifecycle_and_inherited_before_are_attributed` fail (1 failure).
- Limitations discovered:
  - Depth 1 only: F2's victim read is invisible until Phase 3.
  - Running without `--depth 1` exits 2 ("not implemented yet") because the contract default is 2.
  - The test class **constructor and instance-field initialisers** run for every JUnit test
    but are not roots in the contract (`via` has no value for them), so they are not analysed.
    This needs a contract decision.
  - The unit tests are not in CI yet: `.github/` is Member 2's area. CI needs a step that
    compiles the self-test project and runs `python3 -m unittest evidence.tests.test_extract`.

## Phase 3 — Configurable call depth (2026-10-09)

**Requirement:** `--depth N` (default 2; 1, 2, 3 supported) follows calls into the
project's own classes only, never the JDK or third-party jars. Handles recursion and
cycles. Records `call_path` for every access. Reports virtual dispatch and reflection as
unsupported. Measures what each depth adds on the fixture.

- Files: `evidence/extract.py` (`walk_root`, `scan_method`, `scan_call`, `follow_call`,
  `may_be_overridden`, `Project.resolve_method`); `evidence/tests/test_extract.py` (class
  `CallDepthTest` and CLI tests); new self-test input `M1DepthSelfTest`, `SelfTestBase`,
  `SelfTestChild` (javap dump: `evidence/javap-dumps/phase3-depth-selftest.txt`);
  `evidence/tools/measure_depth.py`.
- Expected results read by hand from the JDK 8 javap dump, then matched by the extractor (JDK 8 javap):
  - `M1DepthSelfTest#callsDown`: depth 1 none (`DEPTH_LIMIT @callsDown@0`); depth 2 counter
    WRITE `callsDown@0 > level2@2`; depth 3 adds property WRITE
    `callsDown@0 > level2@5 > level3@4`. level4's READ (depth 4) is never reported
    (`DEPTH_LIMIT @level3@8`).
  - `#recursion` (ping/pong cycle): depth 3 gives counter WRITE
    `recursion@1 > ping@7 > pong@1`, and the walk terminates.
  - `#dispatch`: only the named target is followed, so counter WRITE `dispatch@9 > SelfTestBase.work@2`
    plus `VIRTUAL_DISPATCH @dispatch@9`. `SelfTestChild.work`'s `setProperty`, which is what
    really runs, is **not** claimed.
- Command: `python3 -m unittest evidence.tests.test_extract -v` → `Ran 15 tests … OK` with host
  javap 21.0.12.1, and `Ran 15 tests … OK` with JDK 8 javap.
- Command (fixture compiled unmodified, JDK 8 image, `mvn -B -q test-compile` exit 0):
  `python3 -m evidence.tools.measure_depth --classes fixtures/od-fixture/target/classes --test-classes fixtures/od-fixture/target/test-classes --repeats 5`

  13 test methods, every repeat with an empty class cache:

  | depth | accesses | unsupported | javap calls | median s (javap 21.0.12.1, 5 runs) | median s (javap 1.8.0_502 via Docker, 3 runs) |
  | --- | --- | --- | --- | --- | --- |
  | 1 | 7 | 10 (5 IMPLICIT_CLINIT, 5 DEPTH_LIMIT) | 16 | 5.349 (min 5.138, max 5.963) | 10.933 (10.417–11.072) |
  | 2 | 8 | 6 (5 IMPLICIT_CLINIT, 1 DEPTH_LIMIT) | 16 | 5.124 (5.047–5.565) | 10.825 (10.759–11.121) |
  | 3 | 8 | 5 (5 IMPLICIT_CLINIT) | 16 | 5.378 (5.252–5.641) | 10.507 (10.473–10.600) |

  The only access added by depth 2: `FeatureVictimTest#expectsTurboDisabled` READ
  `sysprop:odfixture.turbo` (F2's victim read). Depth 3 adds no access on the fixture.
- Limitations discovered:
  - **On the fixture, depth adds no measurable time.** All depths load the same 16 classes, and the time is
    almost all `javap` JVM start-up (about 0.33 s per call on the host, about 0.68 s per call through Docker).
    The time differences between depths are within run-to-run noise. The fixture is too small
    to show the cost of depth; a real project (Phase 5) is needed for that.
  - One `javap` process per class. That is acceptable here; for large projects, batching classes
    per call would cut start-up cost (not done).
  - Overrides are not followed (only `VIRTUAL_DISPATCH` is recorded). Finding subclasses
    would need every project class loaded.
  - Measurement-tool error (not an extractor bug): the first JDK 8 run failed with "class not
    found" because the Docker javap wrapper runs in a different working directory and
    relative class paths did not resolve. Re-run with absolute paths.

## Phase 4 — Polluter→victim resource edges (2026-10-09)

**Requirement:** given `--polluter` and `--victim`, report every resource the polluter
WRITES (including its lifecycle code) that the victim READS, with both locations. An empty
edge list carries `no_supported_resource_evidence: true` and never means "no dependency".

- Files: `evidence/extract.py` (`find_edges`, `report_fields`, pair mode in `main`);
  `evidence/tests/test_extract.py` (`PairSelfTest`, `FixturePairTest`, CLI pair tests).
- Fixture compiled unmodified (JDK 8 image, `mvn -B -q test-compile` exit 0). Command per pair:
  `python3 -m evidence.extract --classes fixtures/od-fixture/target/classes --test-classes fixtures/od-fixture/target/test-classes --polluter … --victim …`
  (JDK 8 javap, default depth 2):

  | pair | edges | `no_supported_resource_evidence` |
  | --- | --- | --- |
  | F1 `ConfigPolluterTest#pollute` → `ConfigVictimTest#expectsDefaultMode` | `odfixture.Config#mode`: write `pollute@1`, read `expectsDefaultMode@1` | false |
  | F2 `FeaturePolluterTest#enableTurbo` → `FeatureVictimTest#expectsTurboDisabled` | `sysprop:odfixture.turbo`: write `enableTurbo@4`, read `FeatureFlags.isTurboEnabled@2` (depth 2) | false |
  | F2 at `--depth 1` | none (victim side `DEPTH_LIMIT`) | true |
  | F3 `ToggleAPolluterTest#setFlagA` → `ToggleVictimTest#expectsNotBothFlagsSet` | `odfixture.Toggles#flagA`: write `setFlagA@1`, read `@0` | false |
  | F3 `ToggleBPolluterTest#setFlagB` → same victim | `odfixture.Toggles#flagB`: write `setFlagB@1`, read `@6` | false |
  | `MathUtilTest#addsTwoNumbers` → `NegativeAloneFailTest#alwaysFails` | none | true |
  | `ConfigPolluterTest#pollute` → `FeatureVictimTest#expectsTurboDisabled` | none | true |

  The F3 offsets were checked by hand in JDK 8 `javap -c -p` (`putstatic flagA@1`, `putstatic flagB@1`,
  `getstatic flagA@0`, `getstatic flagB@6`). The F1/F2 offsets are the ones in
  `evidence/javap-dumps/phase1-f1-f2.txt`.
- `report_fields` for F2: `shared_resource = {kind: system-property, key: odfixture.turbo}`,
  `victim_read_location = {class: odfixture.FeatureFlags, method: isTurboEnabled, bytecode_offset: 2}`.
  It and the no-edge case (all `null`) validate against `eval/schema/report.schema.json`.
- Command: `python3 -m unittest evidence.tests.test_extract -v` → `Ran 26 tests … OK` with javap
  21.0.12.1 and with JDK 8 javap (Python 3.13). Under Python 3.11: `Ran 26 … OK (skipped=1)`. The
  skipped test is `test_report_fields_fit_member3_schema`, because jsonschema is not installed for
  3.11 here. It ran and passed under 3.13.
- Limitations discovered:
  - F3 needs **both** polluters, but this component is pairwise. It reports one edge per
    polluter (flagA, flagB). Combining them is Member 2's minimisation (W10).
  - The contract's Invocation section and `interfaces.md` still say "planned, not yet
    implemented". That wording was not edited, because contracts change only with all three members.
  - A CI job for these tests must install `eval/requirements.txt` (for jsonschema) and compile both
    the self-test project and the fixture.

## Test guard and in-process default depth (2026-10-09)

**Requirement:** (1) Member 2's CI job must not pass if the evidence tests silently skip. (2) Calling
`analyse_test` in-process without a depth must use the contract default (2), like the CLI.

- Files: `evidence/tests/test_extract.py` (`needs`, `need_javap`, `REQUIRE_JVM`; new test
  `test_in_process_default_depth_is_2`); `evidence/extract.py` (`analyse_test(..., depth=DEFAULT_DEPTH)`,
  previously `depth=1`).
- Commands and real results (fresh checkout of main `eeb5ba1` plus this change):
  - Nothing compiled, no guard: `python3 -m unittest evidence.tests.test_extract` → `Ran 27 tests … OK (skipped=27)`.
  - Nothing compiled, `FLAKETRACE_REQUIRE_JVM=1` → `FAILED (errors=5)`, each error saying which build is missing.
  - After `mvn -B -q test-compile` of the fixture and the self-test project (both exit 0), with
    `FLAKETRACE_REQUIRE_JVM=1` → `Ran 27 tests … OK` with javap 21.0.12.1, and `Ran 27 tests … OK` with JDK 8 javap.
  - Compiled but javap missing (`FLAKETRACE_JAVAP=/no/such/javap`): with the guard → `FAILED (failures=4, errors=4)`;
    without it → `OK (skipped=23)`.
- Limitation discovered: before this fix, `analyse_test(project, test_id)` defaulted to depth 1 in-process
  while the CLI defaulted to 2. An in-process caller leaving out the depth would have missed F2's edge.

## Contract confirmation and ADR agreement (2026-10-09)

**Requirement:** answer Member 2's integration questions. Confirm the resource-evidence contract,
fix which edge goes into the report, define how Member 2 calls the extractor, and record Member 1's
agreement on ADR-001 to ADR-004.

- Files: `docs/contracts/resource-evidence.md` (status: confirmed by M1 and M2, M3 pending; Invocation
  marked implemented, plus "Calling it from another component"; open questions 1 and 3 answered,
  2/4/6 marked open for M3); `docs/contracts/interfaces.md` (Interface 2 line: implemented);
  M1 rows ticked in ADR-001, ADR-002, ADR-003, ADR-004.
- Check (inline Python): every name the contract now lists exists in `evidence/extract.py` on main
  `eeb5ba1` (`Project`, `analyse_test`, `find_edges`, `report_fields`, `ExtractError.exit_code`,
  `FLAKETRACE_JAVAP` in `javap_command`); the example JSON parses; all anchors resolve. Result: passed.
- Limitation: ADR status lines stay `PROPOSED` until Member 3 ticks. The contract is confirmed by all
  three only when Member 3 approves this PR.

## Phase 5 (part 1): fixture validated against ground truth (2026-10-09)

**Requirement:** check the extractor's edges against Member 3's
`fixtures/od-fixture/ground_truth.json` automatically, not by eye. The file is read only and
never edited.

- Files: `evidence/tests/test_extract.py`, new class `GroundTruthTest` with 3 tests.
  - Every fixture test named in the ground truth (the 5 cases plus the 4 noise tests, 13 tests)
    is tried as polluter against every other one as victim, at the default depth (2). That makes
    156 ordered pairs.
  - The set of pairs with an edge must equal the ground-truth polluter→victim pairs exactly.
  - Each edge must be on the ground-truth `shared_resource`.
  - N1 and N2 (no polluters, `shared_resource: null`) must get no edge from any test.
- Exploratory run first (scratch script, all 156 pairs at depths 1, 2 and 3, javap 21.0.12.1).
  Real result:
  - Depth 1: 3 edges. F1 (`Config#mode`), F3-A (`Toggles#flagA`), F3-B (`Toggles#flagB`). F2 has
    none, because its read is one call down.
  - Depths 2 and 3: 4 edges, the three above plus F2 (`sysprop:odfixture.turbo`).
  - No other pair had an edge at any depth. N1, N2 and the four noise tests have no supported
    accesses at all.
- Commands (classes from `mvn -B -q test-compile` of the fixture and the self-test project, host
  JDK 21 compiling to Java 8, both exit 0):
  - `FLAKETRACE_REQUIRE_JVM=1 python3 -m unittest -v evidence.tests.test_extract.GroundTruthTest`
    → `Ran 3 tests in 6.173s … OK` (javap 21.0.12.1).
  - Full suite, same guard → `Ran 30 tests in 38.421s … OK`.
  - With JDK 8 javap (`FLAKETRACE_JAVAP` pointing at the `ft-jdk8` Docker image):
    `GroundTruthTest` + `FixturePairTest` → `Ran 8 tests in 31.881s … OK`.
- Mutation check (scratch script, nothing in the repo changed). Real results:
  - Depth forced to 1: `FAILED (failures=2)`. Both failures name the missing F2 pair.
  - In-memory ground truth altered (F1 field renamed, a fake N1 polluter added):
    `FAILED (failures=2, errors=1)`. The tests caught both.
- Limitations discovered:
  - F3's ground truth gives the field as free text (`"flagA and flagB (both required)"`). The test
    matches kind and class exactly and only checks that the edge's field is one of the words in
    that text. A machine-readable list would be firmer; that is Member 3's file, so it is noted, not
    changed.
  - This shows the extractor agrees with the ground truth on 5 hand-made cases. It does not show
    accuracy on real projects; that is the fastjson step (Phase 5 part 2, not yet run).
  - CI: Member 2's `evidence` job (PR #20) runs the whole `evidence.tests.test_extract` module,
    so `GroundTruthTest` runs there with no CI change. Ran in CI on PR #23 (JDK 8.0.504):
    `Ran 30 tests in 24.716s … OK`, no skips.
  - N1 and N2 being edge-free is expected, since neither touches a supported resource. The
    extractor's "no supported evidence" never means "no dependency".

## Phase 5 (part 2): real fastjson cases FJ-01 and FJ-02 (2026-10-09)

**Requirement:** run the extractor on a real project, not only the hand-made fixture: fastjson
at the POC's pinned commit, case FJ-01 at depths 1 and 2 (and 3), and settle whether FJ-01's
resource is `JSON.defaultTimeZone` or `JSON.defaultLocale`.

**Setup.**
- fastjson `https://github.com/alibaba/fastjson` @ `e05e9c5e4be580691cc55a59f3256595393203a1`,
  from `POC/manifest/cases.csv`. Fetched into a scratch folder outside the repository.
- Built unmodified in the `ft-jdk8` image (openjdk 1.8.0_502): `mvn -B -DskipTests test-compile`
  → `BUILD SUCCESS` in 1 min 12 s (172 main and 2,496 test sources compiled). `git status` in the
  fastjson checkout showed no source changes afterwards. No fastjson test was run.
- Pairs come from the POC's own records, not memory:
  - FJ-01: `POC/results/replay.csv` names `DateFieldFormatTest#test_format_` → `DateTest#test_date`,
    direction BRITTLE (the victim fails alone and passes after this test sets state). So the
    "polluter" here is a state-setter. The edge rule is the same: it writes, the victim reads.
    `DateFieldTest8#test_0` was also run, because the original Phase 5 brief named it.
  - FJ-02: `DateParserTest#test_date_0` → `DefaultExtJSONParser_parseArray#test_7` (BRITTLE).
- javap excerpt for every method on the paths below: `evidence/javap-dumps/phase5-fastjson.txt` (JDK 8 javap).

**Results with the real CLI** (FJ-01, `python3 -m evidence.extract --classes <fj>/target/classes
--test-classes <fj>/target/test-classes --polluter com.alibaba.json.bvt.date.DateFieldFormatTest#test_format_
--victim com.alibaba.json.bvt.date.DateTest#test_date --depth N`, javap 21.0.12.1, one run each):

| `--depth` | exit | edges | `no_supported_resource_evidence` | victim `DEPTH_LIMIT` observations | wall time |
| --- | --- | --- | --- | --- | --- |
| 1 | 0 | none | true | 5 | 2.71 s |
| 2 | 0 | none | true | 3 | 3.33 s |
| 3 | 0 | none | true | 15 | 6.23 s |

- The same through the in-process API gives the same result, for both state-setters, with javap
  21.0.12.1 and with JDK 8 javap 1.8.0_502 (outputs identical apart from timing).
  - javap calls per depth: 7, 8, 12.
  - The writes are found at every depth: `setUp` writes `JSON.defaultTimeZone` and
    `JSON.defaultLocale` (`DateFieldFormatTest.setUp@5` and `@11`, attributed `via SETUP`).
  - The victim's reads of those fields are deeper than 3. So the result is "no supported evidence",
    with `DEPTH_LIMIT` saying where the walk stopped, never "independent".
- FJ-02, same API, depths 1–3, both javaps: no edge at any depth.

**Exploration only — depth cap lifted in memory by a scratch script; the code and the contract
still accept only depths 1–3:**
- FJ-01: the edge appears at **depth 4**, on both fields. The read path is
  `DateTest.test_date@69 > JSON.toJSONStringWithDateFormat@10 > JSON.toJSONString@21 >
  JSONSerializer.<init>@21` (`defaultTimeZone`; `defaultLocale` is `@28`). Every offset matches the
  JDK 8 javap excerpt. 7.5 s.
- FJ-02: no edge at depth 4 (12.9 s). The edge appears at **depth 5** (26.3 s), victim accesses
  75. The read path is `DefaultExtJSONParser_parseArray.test_7@6 > DefaultJSONParser.<init>@8 >
  DefaultJSONParser.<init>@8 > JSONScanner.<init>@2 > JSONLexerBase.<init>@10`
  (`defaultTimeZone`; `defaultLocale` is `@17`). The write is `DateParserTest.setUp@5 via SETUP`.
  At the same depth the walk also reaches the read named in claim C6, by a second path:
  `test_7@28 > DefaultJSONParser.parseArray@3 > DefaultJSONParser.parseArray@464 >
  DefaultJSONParser.parseObject@1280 > TypeUtils.cast@536` (also `TypeUtils.cast@625`).

**defaultTimeZone or defaultLocale?** Static analysis cannot tell. Both state-setters write both
fields in the same `setUp`, and the victims read both. Reasoning from the test's own constants
(no test was run):
- `DateTest` expects `"2011-12-18 00:23:07"` for `1324138987429` ms. Computed: that is
  Asia/Shanghai time (+8); UTC gives `2011-12-17 16:23:07`.
- The pattern `yyyy-MM-dd HH:mm:ss` is all digits, so the locale cannot change it.
- So FJ-01's failure follows `defaultTimeZone`. The POC's `cause_classification.csv` label
  `JSON.defaultLocale` names the other field written in the same `setUp`.
- Not yet confirmed by a run (that would be Member 2's runner).

**Limitations discovered:**
- **Depth 1–3 does not reach either real fastjson case.** FJ-01 needs depth 4 and FJ-02 depth 5.
  The default depth 2 (ADR-002) is enough for the fixture, not for these. Raising the accepted
  range changes the contract (all three members).
- **POC claim C6's location is confirmed, its depth is not.** C6 says FJ-02's victim reads
  `JSON.defaultTimeZone` at `TypeUtils.cast@536`, "two hops down" (POC hops 2 = our depth 3).
  Following calls from the victim, this extractor reaches that same read only at depth 5, four
  calls below the test method (path above). The POC counted reachability differently (ADR-002
  already flagged the numbering). C6 is a joint row, so it is flagged here, not edited.
- Both fields come out as edges. The extractor reports every shared resource and cannot rank
  them; picking the causal one needs the runner.

**Integration check (Member 3's PR #21, merged):** `eval/report.py` now calls `find_edges` +
`report_fields` instead of its own copy, and `run_w9_integration.py` uses `DEFAULT_DEPTH`.
Member 3's recorded `eval/reports/f2.json` (`VERIFIED`) was compared with a live run of this
extractor on the F2 pair: `shared_resource`, `polluter_write_location` (`enableTurbo@4`) and
`victim_read_location` (`FeatureFlags.isTurboEnabled@2`) are identical, and the report carries the
7 fixed limitation lines. The end-to-end run itself is Member 3's ([[evidence-m3]]).

## Depth decision data for ADR-006 (2026-10-10)

**Requirement:** decide whether depth 1–3 is enough, using measurements rather than the two
fastjson pairs alone. The yardstick is the POC's real runs: `od_relevant` in
`POC/results/scan_FJ-01.csv` and `scan_FJ-02.csv`. It is `YES` when running that candidate before
the victim changed the victim's result.

**Exploration only.** A scratch script (`depth_yield.py`) lifts the depth cap in memory. For every
POC candidate it runs `analyse_test` + `find_edges` against the victim and counts the candidates
with at least one edge, split by `od_relevant`. Same fastjson build as Phase 5 part 2, javap
21.0.12.1, one run.

| Case | Depth | Real (`YES`) with edge | Not real (`NO`) with edge | Seconds (all candidates) |
| --- | --- | --- | --- | --- |
| FJ-01 | 1 / 2 / 3 | 0/42 · 0/42 · 0/42 | 0/30 · 0/30 · 0/30 | 22.4 · 25.9 · 30.2 |
| FJ-01 | 4 | **42/42** | 1/30 | 34.8 |
| FJ-01 | 5 | 42/42 | 1/30 | 45.8 |
| FJ-02 | 1 / 2 / 3 | 0/24 · 0/24 · 0/24 | 0/698 · 0/698 · 0/698 | 143.3 · 148.3 · 156.1 |
| FJ-02 | 4 | 1/24 | 0/698 | 163.2 |
| FJ-02 | 5 | **24/24** | 0/698 | 180.7 |

No candidate failed to analyse (errors 0 in every row).

- **The one false edge** (FJ-01, depths 4 and 5) is `DateTest2#test_date`. It writes
  `JSON.defaultTimeZone` at `DateTest2.test_date@5`, but sets America/Chicago (source line 22) and
  restores the old value in `tearDown` (line 18). In the POC's run the victim still failed after
  it. This is the contract limitation "written values are not modelled".
- **Fixture at depths 2–5** (all 156 ordered pairs, same scratch matrix as Phase 5 part 1, main
  `6b5e065`): exactly the 4 ground-truth edges at every depth, nothing else.
- **Limitation:** two cases from one project. The data shows depth 4–5 is needed and cheap in
  false edges here; it does not show the bound 5 is right elsewhere.
- Decision proposed from this: [[03-Design/decisions/ADR-006-evidence-depth-auto-deepen]]. Not
  implemented.

## Phase 6: lifecycle writes as polluter edges, pair-mode input error (2026-10-10)

**Requirement (Phase 6 list):**
- F1 has exactly one edge.
- A write in `setUp` or `<clinit>` is still attributed.
- An access found only at depth 2.
- No shared resource gives an empty edge list plus the flag.
- A nonexistent test or a missing directory gives an error and a non-zero exit.

Already covered before this phase: F1, depth-2-only, the empty list plus flag, the missing
directory and unknown method. `setUp`/`<clinit>` attribution was tested only in single-test
mode, never as the polluter side of a pair edge.

- Files:
  - `evidence/tests/test_extract.py`: `PairSelfTest.test_polluter_write_in_junit3_setup_is_an_edge`,
    `PairSelfTest.test_polluter_write_in_test_class_clinit_is_an_edge`, and
    `CommandLineTest.test_unknown_victim_in_pair_mode_is_an_input_error`.
  - New self-test input `evidence/tests/resources/m1-selftest/src/test/java/m1selftest/M1ClinitReaderSelfTest.java`.
    It reads `m1.selftest.clinit`, which `M1LifecycleSelfTest`'s static initialiser writes. Before
    this, nothing read that property, so a `<clinit>` edge could not occur.
- Expected offsets read by hand from JDK 8 javap (`javap -c -p`, 1.8.0_502):
  - `M1Junit3SelfTest.setUp`: `1: putstatic … SelfTestState.counter`.
  - `M1SelfTest.writesAndReads`: `4: getstatic … SelfTestState.counter`.
  - `M1LifecycleSelfTest.<clinit>`: `4: invokestatic … System.setProperty` (key `m1.selftest.clinit`).
  - `M1ClinitReaderSelfTest.readsClinitProperty`: `2: invokestatic … System.getProperty`.
- FR-3 check: the contract already settles it. A test class's own `<clinit>` is a root
  (`via CLINIT`); another class's `<clinit>` is reported as `IMPLICIT_CLINIT` and never
  attributed to the next test. No design change was needed.
- Commands and real results (`mvn -B -q test-compile` of both projects, exit 0):
  - `FLAKETRACE_REQUIRE_JVM=1 python3 -m unittest -v evidence.tests.test_extract` → `Ran 33 tests … OK`
    (javap 21.0.12.1).
  - Same with JDK 8 javap (`FLAKETRACE_JAVAP` → `ft-jdk8` image) → `Ran 33 tests in 74.368s … OK`.
  - The CLI with an unknown victim class prints `error: test class not found in project classes:
    m1selftest.NoSuchTest` and exits 2.
- Mutation check (scratch script, roots filtered in memory):
  - `SETUP` roots dropped → only the `setUp` test fails.
  - `CLINIT` roots dropped → only the `<clinit>` test fails.
  - Nothing dropped → both pass.
  - The first version of the script filtered the wrong value (`find_roots` returns
    `(chain, roots)`) and so changed nothing. It was fixed before these results.
- Limitation: a test class's `<clinit>` runs once per JVM, on first use, but its writes are
  attributed to every test of that class. Whether it has already run is execution timing, which
  is not modelled (contract limitation 6).

## ADR-006 implemented: depth 1–5 and pair-mode auto-deepening (2026-10-10)

**Requirement:** ADR-006, accepted by all three members (PRs #28, #29, #33). Accept depths 1–5.
Pair mode deepens one level at a time while there is no edge and a walk hit `DEPTH_LIMIT`, and
records `depth_requested`/`depth_used`. Member 2's request: `report_fields` adds a `limitations`
line when the reported evidence is deeper than depth 2.

- **Code** (`evidence/extract.py`):
  - `MAX_DEPTH = 5`.
  - `analyse_pair(project, polluter_id, victim_id, depth=2, deepen=True)` (loop in `_analyse_pair`).
  - The CLI's pair mode uses it, and `--no-deepen` is added.
  - `report_fields` adds the depth line.
  - `analyse_test`/`find_edges` are unchanged, so callers that have not switched keep today's
    behaviour.
- **Contract** (`docs/contracts/resource-evidence.md`): edited exactly as ADR-006's "Proposed
  contract change" says. Depth range 1–5 and deepening in Terms; `--no-deepen`; `depth_requested`
  and `depth_used` in Output 2; `analyse_pair` in "Calling it from another component"; the depth
  line in the projection table.
- **Tests** (`evidence/tests/test_extract.py`, 6 new):
  - `DeepeningTest`: deepens 2 → 4 to the first edge; `deepen=False` stays at 2 with `DEPTH_LIMIT`;
    a pair with nothing cut off does not deepen; the report names evidence deeper than 2.
  - `GroundTruthTest.test_ground_truth_pairs_are_found_without_deepening`: all fixture pairs stay
    at `depth_used` 2 with no depth line.
  - `CommandLineTest.test_pair_mode_deepens_and_no_deepen_stops_it`.
  - Changed: `test_unsupported_depth_is_an_input_error` now uses `--depth 6`.
- **Expected values** read by hand from JDK 8 javap: `M1DepthSelfTest.level4` is
  `0: getstatic … SelfTestState.counter`; `M1SelfTest.writesAndReads` is `1: putstatic …`.
- **Commands and real results** (both projects compiled with `mvn -B -q test-compile`, exit 0):
  - `FLAKETRACE_REQUIRE_JVM=1 python3 -m unittest -v evidence.tests.test_extract` →
    `Ran 39 tests in 51.710s … OK` (javap 21.0.12.1).
  - Same with JDK 8 javap → `Ran 39 tests in 96.183s … OK`.
  - Member 3's tests: `python3 -m unittest discover -s eval/tests` → `Ran 68 tests … OK`.
  - Member 2's CLI tests, which call this extractor end to end:
    `FLAKETRACE_REQUIRE_JVM=1 python3 -m unittest runner.tests.test_cli` → `Ran 20 tests … OK`.
- **Mutation check** (scratch script; extractor source mutated in memory only):
  - Never deepen → the deepening and depth-line tests fail.
  - Ignore the "cut off" condition → only the no-cut-off test fails.
  - Drop the depth line → only the depth-line test fails.
  - The CLI test runs the unmutated file in a subprocess, so it is not affected by design.
- **fastjson through the real CLI**, default settings (start at 2, deepen), same build as Phase 5
  part 2, javap 21, one run each:

  | Case | `depth_requested` | `depth_used` | Edges | Wall time |
  | --- | --- | --- | --- | --- |
  | FJ-01 (`DateFieldFormatTest#test_format_` → `DateTest#test_date`) | 2 | 4 | `JSON#defaultLocale`, `JSON#defaultTimeZone` | 7.73 s |
  | FJ-02 (`DateParserTest#test_date_0` → `DefaultExtJSONParser_parseArray#test_7`) | 2 | 5 | same two | 24.99 s |

  The report fields for FJ-01 are: write `DateFieldFormatTest.setUp@11`, read
  `JSONSerializer.<init>@28`, plus the lines "This evidence is 3 calls deep (depth 4, above the
  default 2)…" and "Another shared resource is not shown in this report:
  com.alibaba.fastjson.JSON#defaultTimeZone".
- **Limitations:**
  - **The report's single resource is not the causal one on FJ-01/FJ-02.** Both fields are equally
    shallow, and the contract's tie-break (`resource_id`) puts `defaultLocale` first. The real
    cause, `defaultTimeZone` (Phase 5 part 2), is named only in `limitations`. Static evidence
    cannot rank causes; this is documented, not changed.
  - FJ-01/FJ-02 are BRITTLE cases, out of scope for Iteration 1 outcomes (contract Q6, Member 3),
    so this changes their evidence, not their outcome.

## ADR-007 check: several polluters on fixture F3 (2026-10-10)

**Requirement:** before agreeing to ADR-007, confirm that the merged W10 code combines this
component's pair evidence as the ADR says, using `analyse_pair` per polluter.

- Code read on main `2a40f58`: `runner/cli.py` `resource_fields` calls `analyse_pair(classes,
  polluter, victim)` once per polluter; `combine_fields` applies the three cases of ADR-007.
- Command (fixture compiled with `mvn -B -q test-compile`, exit 0):
  `python3 -m runner diagnose --project fixtures/od-fixture --victim odfixture.ToggleVictimTest#expectsNotBothFlagsSet --records <scratch>`
  → exit 0 in 26 s. Real output: `VERIFIED`; polluters `setFlagA`, `setFlagB`; "12 earlier
  tests -> 2 polluters in 10 runs"; reproduced 20/20 (lower bound 0.839), alone 0/20.
- Report: `shared_resource` = `odfixture.Toggles` `flagA` (write `ToggleAPolluterTest#setFlagA@1`,
  read `ToggleVictimTest#expectsNotBothFlagsSet@0`), and the `limitations` line "Polluter
  odfixture.ToggleBPolluterTest#setFlagB: shared resource odfixture.Toggles#flagB is not shown in
  this report".
- Limitation: the report shows one resource; `flagB` is only named until the schema allows one
  edge per polluter (ADR-007, long-term shape).
