# Evidence log — Member 3 (Evaluation & Repair)

Each row: requirement addressed, file/function, test, command, result,
limitation discovered. Commands were run for real against the
`maven:3.9-eclipse-temurin-8` container; no numbers in this file are invented.

## Phase 1 — Seeded fixture project

**Requirement:** F1 static-field pollution case exists, victim passes alone,
fails after its polluter.

- File/function: `fixtures/od-fixture/src/main/java/odfixture/Config.java`;
  `ConfigPolluterTest#pollute`, `ConfigVictimTest#expectsDefaultMode`.
- Command: `mvn -B test` (full module, container working dir `/workspace`
  mounted from `fixtures/od-fixture`).
- Result: `ConfigPolluterTest` passed; `ConfigVictimTest` failed —
  `java.lang.AssertionError: expected:<0> but was:<1>` at
  `ConfigVictimTest.java:10`.
- Command: `mvn -q -Dtest=odfixture.ConfigVictimTest#expectsDefaultMode test`.
- Result: passed alone (no error output, exit 0).
- Limitation: none observed; matches `ground_truth.json` F1 exactly.

**Requirement:** F2 system-property pollution case exists, victim passes
alone, fails after its polluter.

- File/function:
  `fixtures/od-fixture/src/main/java/odfixture/FeatureFlags.java`;
  `FeaturePolluterTest#enableTurbo`, `FeatureVictimTest#expectsTurboDisabled`.
- Command: `mvn -B test` (same full-module run as above).
- Result: `FeaturePolluterTest` passed; `FeatureVictimTest` failed —
  `java.lang.AssertionError` at `FeatureVictimTest.java:10`.
- Command: `mvn -q -Dtest=odfixture.FeatureVictimTest#expectsTurboDisabled test`.
- Result: passed alone (no error output, exit 0).
- Limitation: none observed; matches `ground_truth.json` F2 exactly.

**Requirement:** F3 two-polluter edge case — victim fails only when BOTH
polluters have run, order between them should not matter.

- File/function: `fixtures/od-fixture/src/main/java/odfixture/Toggles.java`;
  `ToggleAPolluterTest#setFlagA`, `ToggleBPolluterTest#setFlagB`,
  `ToggleVictimTest#expectsNotBothFlagsSet`.
- Command: `mvn -q -Dtest=odfixture.ToggleAPolluterTest,odfixture.ToggleVictimTest test`.
- Result: passed (single polluter A insufficient, as designed).
- Command: `mvn -q -Dtest=odfixture.ToggleBPolluterTest,odfixture.ToggleVictimTest test`.
- Result: passed (single polluter B insufficient, as designed).
- Command: `mvn -q -Dtest=odfixture.ToggleAPolluterTest,odfixture.ToggleBPolluterTest,odfixture.ToggleVictimTest test`.
- Result: failed — `Tests run: 3, Failures: 1` ,
  `ToggleVictimTest.expectsNotBothFlagsSet:14`. Matches `ground_truth.json` F3
  exactly ("both required").
- Limitation discovered: Maven Surefire's `runOrder` setting
  (`<runOrder>alphabetical</runOrder>` in `pom.xml`) only supports whole-module
  orderings (alphabetical / reverse-alphabetical / random / filesystem /
  hourly / failedfirst / balanced), not an arbitrary explicit permutation that
  runs `ToggleBPolluterTest` before `ToggleAPolluterTest` while still running
  `ToggleVictimTest` last. I could not empirically force the reverse polluter
  order (B then A) through plain Maven alone. The claim that "order between A
  and B does not matter" holds by code inspection — the victim's assertion is
  the symmetric `flagA && flagB` — but empirical confirmation of the reversed
  temporal order is deferred to Member 2's order runner, which accepts an
  explicit ordered list of test methods in one JVM. Recorded here rather than
  faked.

**Requirement:** N1 negative control fails even when run alone.

- File/function:
  `fixtures/od-fixture/src/test/java/odfixture/NegativeAloneFailTest.java`,
  `alwaysFails`.
- Command: `mvn -q -Dtest=odfixture.NegativeAloneFailTest#alwaysFails test`.
- Result: failed alone — `expected:<2> but was:<1>`. Matches
  `ground_truth.json` N1.
- Limitation: none observed.

**Requirement:** N2 negative control fails intermittently regardless of
order (non-order-dependent flakiness).

- File/function:
  `fixtures/od-fixture/src/test/java/odfixture/NegativeFlakyTest.java`,
  `sometimesFails`.
- Command: `mvn -q -Dtest=odfixture.NegativeFlakyTest#sometimesFails test`,
  run 6 times in a row, alone, no polluter present.
- Result: 2 passes / 4 fails out of 6 runs (`System.nanoTime()`-driven,
  genuinely nondeterministic — real counts, not simulated).
- Limitation: 6 runs is a small sample; this only needs to demonstrate that
  the failure is NOT tied to any polluter or ordering, which it does. A larger
  sample would be needed if this fixture were later used to validate the
  random-order baseline's false-positive rate (Phase 4/5), not for Phase 1.

**Requirement:** Benign noise tests touch no shared state.

- File/function: `MathUtilTest`, `StringUtilTest`.
- Command: included in the full `mvn -B test` run above.
- Result: both passed, 0 failures, in every run observed (they do not
  reference `Config`, `FeatureFlags`, or `Toggles`).
- Limitation: none observed.

**Requirement:** `mvn -q test` builds the project inside the JDK 8 container.

- Command: `mvn -B test` inside `maven:3.9-eclipse-temurin-8`
  (image pulled and verified via `docker pull` / `docker info` before use).
- Result: compiled successfully; the reported `BUILD FAILURE` at the end is
  from the five expected test failures (see above), not a compile error —
  `mvn -q -Dtest=...` runs on the same sources passed independently.
- Limitation: none observed.

## Phase 2 — Reproduction-confidence statistics

**Requirement:** `wilson_interval(successes, n, confidence=0.95)` computes a
correct Wilson score confidence interval, dependency-free, and rejects bad
edge inputs with a clear error.

- File/function: `eval/stats.py`, `wilson_interval`, `_norm_ppf`.
- Command: `python3 -m unittest eval.tests.test_stats -v` (14 tests).
- Result: all 14 passed, including explicit edge cases: `n=0` raises
  `ValueError` ("n > 0" in the message), `successes > n` raises,
  `successes < 0` raises, `confidence` outside `(0, 1)` raises; `0/n` gives
  an exact `lower == 0.0`; `n/n` gives an exact `upper == 1.0`.
- Limitation: `_norm_ppf` (Acklam's rational approximation to the inverse
  normal CDF, used to get the z critical value for an arbitrary confidence
  level) has ~1.15e-9 *relative* error per its own published accuracy — for
  z in the 1.6-2.6 range that is up to ~3e-9 *absolute* error. My first
  unit-test tolerance (`places=9`, i.e. <0.5e-9) was tighter than the
  algorithm's real precision and failed on first run; not a bug in
  `wilson_interval` itself, just a mismatched test tolerance. Corrected to
  `places=8` after checking the actual observed differences
  (1.58e-9 to 2.90e-9 across the three published critical values tested).

**Requirement:** verify the numbers against an independent implementation,
not just my own constants.

- File/function: `eval/tools/verify_wilson_oneoff.py` (one-off script, not
  part of the test suite — requires `statsmodels`, which is intentionally
  not a project dependency).
- Command: created a throwaway venv (`/tmp/ft_verify_venv`), `pip install
  statsmodels` (0.15.0), then ran the script comparing
  `wilson_interval(...)` against
  `statsmodels.stats.proportion.proportion_confint(..., method="wilson")`
  for 11 (successes, n, confidence) combinations including both 0/n and n/n
  edges and three confidence levels (0.90, 0.95, 0.99).
- Result: maximum absolute difference across all 11 cases was
  **2.643e-10** — agreement to about 9-10 decimal places. Full per-case
  output recorded below. The venv was deleted after the check; it is not
  committed and is not needed again unless the Wilson formula changes.
- Limitation: none — this was the strongest evidence available
  (statsmodels is a widely-used, independently-maintained statistics
  library) short of a hand-derived closed-form check, which the unit tests
  also do separately (exact 0/n and n/n bounds).

```
successes=17 n=20 confidence=0.95  mine=(0.6395811350648312, 0.9476312541456368)  statsmodels=(0.6395811352592431, 0.9476312541037835)  max_abs_diff=1.944e-10
successes= 0 n=20 confidence=0.95  mine=(0.0, 0.16112515827076002)  statsmodels=(0.0, 0.16112515805281938)  max_abs_diff=2.179e-10
successes=20 n=20 confidence=0.95  mine=(0.83887484172924, 1.0)  statsmodels=(0.8388748419471806, 1.0)  max_abs_diff=2.179e-10
successes=10 n=20 confidence=0.95  mine=(0.2992980080624758, 0.7007019919375241)  statsmodels=(0.2992980081982123, 0.7007019918017877)  max_abs_diff=1.357e-10
successes= 1 n=20 confidence=0.95  mine=(0.008881448790731947, 0.23613119365295204)  statsmodels=(0.008881448800795402, 0.23613119344674205)  max_abs_diff=2.062e-10
successes=19 n=20 confidence=0.95  mine=(0.7638688063470479, 0.9911185512092681)  statsmodels=(0.763868806553258, 0.9911185511992047)  max_abs_diff=2.062e-10
successes=10 n=20 confidence=0.9   mine=(0.32740376805316856, 0.6725962319468314)  statsmodels=(0.3274037678851559, 0.6725962321148441)  max_abs_diff=1.680e-10
successes=10 n=20 confidence=0.99  mine=(0.250447700111171, 0.749552299888829)  statsmodels=(0.25044770032177954, 0.7495522996782205)  max_abs_diff=2.106e-10
successes= 0 n= 1 confidence=0.95  mine=(0.0, 0.7934506858870164)  statsmodels=(0.0, 0.7934506856227626)  max_abs_diff=2.643e-10
successes= 1 n= 1 confidence=0.95  mine=(0.20654931411298352, 1.0)  statsmodels=(0.20654931437723745, 1.0)  max_abs_diff=2.643e-10
successes= 3 n=20 confidence=0.95  mine=(0.052368745854363144, 0.36041886493516884)  statsmodels=(0.052368745896216595, 0.36041886474075696)  max_abs_diff=1.944e-10

Overall max absolute difference across 11 cases: 2.643e-10
```

