"""Valid shuffled test orders for when the starting order does not reproduce (ADR-008).

Classes are shuffled, then methods within each class; methods of different classes are never
interleaved, because JUnit cannot run such an order (iDFlakies [3], parameter-provenance.md).
"""

import random
from typing import Dict, List, Optional, Sequence, Tuple

from eval.baseline import FailureSignature, TestIdentifier
from runner.search import SYNTHETIC_PREFIX


def class_first_shuffle(order: Sequence[TestIdentifier], seed: int) -> List[TestIdentifier]:
    rng = random.Random(seed)
    by_class: Dict[str, List[TestIdentifier]] = {}
    for test in order:
        by_class.setdefault(test.class_name, []).append(test)
    classes = list(by_class)
    rng.shuffle(classes)
    shuffled: List[TestIdentifier] = []
    for name in classes:
        methods = list(by_class[name])
        rng.shuffle(methods)
        shuffled += methods
    return shuffled


def distinct_shuffles(
    order: Sequence[TestIdentifier], victim: TestIdentifier, budget: int, seed_base: int
) -> Tuple[List[Tuple[int, List[TestIdentifier]]], bool]:
    """Up to `budget` distinct shuffled orders, each cut after the victim and different from the
    starting order, with their seeds. The second value is True when fewer were found within
    10 x budget seeds (no further distinct order found -- sampled, not proven exhaustive)."""
    found: List[Tuple[int, List[TestIdentifier]]] = []
    start = list(order)[: list(order).index(victim) + 1]
    seen = {tuple(start)}  # the starting order already ran; it is not a new shuffled order
    for seed in range(seed_base, seed_base + 10 * budget):
        if len(found) == budget:
            break
        shuffled = class_first_shuffle(order, seed)
        cut = shuffled[: shuffled.index(victim) + 1]
        if tuple(cut) not in seen:
            seen.add(tuple(cut))
            found.append((seed, cut))
    return found, len(found) < budget


def search_orders(
    runner, candidates: Sequence[Tuple[int, List[TestIdentifier]]], victim: TestIdentifier
) -> Tuple[Optional[int], Optional[List[TestIdentifier]], Optional[FailureSignature], int, int]:
    """Run each candidate once; the first real victim failure wins and becomes the reference.
    Returns (seed, order, reference, runs made, runs where the victim failed for any reason)."""
    runs = any_failures = 0
    try:
        for seed, order in candidates:
            if hasattr(runner, "note"):
                runner.note = {"seed": seed}
            runs += 1
            outcome = runner.run_ordered(list(order))[victim]
            if outcome.passed:
                continue
            any_failures += 1
            if not outcome.failure_signature.exception_type.startswith(SYNTHETIC_PREFIX):
                return seed, list(order), outcome.failure_signature, runs, any_failures
        return None, None, None, runs, any_failures
    finally:
        if hasattr(runner, "note"):
            runner.note = {}
