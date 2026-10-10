import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eval.outcome import (
    DecisionInput,
    decide,
    OUTCOME_VERIFIED,
    OUTCOME_CANDIDATE,
    OUTCOME_UNRESOLVED,
    REASON_VICTIM_FAILS_ALONE,
    REASON_NOT_REPRODUCED,
    REASON_SIGNATURE_MISMATCH,
    REASON_INFRASTRUCTURE_FAILURE,
    REASON_NO_SUPPORTED_RESOURCE_EVIDENCE,
    REASON_SOURCE_INTEGRITY_FAILED,
)


def base_kwargs(**overrides):
    """A VERIFIED-shaped baseline; each test overrides just what it needs to
    hit its own decision-table row."""
    kwargs = dict(
        source_integrity_passed=True,
        isolation_successes=0,
        isolation_n=20,
        sequence_successes=20,
        sequence_n=20,
        sequence_failures_any=20,
        resource_edge_exists=True,
    )
    kwargs.update(overrides)
    return kwargs


class TestDecisionTableRows(unittest.TestCase):
    """One test per row of the decision table in eval/outcome.py."""

    def test_row1_source_integrity_failed_overrides_everything(self):
        d = DecisionInput(**base_kwargs(source_integrity_passed=False))
        decision = decide(d)
        self.assertEqual(decision.outcome, OUTCOME_UNRESOLVED)
        self.assertEqual(decision.unresolved_reason, REASON_SOURCE_INTEGRITY_FAILED)

    def test_row2_victim_fails_alone(self):
        d = DecisionInput(**base_kwargs(isolation_successes=1))
        decision = decide(d)
        self.assertEqual(decision.outcome, OUTCOME_UNRESOLVED)
        self.assertEqual(decision.unresolved_reason, REASON_VICTIM_FAILS_ALONE)

    def test_row3a_not_reproduced(self):
        d = DecisionInput(**base_kwargs(sequence_successes=0, sequence_failures_any=0))
        decision = decide(d)
        self.assertEqual(decision.outcome, OUTCOME_UNRESOLVED)
        self.assertEqual(decision.unresolved_reason, REASON_NOT_REPRODUCED)

    def test_row3b_infrastructure_failure(self):
        """ADR-008: every any-signature failure was a crash/timeout, no real exception."""
        d = DecisionInput(**base_kwargs(
            sequence_successes=0, sequence_failures_any=5, infrastructure_failures=5,
        ))
        decision = decide(d)
        self.assertEqual(decision.outcome, OUTCOME_UNRESOLVED)
        self.assertEqual(decision.unresolved_reason, REASON_INFRASTRUCTURE_FAILURE)

    def test_row3b_infrastructure_failure_is_unreachable_by_default(self):
        """Pre-ADR-008 behaviour is exactly preserved when a caller never reports
        infrastructure_failures: any any-signature failure reads as SIGNATURE_MISMATCH."""
        d = DecisionInput(**base_kwargs(sequence_successes=0, sequence_failures_any=5))
        self.assertEqual(d.infrastructure_failures, 0)
        decision = decide(d)
        self.assertEqual(decision.unresolved_reason, REASON_SIGNATURE_MISMATCH)

    def test_row3c_signature_mismatch(self):
        """At least one failure was a real, different exception -- not infrastructure-only."""
        d = DecisionInput(**base_kwargs(
            sequence_successes=0, sequence_failures_any=5, infrastructure_failures=3,
        ))
        decision = decide(d)
        self.assertEqual(decision.outcome, OUTCOME_UNRESOLVED)
        self.assertEqual(decision.unresolved_reason, REASON_SIGNATURE_MISMATCH)

    def test_row4a_no_supported_resource_evidence(self):
        d = DecisionInput(**base_kwargs(resource_edge_exists=False))
        decision = decide(d)
        self.assertEqual(decision.outcome, OUTCOME_UNRESOLVED)
        self.assertEqual(decision.unresolved_reason, REASON_NO_SUPPORTED_RESOURCE_EVIDENCE)

    def test_row4b_verified(self):
        # 20/20 reproduced, 0/20 alone, resource edge present, default threshold.
        d = DecisionInput(**base_kwargs())
        decision = decide(d)
        self.assertEqual(decision.outcome, OUTCOME_VERIFIED)
        self.assertIsNone(decision.unresolved_reason)
        self.assertGreaterEqual(decision.sequence_interval[0], d.lower_bound_threshold)

    def test_row4c_candidate(self):
        # 12/20 reproduced -> Wilson lower bound < 0.70, but resource edge present.
        d = DecisionInput(**base_kwargs(sequence_successes=12, sequence_failures_any=12))
        decision = decide(d)
        self.assertEqual(decision.outcome, OUTCOME_CANDIDATE)
        self.assertIsNone(decision.unresolved_reason)
        self.assertLess(decision.sequence_interval[0], d.lower_bound_threshold)


class TestDecisionInputValidation(unittest.TestCase):
    def test_isolation_n_zero_raises(self):
        with self.assertRaises(ValueError):
            DecisionInput(**base_kwargs(isolation_n=0))

    def test_sequence_n_zero_raises(self):
        with self.assertRaises(ValueError):
            DecisionInput(**base_kwargs(sequence_n=0))

    def test_sequence_successes_exceeds_failures_any_raises(self):
        with self.assertRaises(ValueError):
            DecisionInput(**base_kwargs(sequence_successes=10, sequence_failures_any=5))

    def test_isolation_successes_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            DecisionInput(**base_kwargs(isolation_successes=21))

    def test_confidence_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            DecisionInput(**base_kwargs(confidence=1.0))

    def test_infrastructure_failures_exceeding_failures_any_raises(self):
        with self.assertRaises(ValueError):
            DecisionInput(**base_kwargs(
                sequence_successes=0, sequence_failures_any=5, infrastructure_failures=6,
            ))


if __name__ == "__main__":
    unittest.main()