**Requirement:** a function that compares a sequence result against an
isolation result and returns a structured record.

- File/function: `eval/stats.py`, `compare_sequence_to_isolation`,
  `ReproductionComparison`.
- Command: `python3 -m unittest eval.tests.test_stats -v`
  (`TestCompareSequenceToIsolation`, 3 tests).
- Result: all passed — confirms the `summary` text reads exactly
  `"sequence reproduced 17/20, victim alone 0/20"` for that input, both
  sides carry their own Wilson interval, and `isolation_n=0` /
  `sequence_n=0` each raise a clear `ValueError` (delegated straight from
  `wilson_interval`).
- Limitation: this function only produces the structured comparison; it
  does not decide VERIFIED/CANDIDATE/UNRESOLVED — that decision table is
  Phase 3, and several of its thresholds are explicitly open questions for
  me to confirm before it is finalized.

## Phase 3 — Evidence-report schema and outcome logic

**Requirement:** JSON Schema for the diagnosis report with the specified
fields, and a validator.

- File/function: `eval/schema/report.schema.json`, `eval/schema_validator.py`
  (`validate_report`, `validate_report_file`), using the `jsonschema` package
  (pinned in `eval/requirements.txt`).
- Command: `python3 -m unittest eval.tests.test_schema_validator -v`.
- Result: 8/8 passed, including that the schema document itself is a valid
  JSON Schema (`Draft202012Validator.check_schema`), a valid report passes,
  a missing required field fails, an unknown `outcome` value fails, and the
  `outcome`/`unresolved_reason` conditional is enforced both directions
  (UNRESOLVED without a reason fails; VERIFIED with a reason fails).
- Bug found and fixed during testing: the first draft of the
  `shared_resource` field used `"type": ["object", "null"]` with a sibling
  `"oneOf"` of two object sub-schemas. For a `null` instance, neither
  sub-schema's `properties`/`required` keywords apply (they're no-ops on
  `null`), so **both** branches matched vacuously and `oneOf` correctly
  rejected it for matching more than once. Fixed by restructuring to
  `oneOf: [{"type":"null"}, {"type":"object", "oneOf": [...]}]`, confirmed
  by re-running the two example files that have `shared_resource: null`
  (`example_victim_fails_alone.json`, `example_no_resource_evidence.json`).
- Limitation: `jsonschema` is a new dependency (confirmed with Member 3
  before adding it) — recorded in `eval/requirements.txt`, not yet wired
  into any CI/build step since none exists yet in this repo.

**Requirement:** outcome enum, unresolved-reason enum, and the decision
table — drafted as a starting point, confirmed with Member 3 before
finalizing (per the brief).

- File/function: `eval/outcome.py` (`decide`, `DecisionInput`, `Decision`).
- Four open questions from the brief were put to Member 3 directly before
  any decision code was written (see `docs/contracts/report-schema.md` for
  the resolutions): CANDIDATE vs. `BELOW_CONFIDENCE_THRESHOLD` → CANDIDATE;
  signature-gated success counting → yes; fixed `n=20` vs. generic Wilson
  threshold → generic; source-integrity override → yes, added as a new
  `SOURCE_INTEGRITY_FAILED` reason.
- Command: `python3 -m unittest eval.tests.test_outcome -v` (12 tests: one
  per decision-table row, plus `DecisionInput` validation edge cases).
- Result: 12/12 passed — each of the 7 decision-table rows (source
  integrity failed; victim fails alone; not reproduced; signature mismatch;
  no resource evidence; verified; candidate) produces exactly the outcome
  and reason the table specifies, confirmed with real calls into
  `eval.stats.wilson_interval` (not mocked).
- Limitation: `BELOW_CONFIDENCE_THRESHOLD` stays in the schema's enum (the
  brief requires the five reasons "at least") but `decide()` never emits
  it — documented in both the schema's field description and
  `docs/contracts/report-schema.md` so this isn't mistaken for an omission
  later.

**Requirement:** example JSON files under `examples/`, labelled as
hand-written, not results.

- File/function: `eval/examples/*.json` (7 files, one per decision-table
  row), `eval/examples/README.md`, `eval/tests/test_examples.py`.
- Command: `python3 -m unittest eval.tests.test_examples -v`.
- Result: 4/4 passed — every example file validates against the schema,
  every example's hand-picked counts reproduce the *same* outcome and
  reason when run through `eval.outcome.decide()` (not just asserted by
  hand), and every example's `lower`/`upper` Wilson numbers match the
  formula to 9 decimal places (computed, not typed from guesswork — see
  Phase 2 evidence for the verification of the formula itself).
- Limitation found and documented in the example itself: the schema's
  singular `polluter_write_location` field cannot represent
  `example_f3_candidate.json`'s two required writes (`flagA` and `flagB`
  both set by separate tests); only one is shown, with a note in that
  file's `limitations` array and in `report-schema.md`.

**Requirement:** `docs/contracts/report-schema.md` explaining each field
and which member produces it.

- File/function: `docs/contracts/report-schema.md`.
- Result: field-by-field table with producing member, outcome/reason enum
  tables, the finalized decision table, and an explicit record of the four
  decisions confirmed with Member 3 on 2026-10-08.
- Limitation: none — this is documentation, not executable, so "verification"
  here is that it accurately describes what `eval/outcome.py` and
  `eval/schema/report.schema.json` actually do (checked by re-reading both
  against the table after writing it).

**Correction to Phase 1 ground truth, made in Phase 3 (not based on any run
output):** `fixtures/od-fixture/ground_truth.json`'s N2 case was originally
guessed as `UNRESOLVED(NOT_REPRODUCED)`, flagged at the time as "to be
confirmed against the Phase 3 decision table." Under the finalized table,
any isolation run that reproduces the reference signature at all — even
intermittently — trips `VICTIM_FAILS_ALONE` before reproduction counting is
ever consulted. Phase 1's own evidence (N2 run alone 6 times: 2 pass / 4
fail, same signature each failure) confirms N2 belongs in that category, not
`NOT_REPRODUCED`. Updated the ground truth entry and its notes accordingly;
N1 was already correctly `VICTIM_FAILS_ALONE` and is unchanged.

## Phase 4 — Random-order baseline (interface only)

**Requirement:** design the baseline against an explicit runner interface
(run an ordered list of test methods in one JVM, return per-test outcome +
signature).

- File/function: `eval/baseline.py` — `OrderRunner` (a `typing.Protocol`),
  `TestIdentifier`, `FailureSignature`, `RunOutcome`.
- Result: interface defined; no implementation exists in this repo (Member
  2's component, not built yet). Documented explicitly in
  `eval/README.md` under "Random-order baseline status: NOT YET RUN ON
  REAL TESTS."
- Limitation: none for the interface definition itself — this is
  intentionally interface-only per the brief.

**Requirement:** seeded shuffles of the frozen candidate set; count runs
until the victim's reference failure signature appears; record every seed.

- File/function: `eval/baseline.py` — `run_random_order_baseline`,
  `BaselineAttempt`, `BaselineResult`.
- Command: `python3 -m unittest eval.tests.test_baseline -v`.
- Result: 12/12 passed, including:
  - `test_finds_matching_order_eventually_and_stops_early` — with a fake
    runner where the victim fails iff the polluter is shuffled before it
    (true ~50% of random permutations), found a match within 200 attempts
    and confirmed the runner was called exactly `runs_attempted` times, not
    `max_runs` times (early stopping on first match, real behavior, not
    asserted by inspection).
  - `test_records_every_seed_even_when_never_matching` — 5/5 seeds
    (`[0,1,2,3,4]`) recorded even when none matched.
  - `test_deterministic_given_same_seeds` — two independent runs with the
    same `base_seed` produced byte-identical sequences of shuffled orders
    (real `random.Random(seed).shuffle` determinism, not mocked).
  - `test_different_base_seed_gives_different_orders` — confirms the seed
    actually drives the shuffle (not a no-op parameter).
- Limitation: `random.Random`'s determinism is CPython-internal (Mersenne
  Twister) — reproducible within this project's own environment, not
  intended to match any external/cross-language random source. Acceptable
  for this use (re-running the same seed later in this same toolchain).

**Requirement:** unit-test it with a FakeRunner that lives ONLY in the
tests folder, clearly named as fake; the real CLI must never import it.

- File/function: `eval/tests/fake_runner.py` — `FakeOrderRunner`.
- Command: `grep -rn "fake_runner\|FakeOrderRunner" eval/baseline.py` (and
  every non-test file under `eval/`).
- Result: zero matches outside `eval/tests/` — confirmed `baseline.py` does
  not import the fake, and no other file in `eval/` references it either.
