"""Repeated-run counts (W7, ADR-004)."""

from typing import Sequence, Tuple

from eval.baseline import FailureSignature, TestIdentifier
from runner.search import SYNTHETIC_PREFIX


def repeat(
    runner, sequence: Sequence[TestIdentifier], victim: TestIdentifier, reference: FailureSignature, n: int
) -> Tuple[int, int]:
    """Run `sequence` n times, each in a fresh JVM. Returns (runs where the victim failed with a
    signature matching `reference`, runs where the victim failed for any reason)."""
    successes = any_failures = 0
    for _ in range(n):
        outcome = runner.run_ordered(list(sequence))[victim]
        if not outcome.passed:
            any_failures += 1
            if outcome.failure_signature.matches(reference):
                successes += 1
    return successes, any_failures


def repeat_without_reference(runner, victim: TestIdentifier, n: int):
    """Run the victim alone n times when nothing reproduced yet (ADR-008). The first real failure
    becomes the reference. Returns (reference or None, runs matching it, runs failing for any reason)."""
    outcomes = [runner.run_ordered([victim])[victim] for _ in range(n)]
    reference = next((o.failure_signature for o in outcomes if not o.passed
                      and not o.failure_signature.exception_type.startswith(SYNTHETIC_PREFIX)), None)
    any_failures = sum(1 for o in outcomes if not o.passed)
    successes = 0 if reference is None else sum(
        1 for o in outcomes if not o.passed and o.failure_signature.matches(reference))
    return reference, successes, any_failures
