# Claims Ledger

*Every claim FlakeTrace makes, what backs it, and whether that backing is solid.*

**The rule:** if it is not in this table with a source, it does not get asserted to the
panel. Claims with status `OPEN` or `ASSUMPTION` are stated **as** open or assumed — the
Panel Question Bank is explicit that a supervised panel forgives an open item far more
readily than a fabricated closure.

**Status values:** `SETTLED` (evidenced, defensible) · `OPEN` (known gap, closure planned) ·
`ASSUMPTION` (believed, unevidenced — must be labelled aloud) · `POLICY` (our choice, not a
published finding — defend as a choice) · `FROZEN` (committed pre-registration, cannot change without recorded approval)

---

## A. Problem and stakeholders

| # | Claim | Backing | Source | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| A1 | Order-dependent failures are a real, recurring workflow problem | 3 practitioner interviews; all three independently describe manual binary-search isolation with no tooling support | [[00-Meta/stakeholder-evidence]] | Joint | SETTLED |
| A2 | The current workflow is manual and expensive | SH1: "run the failing test with smaller groups of preceding tests until we identify which combination triggers the failure… time-consuming". SH2: "manual binary search — intuition and trial and error. There is no tooling support for it." SH3: "binary search isolation across preceding tests… time-consuming" | [[00-Meta/stakeholder-evidence]] | Joint | SETTLED |
| A3 | Time cost per incident | SH1: 30–60 min simple, several hours hard. SH2: 25–30 min, flaky failures "a few times a week", root-cause dug into 1–2×/month. SH3: 15 min minor, **2 major incidents this year each consuming nearly a full working day** | [[00-Meta/stakeholder-evidence]] | Joint | SETTLED |
| A4 | Existing tools do not explain cross-test interference | SH1: tools "normally do not automatically tell us that Test A modified some shared state that caused Test B to fail 30 tests later" | [[00-Meta/stakeholder-evidence]] | Joint | SETTLED |
| A5 | Self-hosting is a requirement, not a preference | SH3: sending source externally "out of question" — schemas, migrations, student/payment data. SH1: "strongly preferable" to keep local | [[00-Meta/stakeholder-evidence]] | Joint | SETTLED |
| A6 | Typed abstention is wanted by users, not a cop-out | SH1: "a clearly stated unknown is more useful than a confident but incorrect diagnosis". SH2: "A tool that guesses is worse than useless… if it tells me test B is caused by test A and it is wrong, I have wasted an hour chasing a phantom" | [[00-Meta/stakeholder-evidence]] | Joint | SETTLED |
| A7 | Quarantine removes coverage permanently | SH3: 8-test accessibility suite on `continue-on-error` — "practically disabled in function if not in name" | [[00-Meta/stakeholder-evidence]] | Joint | SETTLED |
| A8 | Our CI overhead budget is realistic | SH1: 5–15 min acceptable on PR if not every build. SH3: 5 min "pushback", 15 min "completely unacceptable" on every PR, **but 30 min tolerable opt-in or nightly** | [[00-Meta/stakeholder-evidence]] | M2 | SETTLED |
| **A9** | **Our stakeholders face the problem in our target ecosystem** | **NOT SUPPORTED.** All three are Python/pytest, Node/Vitest, TS/Vitest. **None uses Java, Maven, JUnit or Surefire.** Their OD instances are DB/staging-state pollution, not JVM static fields | [[00-Meta/stakeholder-evidence]], [[07-Defense/weak-points]] | Joint | **OPEN** |
| A10 | Order dependence is a minority by count but disproportionate by investigation time | Luo et al.: 19/201 commits (12%). Lam et al. iDFlakies dataset: 50.5% of 422 flaky tests OD. Retry works for timing flakiness, not for OD | [[01-Literature/per-paper/luo-2014-empirical-analysis]] | Joint | SETTLED |

## B. Prior art and differentiation