- Limitation: there is no "real CLI" yet anywhere in this repo to check
  against (Member 2 hasn't built one), so this check is necessarily
  limited to "nothing in this repo's non-test code imports the fake" today;
  it will need re-checking once a real CLI exists.

**Requirement:** mark in the README that the baseline is not executed on
real tests until the runner is integrated.

- File/function: `eval/README.md`.
- Result: explicit "NOT YET RUN ON REAL TESTS" section, stating no
  `OrderRunner` implementation exists yet and no baseline numbers against
  `fixtures/od-fixture` or any real project exist or should be invented.

## Phase 5 — Benchmark manifest and yield report

**Requirement:** create/extend the frozen manifest with the fixture cases
(F1-F3, N1-N2) and, if POC case data exists in the repo, the real cases
with pinned SHAs.

- File/function: `eval/benchmark/manifest.json`.
- Command: searched for real-case metadata before assuming none existed —
  `grep -rln "sha\|commit\|repo_url\|github.com" POC` and inspected
  `POC/POC/flaketrace-ui/src/data/recorded.json` directly (real file read,
  not guessed).
- Result: found one — `recorded.json`'s `git` section carries a pinned
  40-character SHA (`ba16cdfde681d0409080f1acbe80942cbae7ae4f`) for a
  "demo-project" case, plus a `suggested` polluter/victim/resource guess
  from the POC's own heuristic backend. Added it to the manifest as
  `POC-DEMO-1` with the pinned SHA, but with `ground_truth_outcome: null`
  — that "suggested" value was the POC backend's own guess, not ground
  truth we independently authored, so copying it in as if verified would
  misrepresent it. Documented in the manifest's `notes` field that this
  case used a custom JDK-21 harness (not Maven/Docker, not our statistical
  pipeline) and that `demo-project`'s source isn't actually present in
  this repo (`recorded.json` points at a `~/demo-project` path local to the
  original author's machine) — so it cannot be attempted by our pipeline
  yet.
- Also checked `POC/POC/sample-dataset/sample` (Holder/ReaderTest/WriterTest,
  found during Phase 0) against the same bar: no pinned SHA, no ground
  truth, 0-byte `pom.xml` (confirmed in Phase 0), JUnit 5 not JUnit 4.
  Excluded from the manifest rather than silently dropped — recorded under
  `excluded_from_manifest` in the manifest file itself, with the reason.
- Cross-check: `python3 -m unittest
  eval.tests.test_yield_report.TestRealManifest.test_real_manifest_matches_fixture_ground_truth`
  — passed, confirming the manifest's F1-F3/N1/N2 entries (victim,
  polluters, `ground_truth_outcome`, `ground_truth_reason`) match
  `fixtures/od-fixture/ground_truth.json` exactly, so the two files can't
  silently drift apart.

**Requirement:** a script that generates a yield report (attempted ->
built -> victim passes alone -> reproduced -> excluded with reason) from
recorded logs, not hand-typed numbers. If no logs exist yet, the report
must show "not yet run" — never invent counts.

- File/function: `eval/benchmark/yield_report.py` —
  `generate_yield_report`, `compute_case_yield`, reading only from
  `eval/benchmark/logs/<case_id>.json`.
- Command: `python3 -m unittest eval.tests.test_yield_report -v` (5 tests:
  2 synthetic-scenario tests using temp manifests/logs, 3 against the real
  manifest/logs).
- Result: 5/5 passed, including a synthetic mixed-funnel scenario (one
  fully-reproduced case, one build-failure, one victim-fails-alone, one
  with no log file at all) that confirmed every funnel count by hand
  computation, and a real check that `eval/benchmark/logs/` currently
  contains zero `.json` files.
- Command (the actual deliverable, not a test): `python3
  eval/benchmark/yield_report.py`.
- Result: real output, reproduced below in full — all 6 cases
  `not_yet_run`, every funnel count 0. This is the literal, current,
  honest state; no number in it was typed by hand.

```json
{
  "total_cases": 6,
  "attempted": 6,
  "not_yet_run": 6,
  "built": 0,
  "build_failed": 0,
  "victim_passes_alone": 0,
  "victim_fails_alone": 0,
  "reproduced": 0,
  "not_reproduced": 0,
  "excluded": 0,
  "cases": [
    {"case_id": "F1", "attempted": true, "not_yet_run": true, "built": null, "victim_passes_alone": null, "reproduced": null, "excluded_reason": null},
    {"case_id": "F2", "attempted": true, "not_yet_run": true, "built": null, "victim_passes_alone": null, "reproduced": null, "excluded_reason": null},
    {"case_id": "F3", "attempted": true, "not_yet_run": true, "built": null, "victim_passes_alone": null, "reproduced": null, "excluded_reason": null},
    {"case_id": "N1", "attempted": true, "not_yet_run": true, "built": null, "victim_passes_alone": null, "reproduced": null, "excluded_reason": null},
    {"case_id": "N2", "attempted": true, "not_yet_run": true, "built": null, "victim_passes_alone": null, "reproduced": null, "excluded_reason": null},
    {"case_id": "POC-DEMO-1", "attempted": true, "not_yet_run": true, "built": null, "victim_passes_alone": null, "reproduced": null, "excluded_reason": null}
  ]
}
```

- Limitation: `eval/benchmark/logs/` is empty because no implementation of
  `baseline.py`'s `OrderRunner` (or any real build/isolation/reproduction
  pipeline) exists in this repo yet — same blocker as Phase 4. Once Member
  2's runner lands and writes real `<case_id>.json` log files, this exact
  script (unchanged) will produce real funnel numbers instead of all
  `not_yet_run`.

## Post-Phase-5 correction — replacing fabricated numbers with real data

The user correctly flagged that Phase 3's `eval/examples/*.json` used
hand-picked counts (e.g. "20/20") never actually measured, and that the
manifest's only "real" case (`POC-DEMO-1`) was one I had already flagged
myself as unusable. Two fixes, both now real:

**Fix 1 — real cases from a real published dataset, not just metadata I
invented.** Searched WSL's `~/WorkSpace/flaketrace/idoft/odr-tests.csv`
(TestingResearchIllinois/idoft, 1908 rows, confirmed via `wc -l` and
`cut -d, -f1 | sort -u | wc -l` → 24 distinct real GitHub projects). Used
Python's `csv.DictReader` (not naive comma-splitting, since some fields
could contain commas) to pull one `OD-test-type=victim` row each from 5
diverse, recognizable projects: dropwizard, kevinsawicki/http-request,
ktuukkan/marine-api, openpojo, spring-boot. Added as
`IDOFT-DROPWIZARD-1`, `IDOFT-HTTP-REQUEST-1`, `IDOFT-MARINE-API-1`,
`IDOFT-OPENPOJO-1`, `IDOFT-SPRING-BOOT-1` in
`eval/benchmark/manifest.json`, each with its real 40-character SHA
transcribed verbatim from the CSV.

- Command: `python3 -m unittest eval.tests.test_yield_report -v` (added
  `test_idoft_cases_have_pinned_shas_and_null_ground_truth`).
