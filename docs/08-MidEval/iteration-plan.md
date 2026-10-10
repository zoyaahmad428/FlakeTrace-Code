# Iteration 1 — plan to the Mid Evaluation

**Iteration objective (due at Mid):** on the seeded fixture, with no application logs,
FlakeTrace shows the victim passing alone, failing after its polluter, the order minimised,
the shared resource named from bytecode, the failure reproduced N times with a confidence
interval, and the source verified unchanged. A negative control is correctly reported
`UNRESOLVED`. *(This is the "before the supervisory mid-evaluation" milestone of the
post-defence plan, §13.)*

> ⚠ **Set the date.** The meeting is 12–16 October. Submission is **48 h before**. If the
> meeting is 12 or 13 October, submission is **10–11 October** — use the *emergency cut*
> below.

## Work packages

| WP | Work | Owner | Planned | State (2026-10-09) | Evidence |
| --- | --- | --- | --- | --- | --- |
| W1 | Seeded fixture F1–F3, N1–N2 with pre-registered ground truth | M3 | Oct 8 | **Complete** | `fixtures/od-fixture`, `docs/evidence-m3.md` Phase 1 |
| W2 | Wilson interval, isolation comparison | M3 | Oct 8 | **Complete** | `eval/stats.py`, verified vs statsmodels |
| W3 | Report schema + outcome decision table | M3 | Oct 8 | **Complete** | `eval/outcome.py`, schema, 7 examples |
| W4 | Random-order baseline (interface) + benchmark manifest + yield report | M3 | Oct 9 | **Complete (no real runs)** | `eval/baseline.py`, `eval/benchmark/` |
| W5 | Single repo, CI, team rules, Mid Eval docs | M2 | Oct 9 | **In review** (this PR) | `.github/`, `CLAUDE.md`, `docs/08-MidEval/` |
| W6 | `OrderRunner`: ordered single-JVM JUnit 4 runner + failure signatures | M2 | S−2 | **Complete** (PR #10 in review): F1 victim passes alone, fails after polluter in one JVM; every test always reported; CI job green on JDK 8 (17 tests) | `runner/order_runner.py`, [[evidence-m2]], [[03-Design/decisions/ADR-003-order-runner-junitcore-harness]] |
| W7 | Victim-alone check, polluter search, repeated-run counts, source hash, execution record | M2 | S−1 | **Complete** (PR #11 in review): F1/F2 polluter found, F3 → W10, N1 fails alone; 57 runner tests pass locally, CI green on JDK 8 | `runner/diagnose.py`, [[evidence-m2]], [[03-Design/decisions/ADR-004-w7-diagnosis-runs]] |
| W8 | Static extraction: static fields + system properties, attributed to test methods | M1 | S−1 | **Complete**: lifecycle attribution, call depth 1–5 with pair-mode auto-deepening (ADR-006, accepted by all three), polluter→victim edges; fixture matches `ground_truth.json` exactly (156 pairs); fastjson FJ-01/FJ-02 edges at `depth_used` 4/5; 39 tests green on JDK 8 in CI (PR #34) | `evidence/extract.py`, `docs/evidence-m1.md` |
| W9 | End-to-end CLI: F1 → validated JSON report | M2 + M3 | S−1 | **Complete for all 5 fixture cases, plus 2 new ones.** Real `runner.diagnose()` + M1's `find_edges`/`report_fields`/`analyse_pair` assembled by `eval.report.assemble_report()`, schema-validated, via both `eval/tools/run_w9_integration.py` (library) and `py -m runner diagnose` (ADR-005). F1/F2 → `VERIFIED`; N1/N2 → `UNRESOLVED(VICTIM_FAILS_ALONE)`; **F3 → `VERIFIED`** since W10 landed (row below). ADR-008 (2026-10-11) added real `NOT_REPRODUCED` handling (nullable `failure_signature`, new `INFRASTRUCTURE_FAILURE` reason, `order_exploration` optional field) plus two new fixture cases, **F4** (needs a shuffled order to reproduce — confirmed by hand, pending Member 2's order-search landing) and **N3** (confirmed `NOT_REPRODUCED`; full report pending Member 2's `diagnose()` always running the alone check). `NO_SINGLE_POLLUTER` is the only status still deliberately unhandled — see [[evidence-m3]]. | `eval/report.py`, `eval/reports/`, [[evidence-m3]], `runner/cli.py`, [[03-Design/decisions/ADR-008-not-reproduced-and-order-search]] |
| W10 | Deletion minimisation incl. F3 two-polluter case | M2 | S | **Complete** (PR #35/#38/#40, merged): `ddmin` when no single polluter; real F3 → `POLLUTER_FOUND` with the ground-truth polluters (`setFlagA`+`setFlagB`), command → `VERIFIED` 20/20, 0/20 alone | `runner/minimise.py`, [[03-Design/decisions/ADR-007-w10-ddmin-minimisation]], [[evidence-m2]] |
| W14 | ADR-008 runner side: `--order`, class-first shuffled orders, alone check always, `NOT_REPRODUCED` reports | M2 (+ M3's schema/fixtures, PR #45) | After S | **Complete** (PR pending): real F4 `VERIFIED` via shuffle seed 1; real N3 `NOT_REPRODUCED` report after 31 shuffles | `runner/orders.py`, [[03-Design/decisions/ADR-008-not-reproduced-and-order-search]], [[evidence-m2]] |
| W11 | Mid report (template) | All, chapter owners in [[08-MidEval/README]] | S | **In progress (M3):** chapters 4, 7, 8 drafted and sent to the member; not yet confirmed incorporated into the actual submission, and due for a refresh (drafted before F3/W10 and ADR-008 landed) | — |
| W12 | Worksheet, GenAI register, tag `mid-eval-v1` | M2 (tag), all | S | Not started | — |
| W13 | Deck + rehearsal on demo laptop | All | Meeting −1 | Not started | — |

*S = submission day (meeting − 48 h).*

## Day plan (fill dates once the meeting is confirmed)

| Day | M1 | M2 | M3 |
| --- | --- | --- | --- |
| Fri 9 Oct | Review + approve restructure PR; agree ADR-001 | Merge restructure; start W6 | Review restructure PR; start report ch. 4 & 7 |
| S−2 | W8 static fields on F1 | W6 done, PR | Report ch. 4, 7; adapt baseline to real runner |
| S−1 | W8 system properties (F2), PR | W7 + W9, PR | Run all 5 fixture cases, record yield report |
| S | Report ch. 1–2, 5 (data/behaviour) | W10 (if time) · report ch. 5–6 · tag | Report ch. 7–8 · worksheet assembly |
| Meeting −1 | Rehearse own 4-min defence | Rehearse demo on laptop | Rehearse own 4-min defence |

## Emergency cut (if submission is within 2 days)

Demo = W6 + W7 + W8 on **F1 and N1 only**, report via `decide()`. F2/F3 and minimisation
(W10) are stated honestly as *in progress* with a recovery date. The rubric rewards a working
core with an honest boundary over a broad, fragile one.

## Variance and recovery

| Variance | Cause | Recovery action | Owner | Revised date |
| --- | --- | --- | --- | --- |
| Runner (W6) not started at 9 Oct | Repo and team process set-up first; post-defence decisions | Runner is the critical path — M2 works on nothing else until W6 lands | M2 | S−2 |
| *add as they occur* | | | | |

## Next iteration outcome (FYP-1 Final)

Working primary scenario end-to-end on all fixtures and at least one real project from the
benchmark manifest; random-order baseline measured with the real runner; first deployment
attempt (container).
