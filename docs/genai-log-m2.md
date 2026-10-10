# GenAI usage log — Member 2 (Search & Verification)

Format follows [[genai-log-m3]]: what was asked, what was retained, what I changed, how it was
verified, errors found, rejections.

## 2026-10-09 — Repository restructure and Mid Eval set-up

**Tool:** Claude Opus 5.5 (claude.ai, with repository access) · **Level:** L2

**What I asked:** Read the Mid Eval documents (rubric, protocol, worksheet, GenAI guide, GCR
announcement), the defence decision and both repositories; then merge the vault into the code
repo, write team rules for three members using AI agents, set up CI, and update the vault for
the post-defence and Mid Eval stage.

**What was retained:** single-repo layout with history preserved (`git subtree`), `CLAUDE.md`,
`CONTRIBUTING.md`, PR template, CODEOWNERS, `.github/workflows/ci.yml`,
`docs/contracts/interfaces.md`, `docs/08-MidEval/*`, `docs/09-Team/*`, ADR-001, folder READMEs.

**What I changed:** *fill after reviewing the PR with the team.*

**How it was verified:**
- Python CI steps run locally: 55 unit tests pass; `yield_report.py` runs on the real manifest.
- Workflow YAML parses; two jobs (`python-eval`, `fixture-build`).
- The `fixture-build` job could not run where Claude worked (Maven Central blocked); it
  first ran on GitHub Actions on PR #1 (run `37926797625`) and every step passed.

**Errors found:**
- `eval/README.md` documents `python3 -m unittest discover -s eval/tests`, which fails because
  `eval/tests` has no `__init__.py`. CI uses explicit module names instead. Reported to M3
  rather than edited, since `eval/` is M3's folder.
- Member numbers for Zoya and Zarpash were inferred, not stated — flagged for confirmation in
  `docs/09-Team/members.md`.

**Rejections:** Claude's question about moving the repo to a GitHub organisation was unclear;
deferred.

Ownership checkpoint: I must be able to explain the CI workflow line by line, the branch
protection rules, and the `OrderRunner` contract before the evaluation.

## 2026-10-09 — Commit protocol: members commit, agents hand over

**Tool:** Claude Opus 5.5 · **Level:** L2

**What I asked:** a hard rule that AI agents never commit or push; after each finished piece
of work the agent updates every affected doc and gives the member the exact commit commands
with a meaningful title and body.

**What was retained:** `CLAUDE.md` §3 (hard rule, when to hand over, message format) and new
§5 (which docs to update for which kind of change); matching sections in `CONTRIBUTING.md`,
`docs/09-Team/claude-guide.md` and the PR template.

**Why:** two problems found today — Zoya's PR #2 commits were authored as "Claude", and my
own restructure commits used an email not on my GitHub account, so neither was credited to
a member. A member running the commit after reading the diff is ownership evidence; an agent
commit is not.

**How it was verified:** read through the changed files; section numbers and cross-references
checked (`grep` for `§` in `CLAUDE.md`). No code changed, so no tests apply.

**What I changed:** *fill after review.*

**Note:** this change was handed to me as a patch to apply and commit myself — the first use
of the new rule.

## 2026-10-09 — W6 design: order runner (ADR-003) and implementation plan

**Tool:** Claude Opus 5.5 (Claude Code, local) · **Level:** L2

**What I asked:** propose at least two designs for `OrderRunner.run_ordered` (JUnit 4, one
fresh JVM per call, exact order), with trade-offs, classpath without new dependencies, and
portability on Windows/WSL/CI; stop for my choice; then write the plan.

**What was retained:** option A — Python `OrderRunner` + JUnitCore harness (ADR-003); the
implementation plan in `docs/superpowers/plans/2026-10-09-order-runner.md`.

**What I decided:** chose A over Maven Surefire (cannot honour a method-level order across
classes) and an all-Java runner (second language boundary with `eval/`).