- Result: 6/6 passed — confirms all 5 idoft SHAs are real 40-char hex
  strings (regex-checked, not just non-null), confirms 5 distinct real
  project names (no accidental duplicates), and confirms
  `ground_truth_outcome` is `null` for every one of them (we have not run
  these ourselves — idoft's own research classification is not the same
  as our pipeline verifying it, so copying their verdict in as "ground
  truth" would misrepresent it).
- Command: `python3 eval/benchmark/yield_report.py` → real output, now 11
  total cases, all 11 still honestly `not_yet_run` (no build/isolation/
  reproduction pipeline exists yet for any source — fixture, POC, or
  idoft).
- Limitation: these 5 rows are metadata only — not cloned, not built, not
  run. Actually doing so (cloning external GitHub repos at a pinned SHA,
  building with Maven, running the specific tests) was explicitly
  descoped by the user to "metadata only" given the cost/risk of building
  unknown external projects; recorded as a known gap, not silently
  dropped.

**Fix 2 — real measured counts for the fixture, replacing hand-picked
numbers.** Wrote `eval/tools/run_real_reps.sh` and ran it for real inside
`maven:3.9-eclipse-temurin-8` (same container as Phase 1): each of
F1/F2/F3's isolation case and reduced-sequence reproduction, plus N1/N2's
isolation case (their reduced_sequence is empty, so isolation ==
reproduction for them), run 20 times each via `mvn -q -Dtest=... test`,
counting real exit codes. 160 Maven invocations total; took about
30 minutes (JVM/Maven startup overhead per invocation, not 1-2s as first
estimated — confirmed healthy via `docker exec ... ps aux` mid-run, not
assumed).

- Command: `python3 eval/tools/run_real_reps.sh` inside the container (via
  `docker run`, volumes mounting `fixtures/od-fixture` and the script).
- Real result (verbatim):
  ```
  F1_isolation: pass=20 fail=0 n=20
  F1_reproduction: pass=0 fail=20 n=20
  F2_isolation: pass=20 fail=0 n=20
  F2_reproduction: pass=0 fail=20 n=20
  F3_isolation: pass=20 fail=0 n=20
  F3_reproduction: pass=0 fail=20 n=20
  N1_isolation: pass=0 fail=20 n=20
  N2_isolation: pass=8 fail=12 n=20
  ```
  ("pass"/"fail" = whether the `mvn` invocation exited 0; for isolation
  runs a "fail" means the victim failed alone, for reproduction runs a
  "fail" means the victim reproduced the bug after the polluter(s).)
- Interpretation: F1/F2/F3 are genuinely deterministic — 20/20 reproduction,
  0/20 alone-failure, confirmed by actually running each 20 times, not
  assumed from one earlier observation. N1 is genuinely deterministic
  (20/20 fails alone). **N2 gave a real, previously-unmeasured number:
  12/20 fails alone** — Phase 1 had only sampled 6 runs informally (2
  pass/4 fail); this is the first proper n=20 measurement.
- Fed these real counts through `eval.outcome.decide()` (not re-derived by
  hand) to get the authoritative outcome for each case:
  `python3 -c "from eval.outcome import DecisionInput, decide; ..."` →
  F1/F2/F3 → `VERIFIED`; N1/N2 → `UNRESOLVED(VICTIM_FAILS_ALONE)`. All five
  match `fixtures/od-fixture/ground_truth.json`'s hand-authored
  expectations exactly.
- Wrote `eval/benchmark/logs/{F1,F2,F3,N1,N2}.json` with these real
  counts and outcomes (`recorded_by` field states plainly this was a
  manual plain-Maven run, not Member 2's automated pipeline). Running
  `python3 eval/benchmark/yield_report.py` now shows real funnel data for
  these 5 cases (3 `reproduced`, 2 `excluded` as `VICTIM_FAILS_ALONE`)
  while the other 6 cases (`POC-DEMO-1` + 5 `IDOFT-*`) remain honestly
  `not_yet_run`.
- Updated `eval/examples/` to match: `example_f1_verified.json` and the
  renamed `example_f3_verified.json` now carry real counts (F3's are
  genuinely 20/20, not the fabricated 12/20 "CANDIDATE" framing used
  before — F3 is deterministic given its full reduced sequence, so it
  cannot produce a real CANDIDATE example). Added
  `example_victim_fails_alone_intermittent.json` with N2's real 12/20.
  Replaced the deleted F3-as-CANDIDATE file with a wholly synthetic
  `example_candidate.json` (`com.example.*` names), since none of
  F1-F3's real behavior lands below the 0.70 threshold. Updated
  `example_source_integrity_failed.json` to reuse F1's now-real stats
  (only the integrity failure itself stays hypothetical, since no real
  integrity checker exists). `eval/examples/README.md` now labels each
  file REAL/SYNTHETIC/MIXED explicitly.
- Command: `python3 -m unittest discover -s eval/tests -v` (after all
  updates, including a new cross-check
  `test_real_examples_match_the_real_log_files` comparing the 4 real
  example files' counts against the actual log files, and a corrected
  `test_yield_report_shows_real_funnel_for_run_cases_and_not_yet_run_for_the_rest`
  replacing the now-outdated "logs dir is empty" assumption).
- Result: 58/58 passed.
- Limitation: `polluter_write_location`/`victim_read_location`'s
  `bytecode_offset` values and `source_integrity` are still placeholders
  in every example — no real static-bytecode-evidence extractor (Member 1)
  or source-integrity checker (Member 2) exists yet. Only the
  reproduction/isolation statistics themselves are now real.

## 2026-10-09 — `eval/README.md` fix: documented test command

**Requirement:** `eval/README.md` documented `python3 -m unittest discover
-s eval/tests -v` as failing because `eval/tests` has no `__init__.py`.
Reproduce for real before fixing anything.

- Command: `python3 -m unittest discover -s eval/tests -v` — ran in WSL
  (Python 3.10.12): **passed, 58/58, exit 0.** The claimed `__init__.py`
  cause did not reproduce there.
- Command: the same command on native Windows Python (`py`, 3.14.3, no
  venv): **failed** — but with `ModuleNotFoundError: No module named
  'jsonschema'` (import error inside `test_examples.py` and
  `test_schema_validator.py`), not an `__init__.py`/namespace-package
  error.
- Command: `py -m pip install -q -r eval/requirements.txt` then the same
  command again, same native Python: **passed, 58/58, exit 0.**
- To rule out any residual state on that machine masking the real bug:
  created a throwaway venv (`py -m venv .tmp_readme_check_venv`),
  installed only `eval/requirements.txt` into it, ran the documented
  command fresh: **passed, 58/58, exit 0.** Deleted the venv afterward,
  not committed.
- Conclusion: there is no `__init__.py`/namespace-package bug. The actual,
  reproducible cause is that `eval/README.md` mentioned
  `pip install -r eval/requirements.txt` once, at the top, separately
  from the "Run everything" command — easy to skip if a reader jumps
  straight to the command.
- Fix (smallest correct one): moved the `pip install` line to sit directly
  above the run command, with an explicit note of the exact
  `ModuleNotFoundError` a reader will hit if they skip it. No code change,
  no `__init__.py` added (none needed — the namespace-package import
  already works, confirmed above).
- Re-verified after the fix, fresh:
  - Documented command: `pip install -q -r eval/requirements.txt &&
    python3 -m unittest discover -s eval/tests -v` → **58/58, exit 0.**
  - CI's actual command (`.github/workflows/ci.yml`, `python-eval` job):
    `modules=$(ls eval/tests/test_*.py | sed 's#/#.#g; s#\.py$##'); python3
    -m unittest -v $modules` → **58/58, exit 0.** `python3
    eval/benchmark/yield_report.py` → exit 0.
- Limitation: none found beyond the one fixed. The brief's premise
  (`__init__.py` missing) turned out to be a misdiagnosis of a plain
  missing-dependency error; worth saying so plainly rather than adding an
  `__init__.py` that was never the cause.

## 2026-10-09 — Fix F1 example's illustrative bytecode offsets

**Requirement:** Zoya's `docs/contracts/resource-evidence.md` (open question
5, on branch `m1/resource-evidence-contract`) noted that
`example_f1_verified.json` used illustrative offsets 3/5, while real JDK 8
offsets are 1/1. Verify independently before trusting her claim and acting
on it.

- Command: `docker run ... maven:3.9-eclipse-temurin-8 bash -c "mvn -q
  test-compile && javap -c -p target/test-classes/odfixture/
  ConfigPolluterTest.class && javap -c -p target/test-classes/odfixture/
  ConfigVictimTest.class"`.
- Result: `putstatic #2 // Field odfixture/Config.mode:I` at **offset 1**
  in `ConfigPolluterTest#pollute`; `getstatic #2 // Field
  odfixture/Config.mode:I` at **offset 1** in
  `ConfigVictimTest#expectsDefaultMode`. Matches Zoya's claimed values
  (1/1) exactly — independently confirmed, not just trusted.
- File/function: `eval/examples/example_f1_verified.json` —
  `polluter_write_location.bytecode_offset` and
  `victim_read_location.bytecode_offset` changed from the placeholder
  3/5 to the real 1/1; `limitations` entry updated to say these are now
  real, verified values, not placeholders.
- Command: `python3 -m unittest discover -s eval/tests -v`.
- Result: 58/58 passed — no test asserts an exact offset value, so this
  change could not have silently broken anything; confirmed anyway rather
  than assumed.
- Limitation: none — this was purely my own example file, no contract
  change, no other member's sign-off needed.

## 2026-10-10 — W9: real end-to-end report assembly

**Requirement:** Interface 3 of `docs/contracts/interfaces.md` ("report assembly, M3") —
turn Member 2's raw diagnosis counts and Member 1's resource-access data into one
schema-validated report, now that both exist for real (PR #10 `runner/order_runner.py`,
PR #11 `runner/diagnose.py`, PR #9 `evidence/extract.py`).

- Before writing any glue code: smoke-tested both real components on this machine (native
  Windows, JDK 24.0.2, Maven 3.9.11 — not the Docker/JDK8 setup used in earlier phases).
  `runner.diagnose.diagnose()` on F1 (`n=5`): real `POLLUTER_FOUND`, correct polluter found,
  matches the shape expected. Cross-checked against my own independent manual measurement
  from two sessions ago (Docker/plain-Maven, `eval/tools/run_real_reps.sh`): F1 and N1 both
  agree exactly (F1: 20/20 reproduced, 0/20 alone; N1: 20/20 alone) — two independently-run
  real measurements agreeing is stronger evidence than either alone.
- File/function: `eval/report.py` — `find_resource_edge` (correlates two
  `evidence.extract.analyse_test` Output-1 results into one edge, per the contract's
  documented `edges[0]` ordering) and `assemble_report` (builds a full report from a
  `DiagnosisRuns` + optional edge, runs it through `eval.outcome.decide` and
  `eval.schema_validator.validate_report`).
- Deliberate scope limit, not silently worked around: `assemble_report` only handles
  `DiagnosisRuns.status` values `POLLUTER_FOUND` and `VICTIM_FAILS_ALONE`, raising
  `UnhandledStatus` otherwise. Two real reasons, found by reading `runner/diagnose.py`
  carefully, not assumed:
  1. `NOT_REPRODUCED` carries `alone_n=0` (M2's code never runs the isolation check if the
     sequence never reproduces at all) — but `eval.outcome.DecisionInput` requires
     `isolation_n > 0`. Feeding it a fabricated `isolation_n=1` just to satisfy the signature
     would be inventing data; raising instead.
  2. `NO_SINGLE_POLLUTER` (M2's one-by-one search finding no single attributable test — F3's
     real status, confirmed below) has no corresponding value in `report.schema.json`'s
     `unresolved_reason` enum. Mapping it onto an existing reason (e.g.
     `NO_SUPPORTED_RESOURCE_EVIDENCE`) would be semantically wrong — that reason means
     missing *resource* evidence, not a missing *polluter identity*. A new enum value is a
     contract change needing all three members, not decided here.
- Command: `py -m unittest eval.tests.test_report -v` (pure-logic tests against literal
  Output-1 dicts and hand-built `DiagnosisRuns` objects — not calling real Maven/JDK, so this
  runs in the existing `python-eval` CI job unchanged).
- Result: 11/11 passed, including: resource-edge correlation finds the right resource and
  picks the lowest-combined-depth edge when more than one is shared; `VERIFIED` for a strong
  reproduction with an edge; `NO_SUPPORTED_RESOURCE_EVIDENCE` with no edge; `CANDIDATE` for a
  weak reproduction; `SOURCE_INTEGRITY_FAILED` overriding a strong case; `VICTIM_FAILS_ALONE`
  correctly ignoring a resource edge even if one is mistakenly passed in; both unhandled
  statuses correctly raising `UnhandledStatus`.
- Command: `py -m unittest discover -s eval/tests -v` (full suite).
- Result: 69/69 passed (58 existing + 11 new).
- **Real end-to-end integration** (`eval/tools/run_w9_integration.py`, not part of the unit
  suite — shells out to real Maven/JDK, a few minutes):
  - F1: `runner.diagnose.diagnose()` for real (`n=20`) → `POLLUTER_FOUND`, 20/20 reproduced,
    0/20 alone, source integrity passed. `evidence.extract.analyse_test()` for real on the
    polluter and victim → real edge, `odfixture.Config#mode`, write/read both at bytecode
    offset 1 (matches the independently-`javap`-verified value from the earlier session).
    `assemble_report` → **`VERIFIED`**, `validate_report` passed. Saved:
    `eval/reports/f1.json`.
  - N1: real `diagnose()` (`n=20`) → `VICTIM_FAILS_ALONE`, 20/20 alone-failures.
    `assemble_report` (no resource edge) → **`UNRESOLVED(VICTIM_FAILS_ALONE)`**,
    `validate_report` passed. Saved: `eval/reports/n1.json`.
  - Both match `fixtures/od-fixture/ground_truth.json` exactly.
- Limitation found and documented, not fixed here (not my folder): `execution_record_reference`
  in both reports is an absolute, machine-specific path, because
  `runner.diagnose.diagnose()` calls `Path(record_dir).resolve()` internally. The committed
  JSON reflects exactly what the real run produced, not cleaned up for presentation.
- Limitation: the raw per-run JSONL execution records
  (`eval/reports/flaketrace-records/*.jsonl`) that back `execution_record_reference` are
  **not committed** — `.gitignore` already excludes `flaketrace-records/` (Member 2's
  existing convention). Only the final assembled reports are committed; the records
  regenerate locally by re-running the integration script.
- Also confirmed empirically, while exploring: on this machine, `diagnose()` reports N2 as
  `NOT_REPRODUCED` (never fails at all, in or out of order), not `VICTIM_FAILS_ALONE` as my
  own earlier Docker measurement found (12/20 alone-failures) or as `ground_truth.json`
  currently assumes. Traced by Member 2 to `System.nanoTime()` having coarser resolution on
  some Windows/JVM combinations (always a multiple of 100ns, always even, so the parity check
  in `NegativeFlakyTest` can never fail there) — see `docs/evidence-m2.md`. This is a genuine,
  environment-dependent behaviour of the fixture, not a bug in either component; it meant
  `ground_truth.json`'s N2 entry was not safely portable across machines as originally
  written. Resolved the same day — see the next section.

## 2026-10-10 — Fix N2's flakiness mechanism (ground truth resolution)

**Requirement:** resolve a real discrepancy found while reviewing Member 2's W9 evidence:
`runner.diagnose()` reported N2 (`NegativeFlakyTest#sometimesFails`) as `NOT_REPRODUCED` on a
Windows/JDK 21 machine (0/40 failures, alone and in the full order), contradicting
`ground_truth.json`'s assumption that it fails at least intermittently
(`docs/evidence-m2.md`). My own earlier measurement (Docker/JDK 8) found 12/20 alone-failures.

- Investigation: `NegativeFlakyTest` used `System.nanoTime() % 2L == 0L`. This inspects only
  the **lowest bit** of the timer value. Some JVM/OS/hardware timer combinations have coarse
  resolution (Member 2 found `System.nanoTime() % 1000` always a multiple of 100 on their
  machine), so every value is even and the assertion is always true — the test can become
  **fully deterministic** (never fails) on specific real hardware, which directly contradicts
  its purpose ("non-order-dependent flakiness... unrelated to the environment").
- Decision: fix the mechanism, not just document the quirk. This is entirely my own file
  (`fixtures/od-fixture`), no contract or cross-member sign-off needed, and a genuine fix is
  stronger than a documented limitation for a case whose entire point is demonstrating
  environment-independent flaky behaviour.
- File/function: `fixtures/od-fixture/src/test/java/odfixture/NegativeFlakyTest.java` —
  replaced the nanoTime-parity check with `new java.util.Random().nextBoolean()`, which mixes
  nanoTime() with a per-call atomic counter through a full LCG rather than exposing one raw
  timer bit.
- Command: `mvn -q -Dtest=odfixture.NegativeFlakyTest#sometimesFails test`, run 20 times in a
  loop, **on native Windows (JDK 24.0.2, where the old mechanism gave 0/40)**.
- Result: **11/20 failures (45%)** — genuinely balanced, real data.
- Command: the same 20-repetition loop, independently, **inside
  `maven:3.9-eclipse-temurin-8` (JDK 8, Linux, Docker)**, run in parallel with the Windows
  check.
- Result: **10/20 failures (50%)** — also genuinely balanced.
- Command: full fixture module, `mvn -B test` (native Windows).
- Result: `Tests run: 13, Failures: 5` — F1, F2, F3, N1 fail exactly as designed (alphabetical
  declared order pollution); N2 failed this particular run (one of its genuine ~50/50
  outcomes, not every run will match) — matches Phase 1's original full-module result exactly,
  confirming the fix did not disturb anything else in the fixture.
- File/function: `fixtures/od-fixture/ground_truth.json` — N2's `expected_outcome_notes`
  rewritten to describe the bug, the fix, and both real verification numbers above, dropping
  the old "~50%, confirmed in Phase 1: 2 pass / 4 fail across 6 isolated runs" claim (that
  6-run sample is superseded by this 20-run, two-platform verification). Also added a short
  confirming note to F3's entry: Member 2's real `diagnose()` run returned
  `NO_SINGLE_POLLUTER` after 12 search runs, exactly as the fixture's design predicted (the
  current one-by-one search cannot find a two-polluter case) — not evidence against F3's
  `VERIFIED` ground truth, evidence that W10 (multi-polluter search) is still needed.
- Limitation: could not literally re-test on Member 2's exact original machine (not available
  to me); the fix's correctness rests on the reasoning that an LCG-mixed seed does not inherit
  a single-bit fragility, backed by two independent real measurements (different OS, different
  JDK major version) both landing close to 50%, not by reproducing the exact prior
  environment.

