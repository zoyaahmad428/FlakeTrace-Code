"""W7 entry point (ADR-004): reproduce the failure, check the victim alone, search for a single
polluter, repeat the sequence, check source integrity, record every run. When no single test is
enough, ddmin shrinks the tests before the victim to a 1-minimal set (W10, ADR-007). Returns raw
counts; the verdict is M3's eval.outcome.decide() (W9 builds the report)."""

import platform
import shutil
import subprocess
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

from eval.baseline import FailureSignature, TestIdentifier
from runner.discovery import discover_order
from runner.integrity import SourceIntegrity, compare, snapshot
from runner.minimise import ddmin
from runner.orders import distinct_shuffles, search_orders
from runner.order_runner import OrderRunner, java_version, maven_test_classpath
from runner.recording import RecordingRunner
from runner.search import find_polluter, reproduce
from runner.verify import repeat, repeat_without_reference

POLLUTER_FOUND = "POLLUTER_FOUND"
VICTIM_FAILS_ALONE = "VICTIM_FAILS_ALONE"
NO_SINGLE_POLLUTER = "NO_SINGLE_POLLUTER"
NOT_REPRODUCED = "NOT_REPRODUCED"


class DiagnoseInputError(ValueError):
    """A wrong argument to diagnose() (n, victim, record folder) -- the caller's input, not a bug."""


@dataclass(frozen=True)
class DiagnosisRuns:
    status: str
    victim: TestIdentifier
    original_order: List[TestIdentifier]
    reference_signature: Optional[FailureSignature]
    polluters: List[TestIdentifier]
    sequence: List[TestIdentifier]
    sequence_n: int
    sequence_successes: int
    sequence_any_failures: int
    alone_n: int
    alone_successes: int
    search_runs: int
    source_integrity: Optional[SourceIntegrity] = None
    execution_record: Optional[str] = None
    minimise_runs: int = 0
    # ADR-008: how the failing order was found (read by eval.report as `order_exploration`).
    order_given: bool = False
    shuffled_orders: int = 0
    orders_exhausted: bool = False
    shuffle_seed_base: int = 0
    reproducing_seed: Optional[int] = None
    infrastructure_failures: int = 0
    shuffle_infrastructure_failures: int = 0  # shuffle runs where the victim only crashed/timed out
    alone_infrastructure_failures: int = 0  # same for alone runs when nothing reproduced


def run_steps(
    runner,
    original_order: Sequence[TestIdentifier],
    victim: TestIdentifier,
    n: int,
    priority: Optional[Sequence[TestIdentifier]] = None,
    shuffles: int = 0,
    seed_base: int = 0,
    order_given: bool = False,
) -> DiagnosisRuns:
    """Steps 3-6 of ADR-004 on any OrderRunner, plus ADR-008: shuffled orders when the starting
    order never fails, and the alone check always. Stops early as the ADRs' status tables say."""
    if n < 1:
        raise DiagnoseInputError(f"n must be >= 1, got {n!r}")
    if victim not in original_order:
        raise DiagnoseInputError(f"victim {victim} is not in the original order")
    full = list(original_order)
    order = full[: full.index(victim) + 1]

    _label(runner, "reproduce")
    reference, attempts, attempt_failures = reproduce(runner, order, victim, n)
    explore = dict(order_given=order_given, shuffle_seed_base=seed_base)
    if reference is None and shuffles > 0:
        # The starting order never failed for real: try valid shuffled orders of the whole suite (ADR-008).
        _label(runner, "shuffle")
        candidates, exhausted = distinct_shuffles(full, victim, shuffles, seed_base)
        seed, found, found_reference, tried, shuffle_any = search_orders(runner, candidates, victim)
        explore.update(shuffled_orders=tried, orders_exhausted=exhausted and found is None,
                       # every failure before the reproducing one was a crash, timeout or skip
                       shuffle_infrastructure_failures=shuffle_any - (1 if found is not None else 0))
        if found is not None:
            order, reference = found, found_reference
            explore["reproducing_seed"] = seed

    _label(runner, "alone")
    if reference is None:
        alone_reference, alone_matches, alone_any = repeat_without_reference(runner, victim, n)
        if alone_reference is not None:
            # The only order that failed is the victim alone, so that is the failing order reported.
            return DiagnosisRuns(VICTIM_FAILS_ALONE, victim, [victim], alone_reference, [], [victim],
                                 n, alone_matches, alone_any, n, alone_matches, 0, **explore)
        # No real failure anywhere, so every failure counted (order, shuffles, alone) was a
        # crash, timeout or skip.
        return DiagnosisRuns(NOT_REPRODUCED, victim, order, None, [], order,
                             attempts, 0, attempt_failures, n, 0, 0,
                             infrastructure_failures=attempt_failures,
                             alone_infrastructure_failures=alone_any, **explore)
    alone_successes, alone_any = repeat(runner, [victim], victim, reference, n)
    if alone_successes >= 1:
        return DiagnosisRuns(VICTIM_FAILS_ALONE, victim, order, reference, [], [victim],
                             n, alone_successes, alone_any, n, alone_successes, 0, **explore)

    _label(runner, "search")
    polluter, search_runs = find_polluter(runner, order, victim, reference, priority)
    polluters, minimise_runs = ([polluter], 0) if polluter is not None else ([], 0)
    if polluter is None and len(order) > 2:
        # No single test is enough: shrink everything before the victim (ADR-007). The full order
        # must fail once more first, so a flaky failure never blames every earlier test. (With one
        # earlier test, the search already ran exactly [test, victim] and saw it pass.)
        _label(runner, "minimise")
        again = runner.run_ordered(order)[victim]
        minimise_runs = 1
        if not again.passed and again.failure_signature.matches(reference):
            polluters, ddmin_runs = ddmin(runner, order[:-1], victim, reference)
            minimise_runs += ddmin_runs
    sequence = polluters + [victim] if polluters else order
    _label(runner, "verify")
    successes, any_failures = repeat(runner, sequence, victim, reference, n)
    status = POLLUTER_FOUND if polluters else NO_SINGLE_POLLUTER
    return DiagnosisRuns(status, victim, order, reference, polluters, sequence,
                         n, successes, any_failures, n, 0, search_runs, minimise_runs=minimise_runs, **explore)