| # | Claim | Backing | Source | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| B1 | We do **not** claim minimisation as a contribution | iFixFlakies' Minimizer already produces 1-minimal orders via delta debugging | [[01-Literature/per-paper/ifixflakies]] | Joint | SETTLED |
| B2 | We do **not** claim ranking OD-relevant tests as a contribution | RankF already does this, validated on 155 OD tests / 34 modules / 24 projects | [[01-Literature/per-paper/rankf]] | Joint | SETTLED |
| B3 | We do **not** claim dynamic shared-state explanation as a contribution | Takuan compares Daikon invariants across passing/failing orders and handles filesystem state | [[01-Literature/per-paper/takuan]] | Joint | SETTLED |
| B4 | We do **not** claim OD detection as a contribution | iDFlakies detects and partially classifies via reordering. Our input is a *known* OD failure | [[01-Literature/per-paper/idflakies]] | Joint | SETTLED |
| B5 | Our delta is the **composition**: budget + certification + intervention + typed abstention | No cited system provides all four. Section 5.5 of the lit review states this explicitly | [[01-Literature/contemporary-comparison-table]] | Joint | SETTLED |
| B6 | Resource evidence is a legitimate opening, not an invented gap | Rahman et al. *themselves* name dynamic execution traces as the unexploited information source for future work | [[01-Literature/per-paper/rankf]] | M1 | SETTLED |
| B7 | Multi-test dependence is a real remainder, not negligible | Zhang et al.: 82% of dependent tests revealed by ≤2 tests — leaves a non-empty 18%. RankF excludes joint dependence citing rarity | [[01-Literature/per-paper/zhang-2014-test-independence]] | M2 | SETTLED |
| B8 | Commercial products do not do this | Trunk / Tuist / Develocity documentation describes detection, tracking, quarantine — **not** which earlier test caused it, through which resource, at what confidence | [[01-Literature/commercial-tools]] | Joint | SETTLED — *phrase as "their published documentation does not describe it", never "they cannot"* |
| B9 | No prior FAST FYP overlaps | Systematic sweep of 989 records, Fall 2019–Fall 2025, for testing/flakiness/test-order/CI/debugging terms. 3 structurally comparable survivors: F22-032-D-ETesting, F22-033-D-WebSPLAT, S25-049-D-TestML | [[01-Literature/prior-fyp-comparison]] | Joint | SETTLED |
| B10 | No *internal module* of a prior FYP overlapped | **We do not claim this.** A title-and-summary repository cannot prove it | [[01-Literature/prior-fyp-comparison]] | Joint | OPEN — *stated as a limit, deliberately* |
| B11 | We have run the baseline tools | **NOT YET.** Baseline integration scheduled FYP-I early; measurement is an explicit Final-1 exit condition | [[07-Defense/weak-points]] | M3 | **OPEN** |

## C. The POC

