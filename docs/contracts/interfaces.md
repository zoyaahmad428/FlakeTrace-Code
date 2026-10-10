# Component interfaces — shared contract

*Status: `PROPOSED` 2026-10-09 — becomes `FROZEN` once all three members approve it in the
restructure PR. After that, changing it needs all three approvals (see CONTRIBUTING.md).*

This file says how the three members' code connects. The data shape of the final output is in
[report-schema.md](report-schema.md); this file covers the calls that produce it.

## The end-to-end flow for one diagnosis

```
 target project + victim test
          │
          ▼
 ┌─────────────────────────┐   ordered list of tests     ┌──────────────────────────┐
 │ M2  runner/             │ ──────────────────────────▶ │ one fresh JVM per order  │
 │ OrderRunner             │ ◀────────────────────────── │ JUnit 4 execution        │
 │ polluter search         │   per-test pass/fail +       └──────────────────────────┘
 │ minimiser · verifier    │   failure signature
 └──────────┬──────────────┘
            │ victim, polluters, reduced_sequence, raw run counts,
            │ failure_signature, source_integrity, execution_record_reference
            ▼
 ┌─────────────────────────┐   compiled classes of target   ┌───────────────────────────┐
 │ M1  evidence/           │ ◀───────────────────────────── │ javap bytecode, no source │
 │ resource extractor      │                                 │ changes                   │
 └──────────┬──────────────┘
            │ shared_resource, polluter_write_location, victim_read_location
            ▼
 ┌─────────────────────────┐
 │ M3  eval/               │  wilson_interval() → reproduction, victim_alone
 │ outcome.decide()        │  decide() → outcome, unresolved_reason
 │ schema_validator        │  validate_report() → the final JSON report
 └─────────────────────────┘
```

## Interface 1 — `OrderRunner` (implemented by M2, consumed by M2's search and M3's baseline)

Defined in `eval/baseline.py` (written by M3 before any runner existed — the runner must
satisfy it, not the other way round).

```python
class OrderRunner(Protocol):
    def run_ordered(self, order: List[TestIdentifier]) -> Dict[TestIdentifier, RunOutcome]: ...
```

| Rule | Why |
| --- | --- |
| All tests in `order` run **in one JVM, in exactly that order** | Shared static state only survives within one JVM; this is the phenomenon |
| Each call to `run_ordered` uses a **fresh JVM** | Calls must not pollute each other |
| Every test in `order` appears in the result | A missing entry is ambiguous; a crash must be reported as a failure |
| A failed test carries a `FailureSignature` (exception type + normalised stack trace) | `FailureSignature.matches()` ignores the message on purpose |
| The target project's source files are never written to | Source-integrity promise to the panel |

M3's `eval/tests/fake_runner.py` is the reference behaviour for tests. Production code never
imports it.

## Interface 2 — resource evidence (implemented by M1, consumed by M2 and M3)

**Input:** path to the target project's compiled classes (`target/classes`,
`target/test-classes`), the victim and the candidate polluters.

**Output:** for each polluter→victim pair, zero or more edges in the report-schema shapes
(illustrative values, copied from M3's hand-written `eval/examples/example_f1_verified.json`):

```json
{
  "shared_resource": {"kind": "static-field", "class": "odfixture.Config", "field": "mode"},
  "polluter_write_location": {"class": "odfixture.ConfigPolluterTest", "method": "pollute", "bytecode_offset": 3},
  "victim_read_location":   {"class": "odfixture.ConfigVictimTest", "method": "expectsDefaultMode", "bytecode_offset": 5}
}
```

Iteration 1 supports `static-field` and `system-property` kinds only. No edge found means
`null` in all three fields, which `decide()` turns into `UNRESOLVED(NO_SUPPORTED_RESOURCE_EVIDENCE)` —
it must never be reported as "no dependency exists".

**Implemented (M1, Phases 2–4):** Python 3 (standard library only), invoked as `python3 -m evidence.extract --classes <dir> --test-classes <dir> --polluter Class#method --victim Class#method [--depth N]`; JSON on stdout, exit codes 0/1/2 — full definition in [resource-evidence.md § Invocation](resource-evidence.md#invocation).

## Interface 3 — report assembly (M3)

M2 passes raw counts (successes, n for the reduced sequence and for the victim alone, plus any-
signature failures); M3's `eval.stats.wilson_interval` and `eval.outcome.decide` produce the
statistical fields and the verdict; `eval.schema_validator.validate_report` must accept the
assembled report before it is shown or saved.

## Open integration questions (decide before code is written against them)

| # | Question | Owner to propose | Status |
| --- | --- | --- | --- |
| I1 | Language for the runner: Java harness invoked from Python, or all-Java with a JSON boundary? | M2 | **Answered:** Python runner launching a small Java harness (`FtHarness`, JUnitCore) in one fresh JVM per order — [ADR-003](../03-Design/decisions/ADR-003-order-runner-junitcore-harness.md), agreed by M1, M2, M3 |
| I2 | Does M1's extractor run on the full suite once, or per candidate pair? | M1 | Open |
| I3 | Default `n` for repeated-run verification at Mid (20 suggested by the defence plan) | M2 + M3 | **Answered:** n = 20 (20/20 → Wilson lower bound 0.839, 19/20 → 0.764, both above 0.70) — [ADR-004](../03-Design/decisions/ADR-004-w7-diagnosis-runs.md), agreed by M1, M2, M3 |
| I4 | Where is the single CLI entry point (`flaketrace diagnose …`) and which language? | M2 | **Answered:** Python, `py -m runner diagnose` from the repository root; an installable `flaketrace` command is deferred — [ADR-005](../03-Design/decisions/ADR-005-w9-diagnose-cli.md), agreed by M1, M2, M3 |
