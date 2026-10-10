"""W9 report assembly (Interface 3, docs/contracts/interfaces.md).

Turns Member 2's raw diagnosis counts (runner.diagnose.DiagnosisRuns) and Member 1's
pair-mode resource-edge data (evidence.extract.find_edges + report_fields, Output 2 of
docs/contracts/resource-evidence.md) into one schema-validated diagnosis report.

Which shared resource goes in the report is decided once, by Member 1's find_edges/
report_fields -- this module does not re-derive it. An earlier version of this file had its
own correlation function (find_resource_edge); it duplicated that logic, dropped M1's
FIXED_LIMITATIONS, and callers were passing --depth 1, which cannot find a resource accessed
through a one-level helper call (e.g. F2's FeatureVictimTest reads the property inside
FeatureFlags.isTurboEnabled(), not in the test method itself) -- flagged by Member 2, see
docs/evidence-m3.md.

With several polluters (W10, ADR-007), a caller's `resource_fields` can have
`shared_resource=None` (because not every polluter has an edge, so none is shown as the primary
resource) while still naming, in `limitations`, which polluters DID have an edge. Appending this
module's own generic "No polluter-write/victim-read resource edge was found by static analysis"
on top of that would contradict it. `resource_fields` may therefore carry an optional
`any_edge_found: bool` key (absent for the ordinary single-polluter case, e.g. M1's
`report_fields()` output): when present, it -- not `shared_resource is not None` -- decides
whether the generic line is added. Flagged by Member 2 against PR #35 (W10); see
docs/evidence-m3.md.

Three of runner.diagnose's four DiagnosisRuns.status values are wired end to end here:
POLLUTER_FOUND, VICTIM_FAILS_ALONE and (ADR-008, 2026-10-10) NOT_REPRODUCED. NO_SINGLE_POLLUTER
is still NOT handled -- see UnhandledStatus: it has no corresponding value in the schema's
unresolved_reason enum, and is a genuinely rarer case post-W10 (M2's ddmin minimisation now
resolves most cases that used to land here; NO_SINGLE_POLLUTER remains only for an empty
prefix, i.e. the victim is first in the order). An open question for the team, not silently
invented.

NOT_REPRODUCED needed two real things before it could be handled, both resolved by ADR-008:
(1) runner.diagnose always sets reference_signature=None and alone_n=0 for this status (it
short-circuits before running the isolation check), which eval.outcome.DecisionInput used to
reject outright (`isolation_n > 0`); and (2) the schema required a real failure_signature,
which a failure that never reproduced does not have. Both are fixed by Member 2's diagnose()
always running the alone check (so isolation_n > 0 once that change lands) and by this
module building `failure_signature: null` whenever `diagnosis.reference_signature is None` --
which is also exactly when `decide()` can land on the new INFRASTRUCTURE_FAILURE reason (same
underlying DiagnosisRuns.status, same None reference), so both reasons share this handling.
Tested here with hand-built DiagnosisRuns objects (this project's established convention for
code whose real dependency hasn't landed yet) ahead of Member 2's diagnose() change.

Until that diagnose() change actually lands, a REAL NOT_REPRODUCED diagnosis still has
alone_n == 0 today -- assemble_report raises UnhandledStatus for that specific case (status
NOT_REPRODUCED and alone_n == 0), not the bare ValueError DecisionInput would otherwise raise,
so either merge order (M2's diagnose() change landing before or after this module's) leaves
the CLI's "exit 3, no report yet" behaviour intact rather than an uncaught traceback. Flagged
by Member 2 while reviewing this branch; see docs/evidence-m3.md.
"""

from typing import Optional

from eval.outcome import DecisionInput, decide
from eval.schema_validator import validate_report
from runner.diagnose import DiagnosisRuns, NOT_REPRODUCED, POLLUTER_FOUND, VICTIM_FAILS_ALONE

_ORDER_EXPLORATION_FIELDS = (
    "order_given", "shuffled_orders", "orders_exhausted", "shuffle_seed_base", "reproducing_seed",
)


class UnhandledStatus(Exception):
    """Raised for a DiagnosisRuns.status this module does not yet turn into a report."""


def _order_exploration(diagnosis: DiagnosisRuns) -> Optional[dict]:
    """ADR-008's optional order_exploration report field, built only once Member 2's
    diagnose() actually tracks it (DiagnosisRuns gaining all five fields below). Until then
    this returns None and the key is omitted entirely -- the schema allows that."""
    if not all(hasattr(diagnosis, f) for f in _ORDER_EXPLORATION_FIELDS):
        return None
    return {
        "order_given": diagnosis.order_given,
        "shuffled_orders_tried": diagnosis.shuffled_orders,
        "orders_exhausted": diagnosis.orders_exhausted,
        "seed_base": diagnosis.shuffle_seed_base,
        "reproducing_seed": diagnosis.reproducing_seed,
    }