## 2026-10-10 — Random-order baseline run for real for the first time

**Requirement:** W4's baseline (`eval/baseline.py`) has been interface-only since Phase 4;
Member 2 confirmed the real `OrderRunner` is ready to use.

- File/function: `eval.baseline.run_random_order_baseline`, against the real
  `runner.order_runner.OrderRunner` (not `eval/tests/fake_runner.py`).
- Command: real F1 case, candidate pool of 7 tests (victim + its polluter + 5 noise tests),
  `max_runs=50`, 4 independent trials with `base_seed` 0, 100, 200, 300.
- Result: found the bug in **1, 1, 3, and 2** random shuffles respectively (average 1.75).
  Every matching attempt's order placed `ConfigPolluterTest#pollute` before
  `ConfigVictimTest#expectsDefaultMode`, as expected.
- Comparison: Member 2's real targeted one-by-one search found the same polluter in 1 search
  run (`docs/evidence-m2.md`, F1 row). Both are cheap on this 7-test fixture by design — the
  baseline comparison's real value will show on a larger real-world project, not this one.
- File/function: `eval/README.md` — corrected the baseline status section, which still said
  "No implementation of `OrderRunner` exists in this repo yet" (stale since PR #10).
- Limitation: only F1 run so far; F2/F3/N1/N2 and any idoft case remain.

## 2026-10-10 — Fix two real bugs Member 2 found in the merged W9 work (PR #13)

**Requirement:** Member 2 reviewed the merged W9 work and flagged two concrete problems.
Verified both against the actual code before acting, not taken on trust.

**Problem 1 — wrong explanation of the absolute execution-record path.**
`eval/reports/README.md`'s "Known limitation" section claimed
`runner.diagnose.diagnose()` calls `Path(record_dir).resolve()` internally, making the path
absolute. Read `runner/diagnose.py` to check:
- `runner/diagnose.py:93` does call `Path(record_dir).resolve()`, but only to build `records`,
  used solely for the record-vs-project containment safety check (line 94-96).
- `runner/diagnose.py:103` builds the actual record path from `Path(record_dir)` — the
  argument exactly as given, not `records`. `diagnose()` never resolves the path it returns.
- The real cause: `eval/tools/run_w9_integration.py:27`'s own `RECORD_DIR = REPO_ROOT / "eval"
  / "reports" / "flaketrace-records"`, where `REPO_ROOT = Path(__file__).resolve().parents[2]`
  — already absolute before it reaches `diagnose()`.
- Fix: corrected `eval/reports/README.md`'s "Known limitation" section to attribute the
  absolute path to the script's own `RECORD_DIR`, with the two line numbers above, and noted
  the correction was made after Member 2 pointed it out.

**Problem 2 — duplicated resource-correlation logic, called at the wrong depth.**
Member 2 pointed out that `eval/report.py` had its own `find_resource_edge` instead of using
Member 1's real `evidence.extract.find_edges`/`report_fields` (landed in `m1/resource-edges`
after W9's first version), that this duplicate dropped M1's `FIXED_LIMITATIONS`, and that
`eval/tools/run_w9_integration.py` called `analyse_test(..., depth=1)`, which can never find
F2's edge.
- Verified by reading `fixtures/od-fixture/src/test/java/odfixture/FeatureVictimTest.java`:
  its victim calls `FeatureFlags.isTurboEnabled()` — the actual `System.getProperty` read is
  one call-level inside that helper, not in the test method itself. `evidence/extract.py`'s
  `follow_call`/`walk_root` only follow calls when `len(path) + 1 < max_depth`; at `depth=1`
  that is `0+1 >= 1`, so the call is never followed and the read is never seen. The contract's
  own `DEFAULT_DEPTH` is 2 (`evidence/extract.py:29`).
- Confirmed with a direct one-off check (`evidence.extract.find_edges`/`report_fields` called
  on F2's real polluter/victim at `depth=1` vs `depth=2`, against the already-compiled fixture
  classes): `depth=1` → `shared_resource: None`; `depth=2` → `shared_resource:
  {"kind": "system-property", "key": "odfixture.turbo"}`. Reproduces the bug and confirms the
  fix, independently of any full diagnose() run.
- Fix: `eval/report.py`'s `assemble_report` now takes `resource_fields` — exactly the dict
  `evidence.extract.report_fields(pair)` returns — instead of building its own edge; deleted
  `find_resource_edge` entirely (no longer used anywhere). `eval/tools/run_w9_integration.py`
  now calls `evidence.extract.find_edges`/`report_fields` at `DEFAULT_DEPTH` (2), for F1 and
  the newly-added F2. `eval/tests/test_report.py` rewritten to build its `resource_fields`
  fixtures by calling M1's real `find_edges`/`report_fields` (not a fake, not a re-derived
  local function).
- Command: `py -m unittest discover -s eval/tests -v` (full suite, after the rewrite).
- Result: 68/68 passed.
- Command: `py eval/tools/run_w9_integration.py` (real Maven/JDK run, native Windows JDK 24).
- Result: **F1 → `VERIFIED`** (unchanged — its access is at the root, depth-independent).
  **F2 → `VERIFIED`** for the first time — real edge `system-property:odfixture.turbo`,
  `victim_read_location` correctly reported as `odfixture.FeatureFlags#isTurboEnabled` (not
  the test method), proving the helper call was genuinely followed, not special-cased.
  **N1 → `UNRESOLVED(VICTIM_FAILS_ALONE)`** (unchanged). Saved: `eval/reports/{f1,f2,n1}.json`.
