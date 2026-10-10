# Live demo plan (Form 2 #3 — 25 marks)

*Status: target plan. Nothing below runs yet — update each step to `REHEARSED` with the date.*

**Core module:** order-dependent failure diagnosis — ordered re-execution, polluter search,
minimisation, static resource evidence, repeated-run verification.
**Why it is meaningful:** it is the approved problem itself, not a UI over it. The POC UI in
`POC/` replays recorded data and is **not** used for the live demo.

| Field | Content |
| --- | --- |
| Input | Path to a Maven/JUnit 4 project + the victim test id |
| Processing | Fresh-JVM ordered runs → victim-alone check → polluter search → minimisation → javap evidence → `wilson_interval` → `decide()` |
| Output | A JSON report validated against `eval/schema/report.schema.json`, printed as a readable summary |
| Dependencies | JDK 8+, Maven, Python 3.11, `jsonschema` |
| Known limitations | Static evidence only; two resource kinds; F3's report shows one resource (`flagA`) and names the second (`flagB`) in `limitations`; the 31-shuffle budget comes from a Python study (assumption for JUnit) |

## Running order (8 minutes)

| Step | Action | Expected result | Evidence visible | Presenter | State |
| --- | --- | --- | --- | --- | --- |
| 0 | State the version: `git describe` → `mid-eval-v1` | Clean tag | Terminal | M2 | — |
| 1 | Show F1 source: no logging anywhere; `git status` clean | Nothing to hide | Editor | M1 | — |
| 2 | Diagnose F1 (normal case) | `VERIFIED`; polluter `ConfigPolluterTest#pollute`; resource `Config.mode`; e.g. *n/n* vs *0/n* alone | Report JSON + summary | M2 | — |
| 3 | Show the resource evidence behind step 2 | `putstatic` / `getstatic` with bytecode offsets | Extractor output | M1 | — |
| 4 | Show source unchanged | Hash match, `git status` clean | `source_integrity.passed = true` | M2 | — |
| 5 | Diagnose N1 (failure case) | `UNRESOLVED(VICTIM_FAILS_ALONE)` — refuses to blame a polluter | Report JSON | M3 | — |
| 6 | Diagnose F3 (edge case) | `VERIFIED`: both polluters (`setFlagA`, `setFlagB`) found by `ddmin`, 20/20; `flagB` named in `limitations` | Report JSON | M2 | — |
| 6b | Optional: diagnose F4 and N3 (ADR-008) | F4 `VERIFIED` through a shuffled order (seed recorded); N3 `UNRESOLVED(NOT_REPRODUCED)` with the bound and "not proof of reliability" | Report JSON + summary | M2 | — |
| 7 | Show CI run and tests on the PR | Green checks | GitHub Actions | M3 | — |
| 8 | State boundaries | What is implemented vs not yet | Slide 6 | M2 | — |

Any result written in the "Expected result" column is a target; the real values come from the
run and go into `docs/evidence-m2.md`.

## Mocked or hardcoded components

| Component | Implemented | Mocked/substituted | Plan to remove |
| --- | --- | --- | --- |
| Runner | Ordered single-JVM runner (W6) and `diagnose()` (W7): reproduce, victim-alone ×n, one-by-one polluter search, repeat ×n, source hash, execution record — real JVM runs on the fixture | None mocked. Report assembly (`eval/report.py`, W9) is done and wired to this for real, for F1/F2/N1/N2. The W9 command `py -m runner diagnose` runs the whole pipeline (real runs): F1, F2 `VERIFIED`, N1 `UNRESOLVED(VICTIM_FAILS_ALONE)`; F3 `VERIFIED` with two polluters found by `ddmin` (W10). Nothing mocked or missing for the fixture | — |
| Evidence extractor | Pair mode (`--polluter`/`--victim`) and single test, depth 1–5 (default 2, pair mode deepens only when needed, ADR-006); real javap on real classes; F1 edge `Config#mode` 1→1, F2 edge `odfixture.turbo` 4→`FeatureFlags.isTurboEnabled@2` | None mocked. Wired into Member 3's report assembly for real (`eval/report.py` calls `find_edges`/`report_fields` directly) | — |
| Outcome + statistics | Yes (M3, tested) | None | — |
| UI | Not part of Mid demo | POC UI uses recorded data | FYP-1 Final or later |

## Fallback

The demo runs entirely offline once Maven dependencies are cached. Before the meeting: run
`mvn -o test-compile` once on the demo laptop to confirm the offline cache works. A recorded
terminal session is kept as backup evidence only — it does not replace the live run.
