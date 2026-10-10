"""Outcome/decision logic for FlakeTrace diagnosis reports (Iteration 1).

Decision table (confirmed with Member 3 on 2026-10-08; first match wins):

  1. source integrity check failed            -> UNRESOLVED(SOURCE_INTEGRITY_FAILED)
  2. victim fails alone at least once          -> UNRESOLVED(VICTIM_FAILS_ALONE)
     (isolation_successes >= 1; a "success" here means the isolation run
     failed with the SAME signature as the reference failure)
  3. sequence never reproduces that signature  (sequence_successes == 0):
       a. and never failed at all              -> UNRESOLVED(NOT_REPRODUCED)
       b. failed only with crashes/timeouts, no real failure at all
          (sequence_failures_any == infrastructure_failures > 0) -> UNRESOLVED(INFRASTRUCTURE_FAILURE)
       c. failed with a real but different signature -> UNRESOLVED(SIGNATURE_MISMATCH)
  4. sequence reproduces it at least once       (sequence_successes >= 1):
       a. no polluter-write/victim-read resource edge -> UNRESOLVED(NO_SUPPORTED_RESOURCE_EVIDENCE)
       b. resource edge exists, Wilson lower bound >= threshold -> VERIFIED
       c. resource edge exists, Wilson lower bound <  threshold -> CANDIDATE

Ranking alone never produces VERIFIED: VERIFIED requires both a concrete
polluter-write/victim-read resource edge AND a Wilson lower bound at or
above the confidence threshold.

BELOW_CONFIDENCE_THRESHOLD stays in the schema's unresolved-reason enum (the
brief requires it "at least"), but this decision function never emits it --
case 4c uses CANDIDATE instead, per the 2026-10-08 team decision.

Row 3b (INFRASTRUCTURE_FAILURE, ADR-008, 2026-10-10) distinguishes "the sequence
never produced a real failure, only crashes/timeouts" from row 3c
(SIGNATURE_MISMATCH, "it failed for real but not the reference bug") -- before
this, a crash-only sequence read as SIGNATURE_MISMATCH, which suggests a
different real bug rather than a tooling/infrastructure problem.
`infrastructure_failures` defaults to 0, so a caller that has not counted this
(every pre-ADR-008 caller) gets exactly the old row 3c (SIGNATURE_MISMATCH)
behaviour whenever `sequence_failures_any > 0` -- row 3b is unreachable unless
a caller actually reports `infrastructure_failures > 0`.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from eval.stats import wilson_interval

OUTCOME_VERIFIED = "VERIFIED"
OUTCOME_CANDIDATE = "CANDIDATE"
OUTCOME_UNRESOLVED = "UNRESOLVED"
VALID_OUTCOMES = (OUTCOME_VERIFIED, OUTCOME_CANDIDATE, OUTCOME_UNRESOLVED)

REASON_VICTIM_FAILS_ALONE = "VICTIM_FAILS_ALONE"
REASON_NOT_REPRODUCED = "NOT_REPRODUCED"
REASON_SIGNATURE_MISMATCH = "SIGNATURE_MISMATCH"
REASON_INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
REASON_NO_SUPPORTED_RESOURCE_EVIDENCE = "NO_SUPPORTED_RESOURCE_EVIDENCE"
REASON_BELOW_CONFIDENCE_THRESHOLD = "BELOW_CONFIDENCE_THRESHOLD"  # reserved, unused by decide()
REASON_SOURCE_INTEGRITY_FAILED = "SOURCE_INTEGRITY_FAILED"
VALID_UNRESOLVED_REASONS = (
    REASON_VICTIM_FAILS_ALONE,
    REASON_NOT_REPRODUCED,
    REASON_SIGNATURE_MISMATCH,
    REASON_INFRASTRUCTURE_FAILURE,
    REASON_NO_SUPPORTED_RESOURCE_EVIDENCE,
    REASON_BELOW_CONFIDENCE_THRESHOLD,
    REASON_SOURCE_INTEGRITY_FAILED,
)

DEFAULT_CONFIDENCE = 0.95
DEFAULT_LOWER_BOUND_THRESHOLD = 0.70


@dataclass(frozen=True)
class DecisionInput:
    source_integrity_passed: bool
    isolation_successes: int
    isolation_n: int
    sequence_successes: int
    sequence_n: int
    sequence_failures_any: int
    resource_edge_exists: bool
    confidence: float = DEFAULT_CONFIDENCE
    lower_bound_threshold: float = DEFAULT_LOWER_BOUND_THRESHOLD
    infrastructure_failures: int = 0
    """How many of sequence_failures_any were a crash/timeout, not a real but
    different exception (ADR-008). Defaults to 0: a caller that has not
    counted this gets exactly the pre-ADR-008 SIGNATURE_MISMATCH behaviour."""

    def __post_init__(self):
        if self.isolation_n <= 0:
            raise ValueError(f"isolation_n must be > 0, got {self.isolation_n!r}")
        if self.sequence_n <= 0:
            raise ValueError(f"sequence_n must be > 0, got {self.sequence_n!r}")
        if not (0 <= self.isolation_successes <= self.isolation_n):
            raise ValueError(
                f"isolation_successes must be within [0, isolation_n], "
                f"got isolation_successes={self.isolation_successes!r}, isolation_n={self.isolation_n!r}"
            )
        if not (0 <= self.sequence_successes <= self.sequence_n):
            raise ValueError(
                f"sequence_successes must be within [0, sequence_n], "
                f"got sequence_successes={self.sequence_successes!r}, sequence_n={self.sequence_n!r}"
            )
        if not (0 <= self.sequence_failures_any <= self.sequence_n):
            raise ValueError(
                f"sequence_failures_any must be within [0, sequence_n], "
                f"got sequence_failures_any={self.sequence_failures_any!r}, sequence_n={self.sequence_n!r}"
            )
        if self.sequence_successes > self.sequence_failures_any:
            raise ValueError(
                "sequence_successes (signature-matching failures) cannot exceed "
                f"sequence_failures_any (any-signature failures), got "
                f"sequence_successes={self.sequence_successes!r}, "
                f"sequence_failures_any={self.sequence_failures_any!r}"
            )
        if not (0 <= self.infrastructure_failures <= self.sequence_failures_any):
            raise ValueError(
                "infrastructure_failures (a subset of the any-signature failures) cannot "
                f"exceed sequence_failures_any, got infrastructure_failures={self.infrastructure_failures!r}, "
                f"sequence_failures_any={self.sequence_failures_any!r}"
            )
        if not (0.0 < self.confidence < 1.0):
            raise ValueError(f"confidence must be in (0, 1), got {self.confidence!r}")
        if not (0.0 <= self.lower_bound_threshold <= 1.0):
            raise ValueError(f"lower_bound_threshold must be in [0, 1], got {self.lower_bound_threshold!r}")


@dataclass(frozen=True)
class Decision:
    outcome: str
    unresolved_reason: Optional[str]
    sequence_interval: Tuple[float, float]
    isolation_interval: Tuple[float, float]
    rationale: str


def decide(d: DecisionInput) -> Decision:
    """Apply the Iteration 1 decision table to a DecisionInput. See module
    docstring for the full table; this function implements it top to bottom,
    first match wins."""

    sequence_interval = wilson_interval(d.sequence_successes, d.sequence_n, d.confidence)
    isolation_interval = wilson_interval(d.isolation_successes, d.isolation_n, d.confidence)

    def result(outcome, reason, rationale):
        return Decision(
            outcome=outcome,
            unresolved_reason=reason,
            sequence_interval=sequence_interval,
            isolation_interval=isolation_interval,
            rationale=rationale,
        )

    if not d.source_integrity_passed:
        return result(
            OUTCOME_UNRESOLVED,
            REASON_SOURCE_INTEGRITY_FAILED,
            "Source-integrity check failed, so no other evidence can be trusted.",
        )

    if d.isolation_successes >= 1:
        return result(
            OUTCOME_UNRESOLVED,
            REASON_VICTIM_FAILS_ALONE,
            f"Victim reproduced its reference failure signature "
            f"{d.isolation_successes}/{d.isolation_n} times when run alone; "
            "cannot attribute any polluted-order failure to a polluter.",
        )

    if d.sequence_successes == 0:
        if d.sequence_failures_any == 0:
            return result(
                OUTCOME_UNRESOLVED,
                REASON_NOT_REPRODUCED,
                f"Sequence never reproduced any failure in {d.sequence_n} runs.",
            )
        if d.sequence_failures_any == d.infrastructure_failures:
            return result(
                OUTCOME_UNRESOLVED,
                REASON_INFRASTRUCTURE_FAILURE,
                f"Sequence failed {d.sequence_failures_any}/{d.sequence_n} times, but every "
                "failure was a crash or timeout, never a real exception -- a tooling problem, "
                "not evidence of a different bug.",
            )
        return result(
            OUTCOME_UNRESOLVED,
            REASON_SIGNATURE_MISMATCH,
            f"Sequence failed {d.sequence_failures_any}/{d.sequence_n} times but never with "
            "the reference failure signature.",
        )

    # sequence_successes >= 1 from here on.
    if not d.resource_edge_exists:
        return result(
            OUTCOME_UNRESOLVED,
            REASON_NO_SUPPORTED_RESOURCE_EVIDENCE,
            f"Sequence reproduced {d.sequence_successes}/{d.sequence_n} times, but no "
            "polluter-write/victim-read resource edge was found to support it.",
        )

    if sequence_interval[0] >= d.lower_bound_threshold:
        return result(
            OUTCOME_VERIFIED,
            None,
            f"Sequence reproduced {d.sequence_successes}/{d.sequence_n} "
            f"(Wilson lower bound {sequence_interval[0]:.3f} >= {d.lower_bound_threshold}), "
            "victim never failed alone, and a resource edge supports it.",
        )

    return result(
        OUTCOME_CANDIDATE,
        None,
        f"Sequence reproduced {d.sequence_successes}/{d.sequence_n} "
        f"(Wilson lower bound {sequence_interval[0]:.3f} < {d.lower_bound_threshold}) "
        "with a supporting resource edge, but below the confidence threshold for VERIFIED.",
    )