- Updated `eval/reports/README.md`'s "What's NOT here yet" section: removed the wrong claim
  that F2 "needs resource-evidence depth 2, not implemented by Member 1 yet" (depth 2 was
  already implemented; the bug was this script hardcoding `depth=1`), added F2 to the results
  table, and updated `docs/08-MidEval/iteration-plan.md`'s W9 row accordingly.
- Limitation: F3 (needs W10's multi-polluter search) and N2 (`NOT_REPRODUCED`, still an
  unhandled `DiagnosisRuns.status`) remain exactly as before — this fix did not touch either.
- Still open, not actioned here: Member 2 also asked me to review/approve contract PR #17
  (`m1/confirm-contract`, already merged) after the fact — a GitHub review action I cannot
  perform myself (no `gh` CLI, no write-scoped API token in this environment); flagged to the
  member to do directly. (Checked at the time: already approved by both M3 and M2 on
  2026-10-09, before PR #17 merged — nothing to do.)

## 2026-10-10 — W9: add N2, now that its mechanism fix is confirmed cross-platform

**Requirement:** a full read-through of `docs/` found that N2 (`NegativeFlakyTest`) was the
only remaining fixture case blocked by a real interface gap rather than by missing
functionality. Confirmed before acting: `docs/evidence-m2.md`'s 2026-10-10 entry records
Member 2 running `diagnose()` on N2 three times for real (native Windows, JDK 21.0.9) after
the `Random.nextBoolean()` mechanism fix landed, getting `VICTIM_FAILS_ALONE` every time
(16/20, 9/20, 11/20 alone-failures) — not the `NOT_REPRODUCED` it used to give on some
machines. `eval/report.py`'s `assemble_report` already handles `VICTIM_FAILS_ALONE` (it was
only `NOT_REPRODUCED` and `NO_SINGLE_POLLUTER` that were real gaps), so landing N2 needed no
new production code, only adding the case to the integration script.

- File/function: `eval/tools/run_w9_integration.py` — added `run_n2()`, identical in shape to
  `run_n1()` (no resource edge: `assemble_report(diagnosis)` with `resource_fields` omitted).
- Command: `py -m unittest discover -s eval/tests -v` (unaffected by this change — pure-logic
  tests don't call the integration script).
- Result: 68/68 passed.
- Command: `py eval/tools/run_w9_integration.py` (real Maven/JDK run, native Windows JDK 24).
- Result: **N2 → `UNRESOLVED(VICTIM_FAILS_ALONE)`** for the first time through the real
  pipeline — 12/20 alone-successes (i.e. 8/20 alone-failures, consistent with the ~50% rate
  both platforms measured after the mechanism fix). F1/F2/N1 unchanged
  (`VERIFIED`/`VERIFIED`/`UNRESOLVED(VICTIM_FAILS_ALONE)`). Saved: `eval/reports/n2.json`.
- Updated `eval/reports/README.md` (added N2 to the results table and to "What's NOT here
  yet" — now only F3 remains, pending W10), `docs/08-MidEval/iteration-plan.md`'s W9 row,
  `docs/09-Team/members.md`'s M3 row, and `docs/08-MidEval/demo-plan.md`'s "Mocked or
  hardcoded components" table (both rows there were stale — still said W9/the evidence
  extractor wiring was "not built yet"/"not wired in yet", though both had been done in the
  previous session).
- Limitation: F3 remains the only fixture case not in `eval/reports/` — genuinely blocked on
  W10 (multi-polluter search/minimisation, M2, not started: confirmed by reading
  `runner/search.py`, which has only a one-by-one `find_polluter`, no deletion-minimisation
  module).

## 2026-10-10 — Answered 3 open contract questions; agreed ADR-005

**Requirement:** a full `docs/` read-through (same session as the N2 addition above) surfaced
three questions in `docs/contracts/resource-evidence.md` marked `OPEN (Member 3)`, and ADR-005
(`docs/03-Design/decisions/ADR-005-w9-diagnose-cli.md`, M2's real W9 CLI design) needing M3's
agreement. Decided with the member, not unilaterally — each answer below was proposed, the
member confirmed "go with your recommendations," then written.

- **Q2 (`victim_read_location` naming a helper, not the test method):** answered **yes, that is
  the intended meaning** — it names where the read instruction actually executes (F2:
  `FeatureFlags#isTurboEnabled@2`), symmetric with `polluter_write_location`. No code or schema
  change: confirms `eval/report.py`'s existing behaviour, which already takes `report_fields`'s
  locations as-is.
- **Q4 (ground truth has no expected bytecode offsets, Phase 5 checks resources only):**
  answered **acceptable** — `GroundTruthTest` already catches the failure mode that matters
  (wrong resource) automatically on every change; exact offsets were hand-verified for F1 and
  spot-checked for F2 (independently, by Member 1, against `eval/reports/f2.json`). Encoding
  exact offsets into `ground_truth.json` would be brittle for little extra protection.
- **Q6 (BRITTLE cases, POC FJ-01's inverse-polluter shape):** answered **out of scope for
  Iteration 1**, same boundary as filesystem evidence — no fixture case exercises it, so there
  is no real case to drive a new outcome category under schedule pressure.
  `UNRESOLVED(VICTIM_FAILS_ALONE)` is not wrong for a brittle case (the victim genuinely does
  fail alone), just not the most informative category; a distinct reason is named as Iteration
  2 work if a real brittle case (e.g. a fastjson pair) turns up in evaluation.
- **ADR-005 agreement:** ticked M3's row — `assemble_report(runs, fields)` as the only report
  builder and catching `UnhandledStatus` both match what Phase-W9 work (above) already built
  and verified; nothing in the ADR asks `eval/` to change.
- Command: `py -m unittest discover -s eval/tests -v` (unaffected — these are doc-only
  decisions, no code touched). Result: 68/68 passed.
- Limitation: M1's row in ADR-005 is still unticked, so the ADR is not yet fully agreed by all
  three members — only M3's part of this entry is closed. (Later ticked by M1 in PR #30 —
  ADR-005 is now fully agreed.)

## 2026-10-10 — Agree ADR-006 (evidence depth 1–5); ADR-007 decided, not yet tickable

**Requirement:** two more ADRs appeared needing M3's agreement, found while re-checking repo
state for "what's left for M3": ADR-006 (M1, `docs/03-Design/decisions/ADR-006-evidence-depth-
auto-deepen.md` — accept depths 1–5, pair mode auto-deepens one level at a time only when
`DEPTH_LIMIT` was hit, stopping at the shallowest edge; new `analyse_pair()` helper) and ADR-007
(M2, on branch `m2/w10-minimise`, not yet a PR — `ddmin` multi-polluter minimisation for F3,
reusing `POLLUTER_FOUND` with a list of polluters).

- **ADR-006: ticked M3's row, agree.** Reasoning: the shallowest-depth-wins rule means F1/F2/F3
  keep paying exactly what they pay today (`depth_used` 2), while fastjson's real cases (depth
  4 and 5) become explainable instead of permanently `NO_SUPPORTED_RESOURCE_EVIDENCE`. The
  alternative of raising the *default* depth to 5 would make every pair pay the most expensive,
  most over-approximated walk even when depth 2 already has the answer — worse for the common
  case to fix the rare one. Noted the follow-up this creates: once M1's `analyse_pair()` lands,
  `eval/report.py`'s callers (`eval/tools/run_w9_integration.py`, and M2's `runner/cli.py`)
  switch their separate `analyse_test`+`find_edges` calls to the one helper — not done yet,
  since `analyse_pair` doesn't exist in `main` yet.