**How it was verified:** a throwaway spike (not committed) compiled the harness against the
fixture's own classpath and ran F1 on my laptop (JDK 21): victim alone PASS; polluter then
victim FAIL `java.lang.AssertionError`; reversed order PASS.

**Errors found:** the ADR first said `javac --release 8`; the spike showed `-source 8 -target 8`
works on both JDK 8 and 21, so the ADR was corrected. Maven was not installed on my laptop —
installed 3.10.0 and added to user PATH.

**What I changed:** *fill after reviewing the ADR.*

## 2026-10-09 — W6 hand-over 1: harness + F1 proof

**Tool:** Claude Opus 5.5 (Claude Code, local) · **Level:** L2

**What I asked:** implement Task 1 of the W6 plan — the JUnitCore harness, the Python
`OrderRunner`, and tests that prove F1's victim passes alone and fails after its polluter in
one JVM.

**What was retained:** `runner/harness/FtHarness.java`, `runner/order_runner.py`,
`runner/tests/test_order_runner.py`, `docs/04-Implementation/sandbox-runner.md`.

**How it was verified:** test written first and seen failing (`ModuleNotFoundError`); then
`py -m unittest -v runner.tests.test_order_runner` → 8 tests OK; the F1 test was deliberately
broken (order reversed) and failed, then restored and passed. `git status --short fixtures/`
empty — fixture source untouched.

**Errors found:** Member 1 had merged their own ADR-002 first; ours was renumbered to ADR-003
and every reference updated. During the merge of `main`, a local merge commit kept conflict
markers in `genai-register.md`; fixed by taking the clean GitHub resolution.

**What I changed:** *fill after reading the diff.*

## 2026-10-09 — W6 hand-over 2: every test always reported

**Tool:** Claude Opus 5.5 (Claude Code, local) · **Level:** L2

**What I asked:** implement Task 2 of the W6 plan — a crash, timeout, skipped test, misspelt
test or duplicate must never make a test disappear from the result.

**What was retained:** the new `parse_results` (incomplete lines ignored, `SKIP` →
`flaketrace.NotExecuted`, missing tests filled in) and `run_ordered` (duplicate check, empty
order, timeout → `flaketrace.Timeout`, early exit → `flaketrace.JvmCrash`); 9 new tests; claims
ledger row E8.

**How it was verified:** the 9 tests were added first: 5 failed for the predicted reasons and
4 already passed because the harness handled them (recorded in [[evidence-m2]]). After the
change: `py -m unittest -v runner.tests.test_order_runner` → 17 tests OK.

**Errors found:** none in the code. Gap stated honestly: a real JVM crash and a real `@Ignore`
are only tested through hand-written result lines, because the fixture has no such test.

**What I changed:** *fill after reading the diff.*

## 2026-10-09 — W6 hand-over 3: runner tests in CI

**Tool:** Claude Opus 5.5 (Claude Code, local) · **Level:** L2

**What I asked:** add the runner's tests to CI on JDK 8 so they can never be skipped silently,
then record the real CI result and close W6.

**What was retained:** the `runner` job in `.github/workflows/ci.yml` with
`FLAKETRACE_REQUIRE_JVM=1`; the test command in `README.md` and `CLAUDE.md` section 8.