def diagnose(
    project_dir,
    victim: TestIdentifier,
    n: int = 20,
    original_order: Optional[Sequence[TestIdentifier]] = None,
    priority: Optional[Sequence[TestIdentifier]] = None,
    record_dir="flaketrace-records",
    timeout_s: float = 120.0,
    shuffles: int = 31,
    seed: int = 0,
) -> DiagnosisRuns:
    if n < 1:
        raise DiagnoseInputError(f"n must be >= 1, got {n!r}")
    if shuffles < 0:
        raise DiagnoseInputError(f"shuffles must be >= 0, got {shuffles!r}")
    if original_order is not None and victim not in original_order:
        raise DiagnoseInputError(f"victim {victim} is not in the original order")
    if original_order is not None and len(set(original_order)) != len(original_order):
        raise DiagnoseInputError("the given order lists a test more than once")
    project = Path(project_dir).resolve()
    records = Path(record_dir).resolve()
    if records == project or project in records.parents:
        # A record written inside the project would itself make the integrity check fail.
        raise DiagnoseInputError(f"record_dir {records} is inside the analysed project {project}")
    if records.exists() and not records.is_dir():
        raise DiagnoseInputError(f"record_dir {records} is a file, not a folder")
    before = snapshot(project)
    runner = OrderRunner(maven_test_classpath(project), working_dir=project, timeout_s=timeout_s)
    discovered = discover_order(runner, project / "target" / "test-classes")
    if original_order is not None:
        # A typo in a given order would fail with ClassNotFound and could pass for a reproduction.
        known = set(discovered)
        unknown = [test for test in original_order if test not in known]
        if unknown:
            raise DiagnoseInputError(
                f"{len(unknown)} test(s) in the given order are not among the project's tests (first: "
                f"{unknown[0]}); only classes matching Surefire's default includes (Test*, *Test, *Tests, "
                "*TestCase) are discovered")
    order = list(original_order) if original_order is not None else discovered
    if victim not in order:
        # Checked before the recorder exists, so no empty record is left behind.
        raise DiagnoseInputError(f"victim {victim} is not among the project's tests")

    started = datetime.now(timezone.utc)
    record = Path(record_dir) / f"{started.strftime('%Y%m%dT%H%M%SZ')}-{victim}.jsonl"
    recorder = RecordingRunner(runner, record, {
        "victim": str(victim), "n": n, "project": str(project),
        "java_version": java_version(), "started": started.isoformat(), **environment(project),
        "order_given": original_order is not None, "shuffles": shuffles, "seed_base": seed,
    })
    result = run_steps(recorder, order, victim, n, priority, shuffles=shuffles, seed_base=seed,
                       order_given=original_order is not None)
    return replace(result, source_integrity=compare(before, snapshot(project)),
                   execution_record=str(record))


def environment(project: Path) -> dict:
    """Execution-record facts for panel action A7: the analysed project's git commit, whether it had
    uncommitted changes, and the OS. Commit and dirty are None when the project is not in a git
    repository or git is missing -- unknown provenance never stops a diagnosis."""
    commit = dirty = None
    git = shutil.which("git")
    if git:
        head = subprocess.run([git, "-C", str(project), "rev-parse", "HEAD"], capture_output=True, text=True)
        status = subprocess.run([git, "-C", str(project), "status", "--porcelain", "--", "."],
                                capture_output=True, text=True)
        if head.returncode == 0 and status.returncode == 0:
            commit, dirty = head.stdout.strip(), bool(status.stdout.strip())
    return {"project_commit": commit, "project_dirty": dirty, "os": platform.platform()}


def _label(runner, step: str) -> None:
    if isinstance(runner, RecordingRunner):
        runner.step = step