| # | Claim | Backing | Source | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| C1 | 8 targets built at pinned SHAs across 2 projects | json-iterator/java @ 6925cf4c (MIT), alibaba/fastjson @ e05e9c5e (Apache-2.0). Build logs, container digests held | [[05-Testing/poc/poc-log]] | M3 | EXECUTED |
| C2 | 4 cases reproduced in clean containers | 10/10 replay reliability, Wilson 95% [0.72, 1.00] | [[05-Testing/poc/raw-numbers]] | M3 | EXECUTED |
| C3 | 2,606 controlled orders run | 5,212 test-method invocations, single-scan protocol | [[05-Testing/poc/raw-numbers]] | M2 | EXECUTED |
| C4 | Zero static-field write/read overlap at depth 1 | Every candidate, every case. Not a weak signal — **no signal** | [[05-Testing/poc/raw-numbers]] | M1 | EXECUTED |
| C5 | Ranked strategy saved 0% vs one-by-one | Byte-identical ordering, because the overlap score was empty for every candidate | [[05-Testing/poc/raw-numbers]] | M2 | EXECUTED |
| C6 | Depth is the mechanism of the failure | FJ-02: state-setter writes `JSON.defaultTimeZone` at `DateParserTest.setUp@5`; target reads at `TypeUtils.cast@536` — **two hops down**. Invisible at one hop | [[07-Defense/decisions/depth-configurable]] | M1 | EXECUTED |
| C7 | Depth 2 moved FJ-02 rank 39 → 1 | 97.4% reduction in confirmations *for that case* | [[05-Testing/poc/raw-numbers]] | M1 | EXECUTED |
| **C8** | **Depth-2 extraction works generally** | **NOT SUPPORTED.** One case moved. The other three did not move at any depth tested. *"One case improving is a mechanism finding, not a method."* | [[05-Testing/poc/poc-log]] | M1 | **ASSUMPTION — never assert** |
| **C9** | **Static-field analysis is useless in general** | **NOT SUPPORTED, in our own favour.** n=4, and both subjects are JSON libraries built around global static configuration — the *most favourable possible substrate* for the hypothesis | [[05-Testing/poc/poc-log]] | M1 | ASSUMPTION — *state the limit ourselves* |
| C10 | Two harness defects were found and corrected | Defect 1: 182 → 0 false polluters after adding suite `@BeforeClass` context. Defect 2: `TZ=Asia/Shanghai` override erased the phenomenon; removed | [[05-Testing/poc/poc-log]] | M3 | EXECUTED |
| C11 | Pre-registration was genuine | Definitions and gates committed to version control **before** any experiment ran; commit timestamp held | [[05-Testing/poc/poc-log]] | M3 | EXECUTED |
| C12 | Frozen definitions were amended after freezing | **Disclose unprompted.** 27 Aug: execution-context fidelity added. Changed neither reproduction criterion nor strategy scoring; moved a result 182 → 0, *against our own interest*. Both commits held | [[05-Testing/poc/poc-log]] | M3 | SETTLED — *volunteer this* |
| **C13** | **Isolation classification vs reproduction count** | **INTERNAL INCONSISTENCY.** Isolation gave 6 victims / 2 brittle; reproduction gave 4, all fastjson — but 2 fastjson targets were classified brittle. Underlying data exists; summary wording needs reconciling | [[07-Defense/weak-points]] | M3 | **OPEN — fix before quoting any POC figure externally** |
| C14 | Reproduction was 4 of 8 | Gate was written as "≥3 of 4". 4 clears the count but 50% is not the rate the gate implied. **Partial**, not pass | [[05-Testing/poc/raw-numbers]] | M3 | SETTLED — *report as partial* |
| **C15** | **Evidence is single-project** | All four reproduced cases came from fastjson. jsoniter returned zero. Setup required ≥2 projects | [[07-Defense/weak-points]] | M3 | **OPEN — out-of-domain subject is priority 4 before defence** |

## D. Method and parameters (see [[01-Literature/parameter-provenance]] for full table)