**How it was verified:** locally, with java/mvn hidden from PATH the tests skip without the
switch and fail with it. On GitHub Actions run `37957537495` (PR #10) all three jobs passed;
job `runner` on JDK 8: `Ran 17 tests in 16.911s — OK` (I copied this line from the job log,
which needs a signed-in account; Claude read the job/step status from the public API).

**Errors found:** none. Noted for Member 1: `evidence/tests/` is not yet run by CI.

**What I changed:** *fill after reading the diff.*

## 2026-10-09 — W6 final review and fixes

**Tool:** Claude Opus 5.5 (Claude Code) — a separate reviewer agent read the whole branch;
the session that wrote the code fixed the findings · **Level:** L2

**What was found:** no critical issues; important: (1) form-feed in a message misreported as a
JVM crash, (2) a cut-off result line could still be parsed, (3) tests ran in the caller's
directory, (4) docs overclaimed JDK-independent signatures. Five minor items deferred (listed
in [[evidence-m2]]).

**What was retained:** fixes for 1–3 with a failing test first for each; `ProbeTest.java` test
asset; reworded docs for 4.

**How it was verified:** 3 new tests failed before the fix, as predicted; 22 tests OK after.

**What I changed:** *fill after reading the diff.*

## 2026-10-09 — W7 design: ADR-004 and implementation plan

**Tool:** Claude Opus 5.5 (Claude Code, local) · **Level:** L2

**What I asked:** design W7 (victim-alone check, polluter search, repeated-run counts, source
hash, execution record) with options, then write the spec and plan.

**What I decided:** the original order is discovered like Surefire with an explicit-order
override; one-by-one polluter search with a priority hook (multi-polluter cases go to W10);
default n = 20 (proposed answer to I3, needs M3); small single-purpose modules with a
recording wrapper.

**What was retained:** ADR-004, `docs/superpowers/plans/2026-10-09-w7-diagnosis-runs.md`.

**How it was verified:** a throwaway spike (not committed) ran the full design on the
fixture: F1 and F2 found the ground-truth polluter, F3 ended NO_SINGLE_POLLUTER after 12
candidates, N1 and N2 ended VICTIM_FAILS_ALONE; 55 tests passed in the spike. Wilson bounds in
the ADR computed with `eval.stats.wilson_interval`.

**Errors found:** I first assumed N2 fails ~50% of the time; measured 18/60 on Windows
(`System.nanoTime()` has 100-ns steps there). The N2 test uses n = 40 so it cannot flake.

**What I changed:** *fill after reviewing the ADR.*

## 2026-10-09 — W7 Task 1: source-integrity check

**Tool:** Claude Opus 5.5 (Claude Code, local) · **Level:** L2

**What I asked:** implement Task 1 of the W7 plan — hash the project's files before and after
a diagnosis and name any difference.

**What was retained:** `runner/integrity.py`, `runner/tests/test_integrity.py` (code identical to
the plan, which was tested in the design spike).

**How it was verified:** tests run first and failed (`ModuleNotFoundError`); after the code,
`py -m unittest -v runner.tests.test_integrity` → 4 tests OK.

**Errors found:** none. Limitation noted: only the top-level `target/` is excluded (multi-module
projects).

**What I changed:** *fill after reading the diff.*

## 2026-10-09 — W7 Task 2: execution record

**Tool:** Claude Opus 5.5 (Claude Code, local) · **Level:** L2

**What I asked:** implement Task 2 — a wrapper that logs every JVM run to a JSON-lines file.

**What was retained:** `runner/recording.py`, `runner/tests/test_recording.py`, the
`.gitignore` entry.

**How it was verified:** tests failed first (`ModuleNotFoundError`); then 2 tests OK.

**Errors found:** none.

**What I changed:** *fill after reading the diff.*

## 2026-10-09 — W7 Task 3: discover the original order

**Tool:** Claude Opus 5.5 (Claude Code, local) · **Level:** L2

**What I asked:** implement Task 3 — list test classes like Surefire and ask JUnit for each
class's methods through a new `FtHarness --list` mode.

**What was retained:** the `--list` mode, `OrderRunner.list_methods`, `java_version`,
`runner/discovery.py`, `runner/tests/test_discovery.py`.

**How it was verified:** tests failed first (`ModuleNotFoundError`); then 28 tests OK (6 new +
22 W6 tests still passing). Printed the real fixture order (13 methods) into [[evidence-m2]].

**Errors found:** none; noted that JUnit's method order inside a class is neither source nor
alphabetical.

**What I changed:** *fill after reading the diff.*

## 2026-10-09 — W7 Task 4: reproduce, polluter search, repeat

**Tool:** Claude Opus 5.5 (Claude Code, local) · **Level:** L2

**What I asked:** implement Task 4 — reproduce the original failure, search for one polluter,
count repeated runs.

**What was retained:** `runner/search.py`, `runner/verify.py`, `runner/tests/test_search.py`.

**How it was verified:** tests failed first (`ModuleNotFoundError`); then 9 OK; mutation check
on the "a crash is never the reference" rule made its test fail, restored → OK.

**Errors found:** none.

**What I changed:** *fill after reading the diff.*

## 2026-10-09 — W7 Task 5: diagnose() end to end

**Tool:** Claude Opus 5.5 (Claude Code, local) · **Level:** L2

**What I asked:** implement Task 5 — `diagnose()` and its tests on all five fixture cases.

**What was retained:** `runner/diagnose.py`, `runner/tests/test_diagnose.py` (with the N2 test
rewritten), `docs/04-Implementation/diagnosis-runs.md`, ADR-004 updates.

**How it was verified:** tests failed first (`ModuleNotFoundError`); the first real run failed on
N2; after investigation 12 tests OK and the full runner suite 55 OK; every case's real numbers
recorded in [[evidence-m2]]; mutation check on the alone-stop.

**Errors found:** the plan's N2 test assumed N2 fails on Windows at ~30% (from the spike). It
then failed 0/80: `System.nanoTime()` was a multiple of 100 (10 MHz timer). The test assumption
was wrong, not the code; the test now checks that no polluter is blamed. Also found and
documented: a rarely-failing flaky victim can produce a spurious polluter (exposed by low
verify counts).

**What I changed:** *fill after reading the diff.*

## 2026-10-09 — W7 final review and fixes

**Tool:** Claude Opus 5.5 — separate reviewer agent on the whole branch; this session fixed
the findings · **Level:** L2

**What was found:** no critical issues; important: `NOT_REPRODUCED` counts disagreed with the
ADR; a record folder inside the project broke the integrity check; docs said CI was pending
after it had passed. Seven minor items deferred (listed in [[evidence-m2]]).

**What was retained:** a `record_dir` guard in `diagnose()` with a test that failed first; a
test pinning the crash-only `NOT_REPRODUCED` counts; ADR/README/note wording made to match the
code; CI run `37971869749` recorded.

**How it was verified:** the record-folder test failed before the guard and passed after; full
runner suite 57 OK.

**What I changed:** *fill after reading the diff.*

## 2026-10-10 — CI job for Member 1's evidence tests

**Tool:** Claude Opus 5.5 · **Level:** L2

**What was asked:** read the PRs merged since W7 (#12–#18) and the M1/M3 answers, then add the
`evidence` CI job Member 1 asked for, and tick ADR-001 and ADR-002.

**What was retained:** the job as Member 1 specified it (JDK 8, compile fixture and self-test,
`FLAKETRACE_REQUIRE_JVM=1`), plus pip caching as in `python-eval`.

**How it was verified:** the job's commands run locally: 27 OK, none skipped (22 skipped
before). With javap pointed at a missing file the run fails (4 failures, 4 errors), so the job
cannot pass by skipping. CI on JDK 8 not yet run.

**What was found while reading the merged PRs:** `eval/reports/README.md` says `diagnose()`
makes `execution_record_reference` absolute; it does not (`runner/diagnose.py:103` uses
`record_dir` as given; the integration script passes an absolute folder). `eval/report.py`
duplicates Member 1's `find_edges`/`report_fields`. Claim E1 as rewritten in PR #18 says Surefire
is used for compiling, which is wrong. Raised with the members, not edited (not M2's folders).

**What I changed:** *fill after reading the diff.*

## 2026-10-10 — N2 test back to `VICTIM_FAILS_ALONE`

**Tool:** Claude Opus 5.5 · **Level:** L2

**What was asked:** bring the N2 test and docs in line with Member 3's N2 fix (PR #14).

**What was retained:** the tightened N2 test; ADR-004, implementation note, demo plan and claim E9
wording.

**How it was verified:** three real N2 diagnoses first (all `VICTIM_FAILS_ALONE`); the new test
passed; a mutation of the alone rule made it fail (`POLLUTER_FOUND`); full runner suite 57 OK.

**What was wrong:** to undo the mutation the agent ran `git checkout -- runner/diagnose.py`,
which CLAUDE.md forbids agents to run. It discarded only the agent's own one-line edit; reported
to the member at the time.

**What I changed:** *fill after reading the diff.*

## 2026-10-10 — W9 CLI design (ADR-005)

**Tool:** Claude Opus 5.5 (brainstorming) · **Level:** L2

**What was asked:** design the W9 end-to-end command after Member 3 built report assembly
(PR #13, #21).

**Decisions made by Member 2:** one victim per run, for the demo and real use (A); no report and
exit 3 when `assemble_report` cannot build one (A); a Python module `py -m runner diagnose` now,
the installable `flaketrace` command deferred to a later iteration (M2 wants it).

**What was retained:** ADR-005 — flow, options, exit codes 0/1/2/3, tests, and the `runner` CI job
needing `eval/requirements.txt`.

**What was argued:** Member 2 questioned whether `py -m runner` is "production". Agreed that the
launch method is not, but behaviour is; a proper install needs a team-wide package rename and the
container decision, so it is recorded as deferred with its constraints.

**What I changed:** *fill after reading the diff.*

## 2026-10-10 — W9 Task 1: the diagnose command

**Tool:** Claude Opus 5.5 · **Level:** L2

**What was asked:** implement Task 1 of `docs/superpowers/plans/2026-10-10-w9-diagnose-cli.md`.

**What was retained:** `runner/cli.py`, `runner/__main__.py`, 11 fast tests, the `runner` CI job's
install step, as planned.

**How it was verified:** tests failed first (module missing), then 11 OK; mutation of the evidence
condition made the report tests fail; full runner suite 68 OK.

**What I changed:** *fill after reading the diff.*

## 2026-10-10 — W9 Task 2: real runs and docs

**Tool:** Claude Opus 5.5 · **Level:** L2

**What was asked:** Task 2 of the W9 plan — real fixture tests for the command, docs.

**What was retained:** 5 real-run tests; `runner/README.md` command section;
[[04-Implementation/diagnose-cli]]; README/CLAUDE.md command line; demo plan, iteration plan,
members, claim E12 (numbered E10 until merging main, where M1 had added E10 and E11).

**How it was verified:** 5 real runs OK; removing the evidence step made the F2 test fail; full
suite 73 OK; F1 run by hand.

**What was wrong:** a Python escape (`\2…` in a string) wrote a control character into the
README's sample paths; found by reading the file back, fixed, and every edited file scanned.

**What I changed:** *fill after reading the diff.*

## 2026-10-10 — W9 final review and fix

**Tool:** Claude Opus 5.5 (author session) + a separate reviewer agent · **Level:** L2

**What was found:** one important issue — broad `ValueError`/`RuntimeError` catching could hide
internal bugs as user errors; six minors deferred (listed in [[evidence-m2]]).

**What was retained:** `DiagnoseInputError` and `ToolError`; the CLI catches only those; a test
that failed first on behaviour; ADR-005 and notes updated.

**What was wrong:** another string-escape slip wrote a non-ASCII byte into a test; caught by the
import error and fixed with `bytes([0xFF])`.

**What I changed:** *fill after reading the diff.*

## 2026-10-10 — W9 review minors fixed

**Tool:** Claude Opus 5.5 · **Level:** L2

**What was asked:** Member 2 asked to fix every deferred review minor that could cause a problem later.

**What was retained:** records-is-a-file refused before Maven; victim checked before any record is
written; Java-name check on `--victim`; discovery timeout → exit 1; `summary()` guard; two summary
tests. Schema `ValidationError` left as a traceback on purpose (a pipeline bug), recorded in ADR-005.

**How it was verified:** each new test failed first (or, for the leftover-record check, failed when
the new check was removed); fast tests 25 OK; full runner suite 78 OK.

**What was wrong:** a `\n` escape in generated test code became a real line break (syntax error);
fixed by editing the file directly. An old stray form-feed character in this log (W6 entry) was
replaced with the text `\f`.

## 2026-10-10 — Claim E1 and a JUnit 3 test

**Tool:** Claude Opus 5.5 · **Level:** L2

**What was asked:** fix claim E1's wording (Member 1's suggestion) and back its JUnit 3 part with a
test through our own harness.

**What was retained:** `LegacyJUnit3Test.java`, two tests in `TestOrderRunnerOnProbes`, the E1 and
scope-boundary wording, the README limitation line.

**How it was verified:** a scratchpad probe first; the tests passed (existing behaviour); a reversed
order made the pollution test fail; full runner suite 59 OK.

**What I changed:** *fill after reading the diff.*

## 2026-10-10 — W10 design (ADR-007)

**Tool:** Claude Opus 5.5 (brainstorming) · **Level:** L2

**What was asked:** design W10 (deletion minimisation, F3's two polluters).

**Decisions made by Member 2** (asking each time for what is best for the product as a whole):
produce a real F3 report with the agreed "first edge shown, rest in limitations" rule (A); `ddmin`
over bisection and one-at-a-time deletion; reuse `POLLUTER_FOUND` for several polluters; require
evidence for every polluter before `VERIFIED`.

**What was retained:** ADR-007 — flow, `ddmin` rules, evidence rule, limitations (single-run
checks, no budget, 1-minimal only), verification plan.

**What I changed:** *fill after reading the diff.*

## 2026-10-10 — W10 Task 1: `ddmin`

**Tool:** Claude Opus 5.5 · **Level:** L2

**What was asked:** Task 1 of `docs/superpowers/plans/2026-10-10-w10-ddmin.md`.

**What was retained:** `runner/minimise.py` and 11 fake-runner tests, as planned.

**How it was verified:** tests failed first (module missing), then 11 OK; removing the complement
step made 7 fail; full runner suite 91 OK.

**What was wrong:** the brainstorming estimate of 10–15 runs for F3's shape was low; the real count
on the fake is 25 (recorded, not the guess).

**What I changed:** *fill after reading the diff.*

## 2026-10-10 — W10 Task 2: minimise in `run_steps`

**Tool:** Claude Opus 5.5 · **Level:** L2

**What was asked:** Task 2 of the W10 plan.

**What was retained:** step 4 in `run_steps`, `minimise_runs`, the `"minimise"` record step, three
`run_steps` tests, the real F3 test, docs (README status table, diagnosis-runs note).

**How it was verified:** tests failed first on behaviour; real F3 found exactly the ground-truth
polluters (9 minimise runs); full suite 93 OK.

**What was wrong:** the plan updated the CLI's F3 test only in Task 3, so Task 2 broke it; caught by
predicting the full-suite result, fixed in Task 2 (ruling in the ledger).

**What I changed:** *fill after reading the diff.*

## 2026-10-10 — W10 Task 3: several polluters in the report

**Tool:** Claude Opus 5.5 · **Level:** L2

**What was asked:** Task 3 of the W10 plan.

**What was retained:** `combine_fields`, per-polluter evidence in `resource_fields`, four combining
tests, the F3 report checks, docs and claim E14 (first numbered E13).

**How it was verified:** tests failed first; the real F3 command is `VERIFIED` with `flagB` in
`limitations`; evidence for the first polluter only made the F3 test fail; full suite 97 OK.

**What I changed:** *fill after reading the diff.*

## 2026-10-10 — W10 final review and fixes

**Tool:** Claude Opus 5.5 (author session) + a separate reviewer agent · **Level:** L2

**What was found:** important: a one-off flaky failure blamed every earlier test; a resource written
by both polluters was called "not shown"; mixed-evidence wording conflicts with M3's generic line.
Minors: a resource named twice, a cost claim stronger than measured, E14 (then E13) marked SETTLED too early,
a missing one-test-prefix test, `minimise_runs` not in the report, an incomplete exit-3 message.

**What was retained:** re-check of the full order before `ddmin`; `combine_fields` de-duplication;
four tests that failed first; ADR-007, E14 and the note corrected; the exit-3 message rewritten.

**What was rejected:** changing M3's generic limitation line (eval/ is M3's) — raised with M3 instead.

**What was wrong (session):** one long shell command with a quote in its text failed to parse; nothing
was applied, checked with grep, redone from a script file.

**What I changed:** *fill after reading the diff.*

## 2026-10-10 — W10: `analyse_pair` per polluter

**Tool:** Claude Opus 5.5 · **Level:** L2

**What was asked:** analyse Member 1's and Member 3's messages and new PRs (#29–#38) for what is best
for the product, then switch the command to `analyse_pair` (ADR-006 follow-up).

**What was retained:** `analyse_pair` once per polluter; the depth note on named edges; the
`any_edge_found` flag for M3's PR #38; three tests that failed first; F3 offsets checked with `javap`.

**What was rejected:** Member 1's suggested one-line swap as written: it predates W10's several
polluters and would have let a deep edge on a second polluter go unmarked in the report.

**What I changed:** *fill after reading the diff.*

## 2026-10-10 — W10 follow-up: minimisation in the summary

**Tool:** Claude Opus 5.5 · **Level:** L2

**What was asked:** fix the deferred review minor (`minimise_runs` not shown), if it helps the product.

**What was retained:** one summary line when `ddmin` found the polluters, stating the shrink and
"1-minimal, not necessarily the minimum"; two tests that failed first; the F3 test checks it.

**What was rejected:** a new report field — the schema is Member 3's contract and the number does not
change the verdict.

## 2026-10-10 — Panel action A7: commit and OS in the execution record

**Tool:** Claude Opus 5.5 · **Level:** L2

**What was asked:** make panel action A7 true before marking it complete.

**What was retained:** `environment(project)` and its use in the record header; two tests plus the F1
header check, all failing first; two mutation checks.

**What was rejected:** recording a dummy seed or container — neither exists, so the docs say so.

**What I changed:** *fill after reading the diff.*

## 2026-10-10 — Panel actions A1, A3, A4, A7 marked complete

**Tool:** Claude Opus 5.5 · **Level:** L2

**What was asked:** update the panel action register for Member 2's actions now that W7–W10 and the
A7 record change are done.

**What was retained:** A1, A3, A4 (M2's part; M1's was done) and A7 set to COMPLETE, each with evidence
links to merged PRs and recorded runs in [[evidence-m2]]; the summary rows updated. A5 (Member 3) and
A6 (Member 1) left open — not ours to close.

**How it was verified:** every cited test, file and PR checked to exist; A7 marked complete only after
the commit and OS were really recorded (previous commit).

**What I changed:** *fill after reading the diff.*

## 2026-10-10 — ADR-008 design (NOT_REPRODUCED and order search)

**Tool:** Claude Opus 5.5 (brainstorming) · **Level:** L2

**What was asked:** a research-based design for failures that do not reproduce, "not because it is
simple".

**Decisions made by Member 2:** accept the real failing order (`--order`) plus valid shuffled orders as
fallback (C); 31 shuffles (Gruber et al.) over 10 or 20; one diagnosis flow over a separate command or
reusing the evaluation baseline.

**What was retained:** ADR-008 — flow, class-first shuffling, distinct-order counting, the schema
proposal for Member 3, fixture requests F4/N3, order of work.

**What was found while checking:** reference [12] (the 31-order figure) studies Python projects; the
ADR states its transfer to JUnit as an assumption instead of a finding.

**What I changed:** *fill after reading the diff.*

## 2026-10-10 — Record agreed ADRs (I1, I3, I4, E14, ADR-007 wording)

**Tool:** Claude Opus 5.5 · **Level:** L1

**What was asked:** record what M1's and M3's ticks (PRs #43, #44) settled.

**What was retained:** `docs/contracts/interfaces.md` I1, I3, I4 marked answered with links to ADR-003,
-004, -005 (each agreed by all three); claim E14 SETTLED; ADR-007's evidence sentence corrected to
`analyse_pair` (stale text found by Member 1). I2 left to Member 1.

**How it was verified:** every ADR's agreement table read on `main`; the quoted Wilson bounds recomputed
(20/20 → 0.839, 19/20 → 0.764); the ADR links resolve.

**What I changed:** *fill after reading the diff.*

## 2026-10-11 — Runner tests independent of the fixture's size

**Tool:** Claude Opus 5.5 · **Level:** L2

**What was asked:** fix our tests so Member 3's new fixture cases (F4, N3) do not break CI.

**What was retained:** three real-run tests now derive their counts from the real order or the fixture
sources; the failures reproduced first on M3's branch; full suite green on both fixtures.

**What was wrong:** (1) the first rewrite of the discovery test reused the include rule under test, so a
mutation failed only on an empty set — rewritten to read the sources independently. (2) The agent ran a
stray `git checkout --` with no path (forbidden for agents by CLAUDE.md; it changed nothing, the listed
modified files proved the edits were intact). (3) Restoring `runner/discovery.py` after a mutation wrote
LF endings; content was identical (empty diff) and the CRLF endings were put back.

**What I changed:** *fill after reading the diff.*

## 2026-10-11 — ADR-008 Task 1: shuffled orders

**Tool:** Claude Opus 5.5 · **Level:** L2

**What was asked:** Task 1 of `docs/superpowers/plans/2026-10-11-adr-008-runner-side.md`.

**What was retained:** `runner/orders.py` and 9 tests as planned.

**What was wrong:** one planned test sorted `TestIdentifier` tuples (a `TypeError`); fixed to a set
comparison with the same meaning (ruling in the plan ledger).

**How it was verified:** tests failed first; flat shuffling made the class-grouping test fail; full suite
117 OK.

**What I changed:** *fill after reading the diff.*

## 2026-10-11 — ADR-008 Task 2: diagnosis tries shuffled orders

**Tool:** Claude Opus 5.5 · **Level:** L2

**What was asked:** Task 2 of the ADR-008 runner-side plan.

**What was retained:** the shuffle phase, the always-run alone check, the six fields Member 3's report
code reads, given-order validation, seeds in the execution record; 10 tests that failed first; real F4
and N3 runs.

**How it was verified:** two mutation checks failed the right tests; full suite 127 OK.

**What I changed:** *fill after reading the diff.*

## 2026-10-11 — ADR-008 Task 3: command options and F4/N3 reports

**Tool:** Claude Opus 5.5 · **Level:** L2

**What was asked:** Task 3 of the ADR-008 runner-side plan.

**What was retained:** `read_order`, `--order/--shuffles/--seed`, the summary lines, 11 tests (incl.
real F4 and N3 through the command); docs, demo plan step 6b, W14, claim E15 (OPEN until CI).

**What was wrong:** (1) the summary said "given order" when the order was discovered — caught by
reading the real N3 output, fixed test-first; (2) a generated test contained a real BOM character
instead of the `\ufeff` escape — replaced with the visible escape.

**What I changed:** *fill after reading the diff.*
