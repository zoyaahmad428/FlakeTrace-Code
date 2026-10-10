# Diagnosis report schema — shared contract

This is a **shared contract**. The schema lives at
[eval/schema/report.schema.json](../../eval/schema/report.schema.json) and the
decision logic that produces `outcome`/`unresolved_reason` lives at
[eval/outcome.py](../../eval/outcome.py). Changing any field here, or the
decision table, needs agreement from all three members — downstream
consumers (the UI, the benchmark/yield report in Phase 5) depend on this
shape staying stable.

Validate any report against the schema with
[eval/schema_validator.py](../../eval/schema_validator.py)
(`validate_report(dict)` / `validate_report_file(path)`), which uses the
`jsonschema` package so the validator can never drift from the schema
document itself.

## Fields

| Field | Type | Produced by | Meaning |
| --- | --- | --- | --- |
| `victim` | `{class, method}` | Member 2 (Search & Verification) | The test being diagnosed. |
| `polluters` | `{class, method}[]` | Member 2 | The test(s) identified as responsible. Empty array if none implicated (e.g. the victim fails alone). |
| `original_failing_order` | `{class, method}[]` | Member 2 | The full order in which the failure was first observed (e.g. the declared/CI order), before minimisation. |
| `reduced_sequence` | `{class, method}[]` | Member 2 (sequence minimiser) | The minimised ordered list of tests (polluter(s) + victim) that still reproduces the failure. |
| `reproduction` | `{successes, n, confidence, lower, upper}` | Member 3 (from Member 2's raw run counts, via `eval.stats.wilson_interval`) | How often `reduced_sequence` reproduced the victim's *reference failure signature* out of `n` runs, with its Wilson score interval. |
| `sequence_any_signature_failures` | integer | Member 3 (from Member 2's raw run counts) | Count of `reduced_sequence` runs that failed for **any** reason, not necessarily matching the reference signature. Always ≥ `reproduction.successes`. Exists to distinguish `NOT_REPRODUCED` (this is 0) from `SIGNATURE_MISMATCH` (this is >0 while `reproduction.successes` is 0) — see decision table below. |
| `victim_alone` | `{successes, n, confidence, lower, upper}` | Member 3 (from Member 2's isolation-check raw counts) | How often the victim reproduced its reference failure signature when run **alone**, with its Wilson score interval. Any nonzero count here means the failure cannot be attributed to a polluter. |
| `shared_resource` | `{kind, class, field}` or `{kind, key}` or `null` | Member 1 (Resource Evidence) | The static field or system property both the polluter and the victim touch. `null` if no resource edge was found. |
| `polluter_write_location` | `{class, method, bytecode_offset}` or `null` | Member 1 | Where the polluter writes the shared resource. `null` if no resource edge was found. Iteration 1 limitation: this field is singular, so a multi-polluter case (e.g. the fixture's F3, where two separate tests must each write before the victim fails) can only show one write location — see `eval/examples/README.md`. |
| `victim_read_location` | `{class, method, bytecode_offset}` or `null` | Member 1 | Where the victim reads the shared resource. `null` if no resource edge was found. |
| `failure_signature` | `{exception_type, message, stack_trace}` or `null` | Member 2 | The reference failure signature that `reproduction`/`victim_alone` are measured against. `null` only when `unresolved_reason` is `NOT_REPRODUCED` or `INFRASTRUCTURE_FAILURE` (ADR-008, 2026-10-10) — a failure that never produced a real reference exception has none to report. |
| `order_exploration` | `{order_given, shuffled_orders_tried, orders_exhausted, seed_base, reproducing_seed}`, optional | Member 2 | ADR-008: how many orders beyond the given/discovered one were tried, and which (if any) reproduced. Omitted entirely until Member 2's `diagnose()` tracks it (not yet landed) — every existing report without it stays valid. |
| `instrumentation_level` | `"static-only"` (fixed) | Member 1 / Member 3 (contract constant) | Always `"static-only"` in Iteration 1. Runtime instrumentation is Iteration 2 and is not built yet. |
| `execution_record_reference` | string | Member 2 | Pointer to Member 2's recorded execution log / run id backing this report, for traceability. |
| `source_integrity` | `{passed, details}` | Member 2 (source-integrity check) | Whether Member 2's check confirmed the instrumented bytecode matches the analyzed source. If `passed` is `false`, the outcome is always `UNRESOLVED(SOURCE_INTEGRITY_FAILED)` regardless of every other field — see decision table. |
| `outcome` | `VERIFIED` \| `CANDIDATE` \| `UNRESOLVED` | Member 3 (Evaluation), via `eval.outcome.decide()` | The final verdict. |
| `unresolved_reason` | enum or `null` | Member 3, via `eval.outcome.decide()` | Required (non-null) when `outcome` is `UNRESOLVED`; must be `null` otherwise. |
| `limitations` | string[] | Member 3 | Free-text caveats about this specific diagnosis (e.g. "illustrative example", "schema can't represent two polluter-write locations"). |

## Outcome enum

- **`VERIFIED`** — strong, trustworthy evidence of order-dependence.
- **`CANDIDATE`** — real signal, not yet strong enough to verify.
- **`UNRESOLVED`** — no order-dependence verdict can be made; see `unresolved_reason`.

**Ranking alone must never produce `VERIFIED`** — a resource edge
(`shared_resource` / `polluter_write_location` / `victim_read_location` all
non-null) is always required alongside the statistics.

## Unresolved-reason enum

| Reason | Meaning |
| --- | --- |
| `VICTIM_FAILS_ALONE` | The victim reproduced its reference signature at least once when run alone. |
| `NOT_REPRODUCED` | The reduced sequence never failed at all. |
| `INFRASTRUCTURE_FAILURE` | ADR-008 (2026-10-10). The reduced sequence failed sometimes, but every failure was a crash or timeout, never a real exception — a tooling problem, not evidence of a different bug. Distinct from `SIGNATURE_MISMATCH`, which means at least one failure was real but unmatched. |
| `SIGNATURE_MISMATCH` | The reduced sequence failed sometimes, but never with the reference signature (and at least one such failure was a real, different exception, not only crashes/timeouts). |
| `NO_SUPPORTED_RESOURCE_EVIDENCE` | The sequence reproduces the failure, but no polluter-write/victim-read resource edge was found. |
| `BELOW_CONFIDENCE_THRESHOLD` | Reserved in the schema per the brief's "at least" requirement. **Not currently emitted** — see below. |
| `SOURCE_INTEGRITY_FAILED` | Added in Phase 3 (not in the brief's original list). The source-integrity check failed, so no other evidence can be trusted. |

## Decision table

Implemented in [eval/outcome.py](../../eval/outcome.py) (`decide()`), evaluated
top to bottom, first match wins. Confirmed with Member 3 on 2026-10-08:

1. `source_integrity.passed` is `false` → `UNRESOLVED(SOURCE_INTEGRITY_FAILED)`
2. `victim_alone.successes >= 1` → `UNRESOLVED(VICTIM_FAILS_ALONE)`
3. `reproduction.successes == 0`:
   - and `sequence_any_signature_failures == 0` → `UNRESOLVED(NOT_REPRODUCED)`
   - and every failure was a crash/timeout (ADR-008's `infrastructure_failures ==
     sequence_any_signature_failures > 0`) → `UNRESOLVED(INFRASTRUCTURE_FAILURE)`
   - and at least one failure was a real, different exception → `UNRESOLVED(SIGNATURE_MISMATCH)`
4. `reproduction.successes >= 1`:
   - no resource edge → `UNRESOLVED(NO_SUPPORTED_RESOURCE_EVIDENCE)`
   - resource edge exists, Wilson lower bound ≥ 0.70 → `VERIFIED`
   - resource edge exists, Wilson lower bound < 0.70 → `CANDIDATE`

### Decisions made explicitly with Member 3 (2026-10-08)

The brief left these open; resolved as follows, recorded here since this is
a shared contract other members and future phases will read against:

- **CANDIDATE vs. `UNRESOLVED(BELOW_CONFIDENCE_THRESHOLD)`** for "reproduces
  but below the 0.70 lower bound": uses **`CANDIDATE`**. This gives
  `CANDIDATE` a reachable meaning (real signal, not yet strong enough) and
  keeps `BELOW_CONFIDENCE_THRESHOLD` reserved in the enum for forward
  compatibility only.
- **Signature matching**: a reproduction "success" requires the **same**
  failure signature as the original failing order. A sequence that fails but
  never matches is `SIGNATURE_MISMATCH`, distinct from `NOT_REPRODUCED`
  (which means it mostly just passed).
- **Rep count `n`**: the decision function is **generic over `n`** — it
  checks the Wilson lower bound regardless of how many reps were actually
  run. The brief's "`n=20`" was its illustrative example, not a fixed
  protocol requirement.
- **Source integrity**: added as a **new override gate** at the top of the
  table (`SOURCE_INTEGRITY_FAILED`), since none of the brief's five reasons
  fit "the instrumentation may have altered behavior."

## Examples

Hand-written illustrative examples for every row of the decision table live
under [eval/examples/](../../eval/examples/), labelled as examples, not
results — see that folder's README. They are validated against this schema
and cross-checked against `eval.outcome.decide()` in
[eval/tests/test_examples.py](../../eval/tests/test_examples.py).