- **ADR-007: agree in principle, not yet ticked in the file.** The ADR only exists on M2's own
  in-progress branch (`m2/w10-minimise`), not `main`, and there is no PR for it yet — nothing to
  safely commit the tick against without writing onto another member's unfinished branch.
  Recorded here instead: I agree with the proposed rule ("`POLLUTER_FOUND` reused for several
  polluters; first polluter's resource shown, the rest named in `limitations`") because it
  applies the exact same shape already agreed for Q1/Q4 (`edges[0]` plus a `limitations` note)
  to a new case, rather than inventing a new rule under schedule pressure. `eval.report.
  assemble_report` already accepts a multi-element `diagnosis.polluters` list with no code
  change (`report["polluters"] = [p.to_dict() for p in diagnosis.polluters]` already loops).
  Will tick ADR-007's actual file once M2 opens a PR for W10.
- Command: `py -m unittest discover -s eval/tests -v` (unaffected — doc-only session).
  Result: 68/68 passed.

## 2026-10-10 — Switch to M1's real `analyse_pair()` (ADR-006 follow-up)

**Requirement:** ADR-006's agreement text committed to switching `eval/report.py`'s callers to
`evidence.extract.analyse_pair()` once it landed. Member 1 merged it for real (PR #34) the
same day.

- Checked first, before changing anything: `eval/report.py` itself needed no change — it
  already takes `report_fields(pair)`'s output as an opaque `resource_fields` argument and has
  never called `analyse_test`/`find_edges` directly. Only `eval/tools/run_w9_integration.py`
  (the actual caller) needed the switch.
- File/function: `eval/tools/run_w9_integration.py` — `run_f1()`/`run_f2()` now call
  `evidence.extract.analyse_pair(project, polluter_id, victim_id)` (default depth 2,
  auto-deepen) in place of separate `analyse_test(..., depth=DEFAULT_DEPTH)` calls for the
  polluter and victim combined with `find_edges()`.
- Command: `py -m unittest discover -s eval/tests -v`. Result: 68/68 passed (no test exercises
  this script directly, as documented in its own module docstring).
- Command: `py eval/tools/run_w9_integration.py` (real Maven/JDK run, native Windows JDK 24).
- Result: **F1 → `VERIFIED`, F2 → `VERIFIED`, N1/N2 → `UNRESOLVED(VICTIM_FAILS_ALONE)`** — all
  four unchanged. Diffed the regenerated `eval/reports/{f1,f2,n1}.json` against the previously
  committed versions: identical except the execution-record timestamp (confirms F1 and F2 both
  still resolve their real edge at depth 2, exactly as before — the auto-deepening adds no
  cost here, only capability for deeper real cases). `n2.json` differs by its alone-success
  count (9/20 this run vs 12/20 previously) and the timestamp only — expected, since N2 is
  intermittent by design; the outcome itself (`VICTIM_FAILS_ALONE`) is unchanged.
- File/function: `eval/reports/README.md` — documented the switch and why it changes nothing
  observable on the fixture.
- Limitation: none introduced. This only removes a dependency on the now-deleted separate
  `analyse_test`+`find_edges` call pattern; fastjson still has not been run through the full
  `diagnose()` pipeline (only through the extractor, as before).

## 2026-10-10 — Fix a real contradiction Member 2 found in W10's evidence wording (PR #35)

**Requirement:** Member 2's W10 PR (#35, F3 now `VERIFIED` end to end via `ddmin` minimisation)
flagged a real bug against `eval/report.py`: their new multi-polluter combining function
(`runner/cli.py`'s `combine_fields`, on branch `m2/w10-minimise`) can set
`shared_resource=None` (because not every polluter has an edge, so none is shown as the
primary resource) while its own `limitations` already name which specific polluters *did*
have an edge. `assemble_report`'s unconditional "No polluter-write/victim-read resource edge
was found by static analysis" line, appended whenever `shared_resource is None`, directly
contradicts those specific lines.

- Read the real diff before fixing anything: `git diff origin/main...origin/m2/w10-minimise --
  runner/cli.py` on `m2/w10-minimise` commit `8a16388`. Confirmed the exact shape:
  `combine_fields`'s "not every polluter has evidence" branch returns
  `dict(fields[0], shared_resource=None, ..., limitations=lines + found + missing)` where
  `found`/`missing` already say, per polluter, whether its edge was found.
- File/function: `eval/report.py` — `assemble_report` now reads an optional
  `any_edge_found: bool` key from `resource_fields` (defaulting to the old
  `shared_resource is not None` check when the key is absent, so M1's ordinary
  single-polluter `report_fields()` output, which never sets this key, is completely
  unaffected). The generic blanket line is now gated on `any_edge_found`, not `edge_found`.
  `edge_found` itself is unchanged and still drives `DecisionInput.resource_edge_exists` (the
  VERIFIED/NO_SUPPORTED_RESOURCE_EVIDENCE decision) — only the limitations *text* changes, not
  the outcome logic, which already matches ADR-007's rule ("VERIFIED only if every polluter has
  an edge") with no change needed.
- File/function: `eval/tests/test_report.py` — two new tests:
  `test_several_polluters_partial_evidence_suppresses_the_generic_no_edge_line` (some edge
  found, `any_edge_found=True` → generic line absent, specific lines present) and
  `test_several_polluters_zero_evidence_keeps_the_generic_no_edge_line` (`any_edge_found=False`
  → generic line present, correctly). Strengthened the existing
  `test_polluter_found_without_edge_gives_no_supported_resource_evidence` to assert the
  generic line is still present for the plain single-polluter case (backward compatibility).
- Mutation check: changed `if not any_edge_found:` back to `if not edge_found:` — the new
  partial-evidence test failed exactly as expected, reproducing the contradiction verbatim
  (`'...found by static analysis.' unexpectedly found in [...]`); restored
  (`git diff eval/report.py` clean after).
- Command: `py -m unittest discover -s eval/tests -v`. Result: **70/70 passed** (68 existing +
  2 new).
- Limitation: this only fixes the wording contradiction in `eval/report.py`. It does not land
  M2's `combine_fields` change itself (`runner/cli.py`, their file, still on their own
  unmerged branch) — their combining function needs one more line once this fix merges:
  `any_edge_found=bool(found)` added to the returned dict in the "not every polluter has
  evidence" branch. Flagged back to Member 2 rather than edited myself (not my folder).
- Also recorded: agreement with ADR-007's per-polluter report rule (first polluter's resource
  shown, others named in `limitations`, `VERIFIED` only if every polluter has an edge) as asked
  in PR #35's description — not yet tickable in the ADR file itself, same situation as
  ADR-006 before it merged: the file exists only on Member 2's unmerged branch, not `main`.

## 2026-10-10 — Tick ADR-003, ADR-004, ADR-007; confirm F3's ground truth end to end

**Requirement:** Member 2 relayed four items once ADR-007 (W10) merged to `main`: tick ADR-007
there for real now that it's mergeable; tick ADR-003 and ADR-004 (both had an empty M3 row
left over from earlier in the project); update `ground_truth.json`'s F3 note, which still said
"needs W10"; and (separately, "when you have time") the NOT_REPRODUCED/schema-change ask
already tracked as ADR-008.

- Verified each claim against the real repo before acting on any of it: read ADR-007's
  agreement table on `main` directly (M1 ☐, M2 ☑, M3 ☐, confirmed empty), ADR-003's and
  ADR-004's M3 rows (both ☐, confirmed empty), commit `539b2dc` (`git show`, confirmed it adds
  `any_edge_found=bool(found)` to `combine_fields`'s mixed-evidence branch exactly as
  described), and `ground_truth.json`'s F3 entry (confirmed it still read "needs W10").
- File/function: `docs/03-Design/decisions/ADR-007-w10-ddmin-minimisation.md`,
  `ADR-003-order-runner-junitcore-harness.md`, `ADR-004-w7-diagnosis-runs.md` — ticked M3's row
  on each, with a comment specific to what M3's own code actually does (not a bare checkmark):
  ADR-007 confirms the per-polluter rule and that `assemble_report` needed no change for a
  multi-polluter `POLLUTER_FOUND` (the field was already a list); ADR-003 notes `eval/`
  consumes the harness's `DiagnosisRuns` output without needing its internals; ADR-004 confirms
  `n=20` (already used throughout `eval/benchmark/`) and that the `DiagnosisRuns`→
  `DecisionInput` mapping built in `eval/report.py` (W9) matches this ADR's fields.
- File/function: `fixtures/od-fixture/ground_truth.json` — F3's `expected_outcome_notes`
  appended (not replaced, so the original prediction stays legible) with the real W10
  confirmation, citing `docs/evidence-m2.md`'s real W10 entries: `diagnose()` gives
  `POLLUTER_FOUND` with both polluters (search 12 runs, minimisation shrinks the 12-test
  prefix to the 2-test 1-minimal set); the real end-to-end command gives `VERIFIED`, 20/20
  reproduced, 0/20 alone, resource `odfixture.Toggles#flagA` shown with `flagB` named in
  `limitations`.
- Command: `py -c "import json; json.load(open('fixtures/od-fixture/ground_truth.json'))"` —
  confirmed the edit kept the file valid JSON (easy to break with an unescaped character inside
  a long string value).
- Command: `py -m unittest discover -s eval/tests -v`. Result: 70/70 passed (unaffected by a
  documentation-only / ground-truth-notes-only change, as expected — no test asserts on the
  exact text of `expected_outcome_notes`).
- Limitation: none. The larger NOT_REPRODUCED/schema-change ask (ADR-008: nullable
  `failure_signature`, optional `order_exploration`, new `INFRASTRUCTURE_FAILURE` reason, new
  fixture cases F4/N3) is real, substantial new work, not done in this entry — tracked
  separately, pending the member's decision on scope and timing.

## 2026-10-10 — ADR-008: NOT_REPRODUCED handling, schema change, fixtures F4/N3

**Requirement:** the member approved going ahead with ADR-008 (Member 2's proposal for
failures that do not reproduce). Member 3's side (step 3 of the ADR's own order-of-work
table): the schema change, `decide()` row, `assemble_report` wiring, and two new
pre-registered fixture cases.

**Fixtures F4 and N3, written before any run** (`fixtures/od-fixture/ground_truth.json`):
- **F4** (`AlwaysEarlyVictimTest`/`ZzzLatePolluterTest`, new `LateFlag` static field): class
  names chosen so the polluter sorts alphabetically after the victim, exploiting this
  project's confirmed alphabetical discovery order (`docs/evidence-m2.md`'s W7 Task 3) so the
  natural order can never reproduce the bug — exactly the shape ADR-008's order-shuffling step
  is for.
- **N3** (`EnvDependentNegativeTest`): models a failure whose real cause is an environment
  variable FlakeTrace never sets. Deliberately does **not** check the literal `CI` variable
  name — GitHub Actions sets `CI=true` on every real runner, so that would make this negative
  control fail on our own CI job. Uses a fictitious name (`FLAKETRACE_N3_NEVER_SET`) instead.