| # | Claim | Backing | Source | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| D1 | 10 isolation replays | Constrained, not fixed, by literature. Lam et al.: 87.8% pass within 5 reruns, recommend ≤5. Gruber et al.: 10 reruns surface ~54% OD. Hashemi et al.: 10×10, same results at 20 and 30 | [[01-Literature/parameter-provenance]] | M2 | SETTLED |
| D2 | 20 orders for order-history evidence | Rahman et al. chose 20 to match iDFlakies; RankFO20 ≥ a 95%-confidence-derived variant | [[01-Literature/parameter-provenance]] | M3 | SETTLED |
| D3 | Wilson interval, not Wald | Brown, Cai & DasGupta: Wald's coverage is "chaotic" and textbook safety claims "cannot be trusted"; Wilson recommended for small n | [[01-Literature/per-paper/brown-cai-dasgupta]] | M2 | SETTLED |
| **D4** | **18/20 and Wilson lower bound ≥ 0.70** | **PROJECT POLICY, not a published finding.** The *estimator* is literature-mandated; the *thresholds* are our acceptance policy | [[01-Literature/parameter-provenance]] | M2 | **POLICY + FROZEN** — frozen after POC/validation, before held-out run |
| **D5** | **25% cost reduction, ≤5pp success loss targets** | **PROJECT-SET success criteria.** The baselines and their published cost figures are literature-derived; the targets are ours | [[01-Literature/parameter-provenance]] | M2 | **POLICY + FROZEN** |
| **D6** | **Budget split between search and verification** | **DERIVED, not cited.** Combines the certifying-algorithm witness requirement with finite-CI-budget evidence. No paper specifies a ratio — which is why the no-verification-reserve ablation is required | [[01-Literature/parameter-provenance]] | M2 | POLICY — *ablation is the test* |
| D7 | Cost unit = test-method invocations | One Maven launch may run 5 or 5,000 tests. Rahman et al. count tests run + separately measured Surefire overhead (averaged over 30 runs) | [[01-Literature/parameter-provenance]] | M2 | SETTLED |
| D8 | Failure equivalence by normalised signature, never exit code | Qi et al. traced invalid repair results to infrastructure checking exit code rather than output — admitted a patch reducing the program to immediate exit | [[01-Literature/per-paper/qi-2015-patch-plausibility]] | M2 | SETTLED |
| D9 | 1-minimal, never "minimum" | Delta debugging returns 1-minimality. Wei et al.: iFixFlakies does not necessarily find all polluters in a prefix. Global minimum is exponential and unreachable under budget | [[01-Literature/per-paper/ifixflakies]] | M2 | SETTLED |
| D10 | Three resource families (static fields, system properties, filesystem paths) | Zhang et al. identify static fields and filesystem among root causes; PolDet monitors heap + filesystem and reports access path/filename as evidence | [[01-Literature/per-paper/poldet-electrictest]] | M1 | SETTLED |
| D11 | Shared-state overlap is a prior, not proof of causation | PolDet: 324 reported polluting tests, 194 judged relevant on manual inspection — a material false-positive rate for a state-difference signal alone | [[01-Literature/per-paper/poldet-electrictest]] | M1 | SETTLED |
| D12 | Instrumentation must be measured, not assumed | ElectricTest: ~20× slowdown for sound dependency detection. PolDet-on-JPF: 1.43× over base JPF | [[01-Literature/per-paper/poldet-electrictest]] | M1 | SETTLED |
| D13 | Split by project, never randomly by test | Two tests in a module share static fields, helpers and often the polluter. RankFL trains per-module holding out the evaluated project | [[01-Literature/parameter-provenance]] | M3 | SETTLED |
| D14 | Catalogues are not benchmarks | Tufano et al.: broken snapshots in 96% of 100 Apache Maven projects; only 38% of history compilable. Rahman et al. lost 249 → 155 on re-execution | [[01-Literature/per-paper/build-rot]] | M3 | SETTLED |
| **D15** | **Median instrumentation overhead threshold** | **NO NUMBER YET, deliberately.** We are not inventing a final overhead figure before we measure it. SH1 gives 5–15 min PR tolerance; SH3 gives 30 min opt-in | [[02-Requirements/non-functional]] | M1 | **OPEN by design** |

## E. Scope and product