def assemble_report(
    diagnosis: DiagnosisRuns,
    resource_fields: Optional[dict] = None,
    confidence: float = 0.95,
) -> dict:
    """Build and validate one diagnosis report from a DiagnosisRuns and (for POLLUTER_FOUND)
    `resource_fields` -- the output of evidence.extract.report_fields(pair) (one polluter) or a
    caller's own combination of several such results (W10, several polluters; see module
    docstring for the optional `any_edge_found` key that case can set).
    Raises UnhandledStatus for any status other than POLLUTER_FOUND, VICTIM_FAILS_ALONE or
    NOT_REPRODUCED -- see module docstring."""
    if diagnosis.status not in (POLLUTER_FOUND, VICTIM_FAILS_ALONE, NOT_REPRODUCED):
        raise UnhandledStatus(
            f"assemble_report does not yet handle DiagnosisRuns.status={diagnosis.status!r}; "
            "see eval/report.py's module docstring"
        )
    if diagnosis.status == NOT_REPRODUCED and diagnosis.alone_n == 0:
        # Safe for either merge order (flagged by Member 2): today's real runner.diagnose()
        # still short-circuits before running the alone check for NOT_REPRODUCED, so alone_n
        # is 0 until ADR-008 step 4 lands. Without this guard, DecisionInput's isolation_n > 0
        # check raises a bare ValueError here, which the CLI does not catch (ADR-005 keeps
        # unexpected bugs loud) -- so the command would crash with a traceback instead of its
        # designed "exit 3, no report yet" UX. Raising UnhandledStatus instead keeps that UX
        # working right up until runner.diagnose() actually starts providing alone_n > 0, at
        # which point this branch is simply never reached.
        raise UnhandledStatus(
            "assemble_report cannot yet build a NOT_REPRODUCED report: alone_n is 0, meaning "
            "runner.diagnose() has not started running the alone check for this status yet "
            "(ADR-008 step 4, not landed). See eval/report.py's module docstring."
        )
    fields = resource_fields if diagnosis.status == POLLUTER_FOUND else None
    edge_found = bool(fields and fields["shared_resource"] is not None)
    any_edge_found = fields.get("any_edge_found", edge_found) if fields else False
    infrastructure_failures = getattr(diagnosis, "infrastructure_failures", 0)

    decision_input = DecisionInput(
        source_integrity_passed=diagnosis.source_integrity.passed,
        isolation_successes=diagnosis.alone_successes,
        isolation_n=diagnosis.alone_n,
        sequence_successes=diagnosis.sequence_successes,
        sequence_n=diagnosis.sequence_n,
        sequence_failures_any=diagnosis.sequence_any_failures,
        resource_edge_exists=edge_found,
        confidence=confidence,
        infrastructure_failures=infrastructure_failures,
    )
    decision = decide(decision_input)

    ref = diagnosis.reference_signature
    if diagnosis.status in (POLLUTER_FOUND, VICTIM_FAILS_ALONE):
        assert ref is not None, "POLLUTER_FOUND/VICTIM_FAILS_ALONE always carry a reference signature"
    failure_signature = None if ref is None else {
        "exception_type": ref.exception_type,
        "message": ref.message,
        "stack_trace": ref.stack_trace,
    }

    limitations = [
        "instrumentation_level is static-only (Iteration 1); runtime instrumentation is Iteration 2.",
    ]
    if diagnosis.status == POLLUTER_FOUND:
        if fields:
            limitations += fields["limitations"]
        if not any_edge_found:
            limitations.append("No polluter-write/victim-read resource edge was found by static analysis.")
    elif decision.unresolved_reason == "NOT_REPRODUCED":
        limitations.append(
            f"Not reproduced: {diagnosis.sequence_n} runs of the given order, "
            f"{diagnosis.alone_n} runs alone. In the given order the failure rate is below "
            f"{decision.sequence_interval[1]:.3f} with {confidence:.0%} confidence (Wilson). "
            "This is not evidence that the test is reliable: flaky tests have been found only "
            "after thousands of reruns."
        )
    elif decision.unresolved_reason == "INFRASTRUCTURE_FAILURE":
        limitations.append(
            f"Every one of {diagnosis.sequence_any_failures} failing run(s) of {diagnosis.sequence_n} "
            "crashed or timed out; none produced a real exception, so there is no failure signature "
            "to report. This is a tooling/infrastructure problem, not evidence of a different bug."
        )

    report = {
        "victim": diagnosis.victim.to_dict(),
        "polluters": [p.to_dict() for p in diagnosis.polluters],
        "original_failing_order": [t.to_dict() for t in diagnosis.original_order],
        "reduced_sequence": [t.to_dict() for t in diagnosis.sequence],
        "reproduction": {
            "successes": diagnosis.sequence_successes, "n": diagnosis.sequence_n,
            "confidence": confidence,
            "lower": decision.sequence_interval[0], "upper": decision.sequence_interval[1],
        },
        "sequence_any_signature_failures": diagnosis.sequence_any_failures,
        "victim_alone": {
            "successes": diagnosis.alone_successes, "n": diagnosis.alone_n,
            "confidence": confidence,
            "lower": decision.isolation_interval[0], "upper": decision.isolation_interval[1],
        },
        "shared_resource": fields["shared_resource"] if fields else None,
        "polluter_write_location": fields["polluter_write_location"] if fields else None,
        "victim_read_location": fields["victim_read_location"] if fields else None,
        "failure_signature": failure_signature,
        "instrumentation_level": "static-only",
        "execution_record_reference": diagnosis.execution_record,
        "source_integrity": {
            "passed": diagnosis.source_integrity.passed,
            "details": diagnosis.source_integrity.details,
        },
        "outcome": decision.outcome,
        "unresolved_reason": decision.unresolved_reason,
        "limitations": limitations,
    }
    order_exploration = _order_exploration(diagnosis)
    if order_exploration is not None:
        report["order_exploration"] = order_exploration
    validate_report(report)
    return report