- Real verification before writing a single line of Python: compiled
  (`mvn -B -q -f fixtures/od-fixture/pom.xml test-compile`), confirmed the real discovered
  order places `AlwaysEarlyVictimTest` first and `ZzzLatePolluterTest` last of 16 methods
  (`runner.discovery.discover_order`), ran the full module (`mvn -B test`, no new failures:
  still exactly F1/F2/N1/F3's four, F4/N3 both pass), ran the real one-fresh-JVM order
  `[ZzzLatePolluterTest#setLateFlag, AlwaysEarlyVictimTest#expectsLateFlagUnset]` via
  `runner.order_runner.OrderRunner.run_ordered` (polluter passes, victim FAILS with
  `java.lang.AssertionError` — exactly the predicted mechanism), and ran the real victim alone
  (passes). Also ran real `diagnose()` on both F4 and N3 in the natural order: both give
  `NOT_REPRODUCED`, `alone_n=0` — confirming the exact gap ADR-008 names, not a bug in the
  fixture. **Independent cross-check**: Member 1's own `GroundTruthTest`
  (`evidence.tests.test_extract`, untouched by me) also passed with these two new cases added
  to `ground_truth.json` — it found the real `LateFlag#isSet` edge for F4's pair and no edge
  for any N3 pair, matching my ground truth exactly, from a completely independent test.
- Added F4/N3 to `eval/benchmark/manifest.json` (both `not_yet_run`, no log files) — required
  by `test_real_manifest_matches_fixture_ground_truth`, which checks the two files' case IDs
  match exactly.

**Schema** (`eval/schema/report.schema.json`): `failure_signature` nullable via the same
`oneOf`/null pattern already used (and already fixed once this session) for `shared_resource`;
new optional `order_exploration` object; `INFRASTRUCTURE_FAILURE` added to the
`unresolved_reason` enum. **Found and fixed a real gap beyond what the ADR literally asked
for**, by reading `runner/diagnose.py`'s actual code rather than assuming: ADR-008's text says
nullable `failure_signature` "only for NOT_REPRODUCED," but `run_steps` sets
`reference_signature=None` for its *entire* `NOT_REPRODUCED` status, which `INFRASTRUCTURE_FAILURE`
is decided from too (same status, same `None` reference) — so a schema tied strictly to the
`NOT_REPRODUCED` string would reject a real future `INFRASTRUCTURE_FAILURE` report. Widened the
conditional to cover both reasons before this became a real bug.

**`eval/outcome.py`**: `REASON_INFRASTRUCTURE_FAILURE`; new `DecisionInput.infrastructure_failures`
field (default 0 — a caller that never reports it gets exactly the pre-ADR-008
`SIGNATURE_MISMATCH` behaviour, proven by a dedicated test); new `decide()` row between
`NOT_REPRODUCED` and `SIGNATURE_MISMATCH`.

**`eval/report.py`**: `assemble_report` now handles `NOT_REPRODUCED` (was `UnhandledStatus`);
builds `failure_signature: null` whenever `diagnosis.reference_signature is None` (covers both
`NOT_REPRODUCED` and `INFRASTRUCTURE_FAILURE`); reads `infrastructure_failures` via
`getattr(diagnosis, ..., 0)` and the new optional `order_exploration` via a `hasattr` check on
all five needed fields — both forward-compatible with Member 2's `DiagnosisRuns` not having
them yet, omitted entirely (schema allows it) until that lands.

- Command: `py -m unittest discover -s eval/tests -v`. Result: **80/80 passed** (68 existing +
  12 new, across `test_schema_validator.py`, `test_outcome.py`, `test_report.py`,
  `test_yield_report.py`).
- Mutation checks, each confirmed failing before restoring: `decide()`'s new row condition
  forced to `False` → `test_row3b_infrastructure_failure` failed exactly as expected;
  `assemble_report`'s `failure_signature = None if ref is None` forced to always build a dict
  → `test_not_reproduced_with_isolation_data_gives_unresolved` failed with the real
  `AttributeError` that would occur in production.
- Real run confirming no regression: `py eval/tools/run_w9_integration.py` — F1/F2 still
  `VERIFIED`, N1/N2 still `UNRESOLVED(VICTIM_FAILS_ALONE)`, resource edges and locations
  byte-identical to before (only the execution-record timestamp and N2's own designed
  randomness differ); `original_failing_order` correctly grew to include the 3 new fixture
  classes that sort before each victim alphabetically.
- Real run confirming the exact documented limitation, not a bug: real `diagnose()` on N3 in
  the natural order gives `NOT_REPRODUCED` with `alone_n=0`; calling `assemble_report` on that
  real diagnosis raises `ValueError: isolation_n must be > 0` — exactly as designed, pending
  Member 2's `diagnose()` change (ADR-008 step 4, not yet landed).
- **Also discovered and fixed, independent of this ADR**: this session's branch had been
  created from a stale local `main` ref (missing the just-merged ADR-003/004/007 ticks commit
  and everything after it up to Member 1's ADR-007 agreement). Found it the moment I checked
  `git log --oneline -1 HEAD` against `origin/main` and saw they disagreed by several commits.
  Diagnosed the exact scope with `git diff --name-only <stale-base> origin/main` (8 files,
  only 3 overlapping with this session's own edits), restored the 5 untouched files directly
  from `origin/main`, and manually re-applied this session's own F4/N3 additions and new
  entries on top of the other 3 files' correct (non-stale) content — rather than running
  `git merge`/`git stash`/`git rebase` myself, which this project's rules reserve for the
  member. Confirmed clean afterward: `git diff origin/main -- <each of the 8 files>` shows
  zero difference on the 7 untouched files and only this session's genuine new content on
  the 8th (`ground_truth.json`).

## 2026-10-10 — Fix a real merge-order risk Member 2 found in PR #45

**Requirement:** Member 2 reviewed PR #45 (ADR-008's M3 side) and flagged a real risk: today,
`runner.diagnose()` still returns `NOT_REPRODUCED` with `alone_n = 0` (ADR-008 step 4, their
diagnose() change making it always run the alone check, hasn't landed yet). Calling
`assemble_report` on that real shape hits `eval.outcome.DecisionInput`'s `isolation_n > 0`
check, raising a bare `ValueError` the CLI does not catch — crashing with a traceback instead
of the designed "exit 3, no report yet" behaviour, regardless of which of the two changes
(theirs or mine) merges first.

- File/function: `eval/report.py` — `assemble_report` now raises `UnhandledStatus` explicitly
  when `diagnosis.status == NOT_REPRODUCED and diagnosis.alone_n == 0`, before building
  `DecisionInput` at all. Once Member 2's `diagnose()` change lands (`alone_n > 0` always),
  this branch is simply never reached and the real report-building path runs unchanged.
- File/function: `eval/tests/test_report.py` — renamed/updated
  `test_not_reproduced_with_todays_real_shape_is_unhandled_not_a_crash` to assert
  `UnhandledStatus` (was `ValueError`).
- Command: `py -m unittest discover -s eval/tests -v`. Result: 80/80 passed.
- Mutation check: disabled the new guard (`if False:`) — the test failed with the exact real
  `ValueError: isolation_n must be > 0, got 0` traceback Member 2 described; restored,
  confirmed `git diff` clean.
- Also asked by Member 2: comment agreement on ADR-008's PR (#42) or tick M3's row there.
  Not done directly — I have no GitHub write access in this environment; drafted a comment for
  the member to post, and will tick the actual ADR file in a follow-up PR once #42 merges
  (same pattern as ADR-006/007).
- **Found independently, not mentioned by Member 2**: PR #45's real CI `runner` job was
  failing for a different, real reason — three hardcoded counts in `runner/tests/` (M2's
  folder) were stale because this PR's new F4/N3 fixture classes changed the fixture's real
  discovered-order size (13 → 16 methods) and F3's search prefix (12 → 14). Flagged to the
  member, who authorized fixing it directly rather than waiting on Member 2 — see the next
  entry for the fix itself and the real re-verification.

## 2026-10-11 — Fix the 3 stale hardcoded counts in `runner/tests/`, with the member's go-ahead

**Requirement:** the member authorized fixing the three CI failures named above directly,
rather than relaying them to Member 2 first. `runner/tests/` is not my folder, so this is
recorded explicitly, with the real reasoning, rather than a silent edit.

- Re-verified the real discovered order first (`runner.discovery.discover_order` on the
  compiled fixture, native Windows JDK 24): **16** methods, `AlwaysEarlyVictimTest#...` first,
  `ZzzLatePolluterTest#...` last — matches the design intent exactly (both chosen to sort at
  the extremes).
- File/function: `runner/tests/test_discovery.py` —
  `test_all_thirteen_fixture_methods_in_alphabetical_class_order` renamed to
  `test_all_fixture_methods_in_alphabetical_class_order` (the literal "thirteen" is no longer
  true); asserts `len == 16`, first two = `[AlwaysEarlyVictimTest#expectsLateFlagUnset,
  ConfigPolluterTest#pollute]`, last = `ZzzLatePolluterTest#setLateFlag`.
- File/function: `runner/tests/test_diagnose.py` — ran the real test first to get the exact
  number rather than computing it by hand:
  `py -m unittest runner.tests.test_diagnose.TestDiagnoseOnFixture.test_f3_two_polluters_are_found_by_minimisation`
  → real failure, `AssertionError: 14 != 12`, confirming the exact new value. Updated
  `search_runs` assertion from 12 to 14, with a comment naming the real cause (two of the new
  classes sort before F3's victim, growing its search prefix).
- File/function: `runner/tests/test_cli.py` — same real cause; updated the summary-line
  substring assertion from `"12 earlier tests"` to `"14 earlier tests"`.
- Command: `py -m unittest discover -s runner/tests -v` (real JVM runs, native Windows JDK 24).
  Result: **108/108 passed** (was 105/108 before this fix, confirmed by reproducing the 3
  failures first).
- Command: `py -m unittest discover -s eval/tests -v`. Result: 80/80 passed (unaffected, as
  expected — pure Python logic, no JVM).
- Limitation: none found beyond the three fixed. CI on JDK 8/Linux not yet re-confirmed from
  this exact commit (runs on the PR).