| # | Claim | Backing | Source | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| E1 | Committed: Linux container; Maven for build and classpath; JUnit 4 tests run in one JVM via JUnitCore (JUnit 3 `TestCase` via the JUnit38 adapter) (ADR-003) | POC: all 8 cases were JUnit 3 (run under Surefire). Our harness: `runner/tests/test_order_runner.py` runs a JUnit 3 `TestCase` (`runner/tests/resources/LegacyJUnit3Test.java`) — methods listed, victim passes alone, fails after its polluter in one JVM with `junit.framework.AssertionFailedError`. The Linux container is a committed target, not yet built | [[02-Requirements/scope-boundary]], [[evidence-m2]] | M2 | COMMITTED |
| E2 | JUnit 5 is conditional | Becomes committed only after discovery + instrumentation attribute events to correct test boundaries under Jupiter | [[02-Requirements/scope-boundary]] | M2 | GATED |
| E3 | Databases, network, threads, timing are unsupported — not silent | Produce *opaque events* contributing to the abstention decision and the coverage report | [[02-Requirements/scope-boundary]] | M1 | COMMITTED |
| E4 | We never claim definitive causality | Explicit exclusion. Certificate language is "evidence-supported interference path" | [[03-Design/certificate-contract]] | Joint | COMMITTED |
| E5 | CDR does not violate our own repair exclusion | What was excluded is *automatic source-code repair* — the system deciding and applying a fix. CDR consumes a Verified certificate, produces ranked options, a human applies | [[07-Defense/decisions/cdr-gated-module]] | M3 | GATED — *see contradiction note* |
| **E6** | **CDR wording is consistent across our own documents** | **CHECK REQUIRED.** Rev 2 added CDR after the original scope excluded automatic repair. A panel that finds two of our own documents contradicting each other pursues it much harder than a gap we name ourselves | [[07-Defense/weak-points]] | Joint | **OPEN — audit slide deck, proposal doc and Rev 2 before defence** |
| E7 | "Deployed" has a testable definition | Third party installs on clean Linux from documentation, runs one frozen case, obtains same certificate class, replays the order, removes all containers and workspaces | [[02-Requirements/non-functional]] | M2 | COMMITTED |
| E8 | The order runner executes tests in exactly the requested order in one fresh JVM per call, and never drops a test (crash, timeout and skip are reported as failures) | 17 tests in `runner/tests/test_order_runner.py`, including real-JVM runs on fixture F1 (victim alone PASS, after polluter FAIL, reversed order PASS); passes on JDK 21 (local) and JDK 8 (CI run `37957537495`) | [[evidence-m2]] | M2 | SETTLED |
| E9 | W7 finds the ground-truth polluter for F1 and F2, reports F3 as needing more than one polluter instead of guessing (W10 then finds both, E14), and reports N1 and N2 as failing alone — without modifying the fixture source | `runner/tests/test_diagnose.py` real runs; per-case counts (F1: 20/20 after the polluter, 0/20 alone); source hash passed for every case; same tests green on JDK 8 in CI run `37971869749`. N2 (fixed by Member 3 in PR #14): `VICTIM_FAILS_ALONE` in 3 of 3 real local runs (Windows, JDK 21), alone 16, 9, 11 of 20 | [[evidence-m2]] | M2 | SETTLED |
| E10 | The extractor finds exactly the fixture's ground-truth edges and no others | All 156 ordered pairs of fixture tests at depth 2: edges for exactly F1, F2, F3-A, F3-B, on the ground-truth resource; none for N1, N2 or noise tests. `GroundTruthTest`, green on JDK 8 in CI (PR #23) | [[evidence-m1]] | M1 | SETTLED |
| E11 | On real fastjson, depth 1–3 finds no edge for FJ-01 or FJ-02, and says so instead of claiming independence | FJ-01 and FJ-02 at depths 1–3: no edge, `no_supported_resource_evidence`, `DEPTH_LIMIT` where the walk stopped. Exploration: edges at depth 4 (FJ-01) and 5 (FJ-02). C6's read `TypeUtils.cast@536` is reached, but at depth 5, not two hops (needs a joint check of C6/C7 wording) | [[evidence-m1]] | M1 | SETTLED (depth 4/5 is exploration) |
| E12 | One command (`py -m runner diagnose`) goes from a failing test to a schema-validated report, joining all three members' components without modifying the fixture | `runner/tests/test_cli.py` real runs: F1 and F2 `VERIFIED` (F2 through a depth-2 edge), N1 `UNRESOLVED(VICTIM_FAILS_ALONE)`, F3 exit 3 with no report until W10 (now `VERIFIED`, E14); fixture unchanged (local, JDK 21; CI on JDK 8, PR #26 commit `6caaaaf`: runner job 78 tests OK) | [[evidence-m2]], [[03-Design/decisions/ADR-005-w9-diagnose-cli]] | M2 | SETTLED |
| E13 | With auto-deepening (ADR-006), the extractor finds the shared field for both real fastjson cases and keeps the fixture at depth 2 | Real CLI, default settings: FJ-01 `depth_used` 4, FJ-02 `depth_used` 5; all fixture ground-truth pairs `depth_used` 2 (`GroundTruthTest`). The report's single resource is picked by name on ties (FJ-01 shows `defaultLocale`; the causal `defaultTimeZone` is in `limitations`) | [[evidence-m1]] | M1 | SETTLED |
| E14 | When no single test causes the failure, delta debugging finds a 1-minimal set of polluters (never claimed to be the minimum), and the report is `VERIFIED` only if every polluter has resource evidence | Fixture F3: real `diagnose()` → `setFlagA` + `setFlagB` (= ground truth; search 12 runs, minimise 10 = 1 re-check + 9 `ddmin`); the command → `VERIFIED`, 20/20, 0/20 alone, `flagB` named in `limitations`; fake-runner tests incl. 1-minimality and a 100-test prefix shrunk by `ddmin` alone in 48 runs (the search before it still runs once per test); a one-off flaky failure blames nobody (local, JDK 21; CI on JDK 8, W10 PR commit 539b2dc: runner job 104 tests OK) | [[evidence-m2]], [[03-Design/decisions/ADR-007-w10-ddmin-minimisation]] | M2 | SETTLED (ADR-007 agreed by M1, M2, M3: PRs #43, #44) |
| E15 | When a failure does not reproduce in the starting order, FlakeTrace tries up to 31 distinct valid shuffled orders (classes never interleaved) and reports `NOT_REPRODUCED` honestly — counts, a Wilson upper bound, and "not proof of reliability" — instead of claiming the test is fine | Real runs (local, JDK 21): F4 found only through shuffle seed 1 (`VERIFIED`, 20/20); N3 `NOT_REPRODUCED` after 20 + 31 + 20 runs, bound 0.161. CI on JDK 8 (commit 0299e7b): runner job 144 tests OK. Budget 31 from Gruber et al. [12], a **Python** study — assumption for JUnit | [[evidence-m2]], [[03-Design/decisions/ADR-008-not-reproduced-and-order-search]] | M2 | SETTLED (ADR-008 agreed by M2, M3; CI green) |

## F. Team and process

| # | Claim | Backing | Source | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| F1 | Member 3's role passes the removal test | The POC's two invalidating defects were *harness* problems, not algorithm problems. Without M3: an algorithm and no trustworthy evidence it works | [[07-Defense/ownership-map]] | Joint | SETTLED |
| F2 | Scope grew by exactly one pillar when the team grew | Resource families, build system, language and certificate contract are unchanged from the two-member boundary | [[07-Defense/decisions/three-member-split]] | Joint | SETTLED |
| **F3** | **The three-member group is departmentally approved** | **NOT CONFIRMED.** Listed as decision 1 requiring supervisor input | [[07-Defense/weak-points]] | Joint | **OPEN** |
| F4 | AI tool usage is logged and acknowledged | Required by HEC guidance and the School guide. No component we claim as contribution is core-replacement | [[00-Meta/ai-usage-log]] | Joint | OPEN — *log must be current on the day* |

---

## How to use this in the room

1. **Never assert an `OPEN` or `ASSUMPTION` row as fact.** Say it is open, say when it closes, say who approves.
2. **Volunteer C12 and C15 before you are asked.** Self-disclosed limits buy credibility; discovered ones cost it.
3. **When challenged on a number, name the source, not the confidence.** "Rahman et al. measured that" beats "we're confident".
4. **For `POLICY` rows, say "that is our acceptance policy, frozen on [date], not a published finding."** Panels respect the distinction and punish blurring it.
