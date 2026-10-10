# ADR-008 Runner Side Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the starting order never fails, try up to 31 distinct class-first shuffled orders, always run the victim alone, accept the real failing order via `--order`, and give Member 3's merged report code the fields it reads — so F4 becomes `VERIFIED` through a shuffle and N3 gets an honest `NOT_REPRODUCED` report.

**Architecture:** New `runner/orders.py` (pure order generation + a search over orders). `runner/verify.py` gains a repeat without a reference signature. `runner/diagnose.run_steps` gets the shuffle phase and the always-run alone check, `DiagnosisRuns` gains six defaulted fields, `diagnose()` validates a given order. `runner/recording.py` lets a run line carry a note (the seed). `runner/cli.py` gets `--order/--shuffles/--seed` and summary lines. Nothing in `eval/` or `evidence/` changes (M3's side merged in PR #45).

**Tech Stack:** Python 3.11 (CI) / 3.14 (local), `unittest`, `random.Random`, `FakeOrderRunner` (tests only); JDK 8+, Maven for real runs.

**Spec:** `docs/03-Design/decisions/ADR-008-not-reproduced-and-order-search.md`

## Global Constraints

- Shuffle = group by class, shuffle classes, shuffle methods inside each class, `random.Random(seed)`; never interleave classes; cut after the victim.
- Seeds `seed_base, seed_base+1, …`; count **distinct** cut orders only; stop at the budget or after `10 × budget` seeds; report the real number and whether orders were exhausted.
- A run reproduces only with a real exception (`exception_type` not starting with `flaketrace.`).
- Default budget 31 (`--shuffles`), default seed 0 (`--seed`); `run_steps` defaults to 0 shuffles so existing fake-runner tests keep their run counts.
- `DiagnosisRuns` new fields, exact names (M3's `eval/report.py` reads them): `order_given`, `shuffled_orders`, `orders_exhausted`, `shuffle_seed_base`, `reproducing_seed`, `infrastructure_failures`.
- Alone check always runs; without a reference the first real alone failure becomes the reference.
- `--order` file: one `Class#method` per line, blank and `#` lines ignored, UTF-8 with or without BOM, CRLF ok; exit 2 for missing/empty file, bad line, duplicate, victim absent, unknown test.
- Fakes only under tests; never modify the fixture; the member commits (single-line cmd commands).

## Review Focus

1. An `--order` file saved on Windows (CRLF, UTF-8 BOM, trailing spaces) → parsed exactly like a clean file (Task 3, `test_order_file_with_bom_crlf_and_spaces_is_read`).
2. A suite where every class has one method and only two classes exist → `orders_exhausted` true and the count is 2, not 31 (Task 1, `test_small_suite_is_exhausted_honestly`).
3. A shuffle that puts the victim first → runs `[victim]`, counted once as a distinct order (Task 1, `test_victim_first_shuffle_is_a_distinct_order`).
4. `--shuffles 0` → no shuffle runs; a not-reproduced diagnosis still reports with `shuffled_orders` 0 (Task 2, `test_zero_shuffles_skips_the_phase`).
5. The seed of every shuffle run is in its execution-record line (Task 2, `test_shuffle_runs_record_their_seed`).

## File Structure

| File | Responsibility |
| --- | --- |
| `runner/orders.py` (create) | `class_first_shuffle`, `distinct_shuffles`, `search_orders` |
| `runner/tests/test_orders.py` (create) | the above, pure + `FakeOrderRunner` |
| `runner/recording.py` (modify) | optional `note` merged into run lines |
| `runner/verify.py` (modify) | `repeat_without_reference` |
| `runner/diagnose.py` (modify) | shuffle phase, alone always, new fields, given-order validation, header |
| `runner/tests/test_diagnose.py`, `test_recording.py` (modify) | fake + real F4/N3 |
| `runner/cli.py`, `runner/tests/test_cli.py` (modify) | options, `read_order`, summary lines; real F4/N3 |

---

### Task 1: Valid shuffled orders and the search over them

**Files:** Create `runner/orders.py`, `runner/tests/test_orders.py`.

**Interfaces:**
- Consumes: `TestIdentifier`, `RunOutcome`, `FailureSignature`, `runner.search.SYNTHETIC_PREFIX`.
- Produces:
  - `class_first_shuffle(order: Sequence[TestIdentifier], seed: int) -> List[TestIdentifier]`
  - `distinct_shuffles(order, victim, budget: int, seed_base: int) -> Tuple[List[Tuple[int, List[TestIdentifier]]], bool]` — (seed, order cut after victim) pairs, distinct, in seed order; `True` if fewer than `budget` were found within `10 × budget` seeds.
  - `search_orders(runner, candidates, victim) -> Tuple[Optional[int], Optional[List[TestIdentifier]], Optional[FailureSignature], int, int]` — (seed, order, reference, runs, runs where the victim failed for any reason); stops at the first real failure; sets `runner.note = {"seed": s}` before each run when the runner has a `note` attribute, and `{}` after.

- [ ] **Step 1: Write the failing tests** — `runner/tests/test_orders.py`:

```python
import unittest

from eval.baseline import FailureSignature, RunOutcome, TestIdentifier
from eval.tests.fake_runner import FakeOrderRunner
from runner.orders import class_first_shuffle, distinct_shuffles, search_orders

V = TestIdentifier("pkg.AVictimTest", "v")
REAL = RunOutcome(passed=False, failure_signature=FailureSignature("java.lang.AssertionError", "x:1", "m"))
CRASH = RunOutcome(passed=False, failure_signature=FailureSignature("flaketrace.JvmCrash", "", "code 1"))
PASS = RunOutcome(passed=True)


def suite(classes=4, methods=2):
    tests = [TestIdentifier(f"pkg.C{c}Test", f"m{m}") for c in range(classes) for m in range(methods)]
    return tests + [V]


class TestShuffle(unittest.TestCase):
    def test_methods_of_a_class_stay_together(self):
        for seed in range(20):
            order = class_first_shuffle(suite(), seed)
            classes = [t.class_name for t in order]
            runs = [c for i, c in enumerate(classes) if i == 0 or c != classes[i - 1]]
            self.assertEqual(len(runs), len(set(runs)), order)

    def test_same_seed_same_order_and_nothing_lost(self):
        self.assertEqual(class_first_shuffle(suite(), 7), class_first_shuffle(suite(), 7))
        self.assertEqual(sorted(class_first_shuffle(suite(), 7), key=str), sorted(suite(), key=str))

    def test_different_seeds_give_different_orders(self):
        self.assertGreater(len({tuple(class_first_shuffle(suite(), s)) for s in range(10)}), 1)

    def test_orders_are_cut_after_the_victim_and_distinct(self):
        shuffles, _ = distinct_shuffles(suite(), V, budget=10, seed_base=0)
        self.assertEqual(len(shuffles), 10)
        self.assertTrue(all(order[-1] == V for _, order in shuffles))
        self.assertEqual(len({tuple(order) for _, order in shuffles}), 10)

    def test_small_suite_is_exhausted_honestly(self):
        two = [TestIdentifier("pkg.BTest", "b"), V]
        shuffles, exhausted = distinct_shuffles(two, V, budget=31, seed_base=0)
        self.assertEqual(sorted(tuple(o) for _, o in shuffles), sorted([(V,), (two[0], V)]))
        self.assertTrue(exhausted)

    def test_victim_first_shuffle_is_a_distinct_order(self):
        shuffles, _ = distinct_shuffles(suite(classes=3, methods=1), V, budget=31, seed_base=0)
        self.assertIn((V,), [tuple(o) for _, o in shuffles])

    def test_seeds_are_consecutive_from_the_base(self):
        shuffles, _ = distinct_shuffles(suite(), V, budget=5, seed_base=100)
        self.assertEqual(shuffles[0][0], 100)
        self.assertTrue(all(a < b for (a, _), (b, _) in zip(shuffles, shuffles[1:])))


class TestSearchOrders(unittest.TestCase):
    def test_first_real_failure_wins_and_crashes_do_not_count(self):
        candidates = [(0, [V]), (1, [TestIdentifier("pkg.ZTest", "z"), V]), (2, [V])]
        outcomes = iter([CRASH, REAL, REAL])
        runner = FakeOrderRunner(lambda order, test: next(outcomes) if test == V else PASS)
        seed, order, reference, runs, any_failures = search_orders(runner, candidates, V)
        self.assertEqual((seed, order, runs, any_failures), (1, candidates[1][1], 2, 2))
        self.assertEqual(reference.exception_type, "java.lang.AssertionError")

    def test_nothing_fails(self):
        runner = FakeOrderRunner(lambda order, test: PASS)
        self.assertEqual(search_orders(runner, [(0, [V]), (1, [V])], V), (None, None, None, 2, 0))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify they fail** — `py -m unittest runner.tests.test_orders` → `ModuleNotFoundError: No module named 'runner.orders'`.

- [ ] **Step 3: Write `runner/orders.py`**

```python
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
    """Up to `budget` distinct shuffled orders, each cut after the victim, with their seeds.
    The second value is True when fewer were found within 10 x budget seeds (orders exhausted)."""
    found: List[Tuple[int, List[TestIdentifier]]] = []
    seen = set()
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
```

- [ ] **Step 4: Run to verify they pass** — `py -m unittest -v runner.tests.test_orders` → `Ran 9 tests … OK`.

- [ ] **Step 5: Mutation check** — on a copy, make `class_first_shuffle` shuffle the flat list (`shuffled = list(order); rng.shuffle(shuffled); return shuffled`); `test_methods_of_a_class_stay_together` must FAIL; restore from the copy (not git); rerun → OK.

- [ ] **Step 6: Full runner suite** — expect `Ran 117 tests … OK` (108 + 9). Docs: evidence log, GenAI log, register row. Commit title `[M2] runner: add class-first shuffled orders for ADR-008`.

---

### Task 2: The diagnosis tries shuffled orders and always runs the alone check

**Files:** Modify `runner/recording.py`, `runner/verify.py`, `runner/diagnose.py`; tests in `runner/tests/test_recording.py`, `runner/tests/test_diagnose.py`.

**Interfaces:**
- Consumes: Task 1's `distinct_shuffles`, `search_orders`.
- Produces:
  - `RecordingRunner.note: dict` (default `{}`), merged into every run line written while non-empty.
  - `repeat_without_reference(runner, victim, n) -> Tuple[Optional[FailureSignature], int, int]` in `runner/verify.py` — runs `[victim]` n times; reference = first real failure; returns (reference, runs matching it, runs failing for any reason).
  - `DiagnosisRuns` fields (all defaulted, after `minimise_runs`): `order_given: bool = False`, `shuffled_orders: int = 0`, `orders_exhausted: bool = False`, `shuffle_seed_base: int = 0`, `reproducing_seed: Optional[int] = None`, `infrastructure_failures: int = 0`.
  - `run_steps(runner, original_order, victim, n, priority=None, shuffles=0, seed_base=0, order_given=False)`.
  - `diagnose(..., shuffles=31, seed=0)`; with `original_order` given: `DiagnoseInputError` for duplicates and for tests not among the discovered tests (one listing run), before any record is written.

- [ ] **Step 1: Write the failing tests**

`runner/tests/test_recording.py` — add:

```python
    def test_note_is_written_into_run_lines_while_set(self):
        path = Path(tempfile.mkdtemp()) / "r.jsonl"
        runner = RecordingRunner(FakeOrderRunner(lambda order, test: RunOutcome(passed=True)), path, {})
        runner.note = {"seed": 7}
        runner.run_ordered([A])
        runner.note = {}
        runner.run_ordered([A])
        lines = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()[1:]]
        self.assertEqual((lines[0]["seed"], "seed" in lines[1]), (7, False))
```

(use the file's existing imports and its test identifier `A`; add any missing import such as `json`, `tempfile`, `Path`, `RunOutcome`, `FakeOrderRunner` at the top.)

`runner/tests/test_diagnose.py` — add to `TestRunSteps` (helpers `victim_fails_when`, `A`, `B`, `V`, `LATER`, `FAIL`, `PASS`, `REF` exist):

```python
    def test_shuffle_finds_an_order_the_starting_order_could_not(self):
        # Victim fails only when LATER ran before it; the starting order puts LATER after it.
        runner = victim_fails_when(lambda order: LATER in order[: order.index(V)])
        runs = run_steps(runner, [A, V, LATER], V, n=2, shuffles=31)
        self.assertEqual(runs.status, POLLUTER_FOUND)
        self.assertEqual(runs.polluters, [LATER])
        self.assertIsNotNone(runs.reproducing_seed)
        self.assertEqual(runs.original_order[-1], V)
        self.assertIn(LATER, runs.original_order)
        self.assertGreater(runs.shuffled_orders, 0)

    def test_nothing_fails_anywhere_is_not_reproduced_with_all_counts(self):
        runs = run_steps(victim_fails_when(lambda order: False), [A, B, V], V, n=3, shuffles=31)
        self.assertEqual(runs.status, NOT_REPRODUCED)
        self.assertIsNone(runs.reference_signature)
        self.assertEqual((runs.sequence_n, runs.alone_n, runs.alone_successes), (3, 3, 0))
        # Cut orders of three one-method classes: [V], [A,V], [B,V], [A,B,V], [B,A,V] — 5 in total.
        self.assertEqual(runs.shuffled_orders, 5)
        self.assertTrue(runs.orders_exhausted)

    def test_failing_alone_without_a_reference_is_victim_fails_alone(self):
        calls = []
        def outcome(order, test):
            if test != V:
                return PASS
            calls.append(order)
            return FAIL if order == [V] else PASS
        runs = run_steps(FakeOrderRunner(outcome), [A, V], V, n=3, shuffles=0)
        self.assertEqual(runs.status, VICTIM_FAILS_ALONE)
        self.assertEqual(runs.reference_signature, REF)
        self.assertEqual((runs.alone_n, runs.alone_successes), (3, 3))

    def test_crash_only_not_reproduced_counts_infrastructure_failures(self):
        crash = RunOutcome(passed=False, failure_signature=FailureSignature("flaketrace.JvmCrash", "", "code 1"))
        runner = FakeOrderRunner(lambda order, test: crash if test == V and order != [V] else PASS)
        runs = run_steps(runner, [A, V], V, n=3, shuffles=0)
        self.assertEqual(runs.status, NOT_REPRODUCED)
        self.assertEqual((runs.sequence_any_failures, runs.infrastructure_failures), (3, 3))

    def test_zero_shuffles_skips_the_phase(self):
        runner = victim_fails_when(lambda order: False)
        runs = run_steps(runner, [A, B, V], V, n=2, shuffles=0)
        self.assertEqual((runs.status, runs.shuffled_orders), (NOT_REPRODUCED, 0))
        self.assertEqual(len(runner.calls), 2 + 2)   # reproduce 2 + alone 2, no shuffle runs

    def test_shuffle_runs_record_their_seed(self):
        record = Path(tempfile.mkdtemp(prefix="flaketrace-rec-")) / "r.jsonl"
        runner = RecordingRunner(victim_fails_when(lambda order: False), record, {})
        run_steps(runner, [A, B, V], V, n=1, shuffles=5, seed_base=40)
        lines = [json.loads(l) for l in record.read_text(encoding="utf-8").splitlines()[1:]]
        shuffles = [l for l in lines if l["step"] == "shuffle"]
        self.assertTrue(shuffles and all(isinstance(l["seed"], int) and l["seed"] >= 40 for l in shuffles))
        self.assertTrue(all("seed" not in l for l in lines if l["step"] != "shuffle"))
```

Update `test_never_failing_is_not_reproduced_and_runs_nothing_else` (it expected the alone check to be skipped): rename to `test_never_failing_without_shuffles_runs_reproduce_and_alone_only` and expect `(runs.alone_n, runs.alone_successes, runs.search_runs) == (3, 0, 0)` and `len(runner.calls) == 3 + 3`.

Update `test_crash_only_original_order_counts_as_failed_but_not_reproduced`: also assert `runs.infrastructure_failures == 3`.

Add real-run tests to `TestDiagnoseOnFixture` (ground truth already has F4 and N3):

```python
    def test_f4_only_a_shuffled_order_reproduces(self):
        runs = self.diagnose_case("F4", n=5)
        self.assertEqual(runs.status, POLLUTER_FOUND)
        self.assertEqual(runs.polluters, self.expected_polluters("F4"))
        self.assertIsNotNone(runs.reproducing_seed)
        self.assertEqual(runs.sequence_successes, 5)

    def test_n3_is_not_reproduced_after_shuffles_and_alone(self):
        runs = self.diagnose_case("N3", n=5)
        self.assertEqual(runs.status, NOT_REPRODUCED)
        self.assertEqual((runs.sequence_n, runs.alone_n, runs.alone_successes), (5, 5, 0))
        self.assertEqual(runs.shuffled_orders, 31)
        self.assertFalse(runs.orders_exhausted)
```

And to `TestRunSteps` (fast, no Maven), given-order validation in `diagnose()`:

```python
    def test_given_order_with_a_duplicate_is_refused_before_maven_runs(self):
        with self.assertRaises(DiagnoseInputError):
            diagnose(Path("does-not-exist"), V, original_order=[A, A, V])
```

- [ ] **Step 2: Run to verify they fail** — `py -m unittest runner.tests.test_recording runner.tests.test_diagnose.TestRunSteps` → failures/errors for `shuffles` unexpected keyword, missing `note`, missing fields.

- [ ] **Step 3: Implement**

`runner/recording.py`: in `__init__` add `self.note: dict = {}`; in `run_ordered` build the entry dict, then `entry.update(self.note)` before `self._write(entry)`.

`runner/verify.py` — add:

```python
def repeat_without_reference(runner, victim: TestIdentifier, n: int):
    """Run the victim alone n times when nothing reproduced yet (ADR-008). The first real failure
    becomes the reference. Returns (reference or None, runs matching it, runs failing for any reason)."""
    reference = None
    outcomes = [runner.run_ordered([victim])[victim] for _ in range(n)]
    for outcome in outcomes:
        if not outcome.passed and not outcome.failure_signature.exception_type.startswith(SYNTHETIC_PREFIX):
            reference = outcome.failure_signature
            break
    any_failures = sum(1 for o in outcomes if not o.passed)
    successes = 0 if reference is None else sum(
        1 for o in outcomes if not o.passed and o.failure_signature.matches(reference))
    return reference, successes, any_failures
```

(import `SYNTHETIC_PREFIX` from `runner.search`.)

`runner/diagnose.py` — add the six fields to `DiagnosisRuns` after `minimise_runs`; change `run_steps`:

```python
def run_steps(runner, original_order, victim, n, priority=None, shuffles=0, seed_base=0, order_given=False):
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
        # The starting order never failed for real: try valid shuffled orders (ADR-008).
        _label(runner, "shuffle")
        candidates, exhausted = distinct_shuffles(full, victim, shuffles, seed_base)
        seed, found, found_ref, tried, _ = search_orders(runner, candidates, victim)
        explore.update(shuffled_orders=tried, orders_exhausted=exhausted and found is None)
        if found is not None:
            order, reference = found, found_ref
            explore["reproducing_seed"] = seed

    _label(runner, "alone")
    if reference is None:
        alone_ref, alone_matches, alone_any = repeat_without_reference(runner, victim, n)
        if alone_ref is not None:
            return DiagnosisRuns(VICTIM_FAILS_ALONE, victim, order, alone_ref, [], [victim],
                                 n, alone_matches, alone_any, n, alone_matches, 0, **explore)
        # attempt_failures are all crashes/timeouts/skips here: no real failure was ever seen.
        return DiagnosisRuns(NOT_REPRODUCED, victim, order, None, [], order,
                             attempts, 0, attempt_failures, n, 0, 0,
                             infrastructure_failures=attempt_failures, **explore)
    alone_successes, alone_any = repeat(runner, [victim], victim, reference, n)
    if alone_successes >= 1:
        return DiagnosisRuns(VICTIM_FAILS_ALONE, victim, order, reference, [], [victim],
                             n, alone_successes, alone_any, n, alone_successes, 0, **explore)
    # … the existing search / minimise / verify block, unchanged, with `**explore` added to its
    # final DiagnosisRuns(...) call next to minimise_runs=minimise_runs.
```

`diagnose()` — new keyword arguments `shuffles: int = 31, seed: int = 0`. Before the record is created: if `original_order` was given, reject duplicates (`len(set(original_order)) != len(original_order)` → `DiagnoseInputError("the given order lists a test more than once")`) **before** Maven runs; after the runner exists, discover the project's tests and reject any given test not among them (`DiagnoseInputError(f"{test} in the given order is not one of the project's tests")`). Pass `shuffles=shuffles, seed_base=seed, order_given=original_order is not None` to `run_steps`. Add `"shuffles": shuffles, "seed_base": seed, "order_given": original_order is not None` to the record header.

Imports: `from runner.orders import distinct_shuffles, search_orders`; `from runner.verify import repeat, repeat_without_reference`.

- [ ] **Step 4: Run to verify they pass** — fake tests OK; real `test_f4_only_a_shuffled_order_reproduces` and `test_n3_is_not_reproduced_after_shuffles_and_alone` OK. Record F4's `reproducing_seed`, `shuffled_orders` and N3's run time in the evidence log.

- [ ] **Step 5: Mutation checks** — on copies: (a) skip the shuffle phase (`if False and reference is None …`) → `test_shuffle_finds_an_order…` and real F4 FAIL; (b) count duplicates (remove the `seen` check in `distinct_shuffles`) → `test_small_suite_is_exhausted_honestly` FAILS. Restore from copies.

- [ ] **Step 6: Full runner suite** — expect all OK; record the count. Docs: `runner/README.md` (status table: NOT_REPRODUCED now after shuffles + alone; record note), `docs/04-Implementation/diagnosis-runs.md`, evidence, GenAI log, register. Commit title `[M2] runner: try shuffled orders and always check the victim alone`.

---

### Task 3: Command options, summary lines, real reports for F4 and N3, docs

**Files:** Modify `runner/cli.py`, `runner/tests/test_cli.py`, docs.

**Interfaces:**
- Consumes: `diagnose(..., original_order, shuffles, seed)` (Task 2); report key `order_exploration` (M3's `assemble_report`, present once `DiagnosisRuns` has the fields).
- Produces: `read_order(path: Path, victim: TestIdentifier) -> List[TestIdentifier]` raising `OrderFileError(message)`; options `--order`, `--shuffles`, `--seed`; summary lines `orders:` and `bound:`.

- [ ] **Step 1: Write the failing tests** — in `runner/tests/test_cli.py`:

```python
from runner.cli import OrderFileError, read_order


class TestOrderFile(unittest.TestCase):
    def write(self, text, encoding="utf-8"):
        path = Path(tempfile.mkdtemp(prefix="flaketrace-order-")) / "order.txt"
        path.write_bytes(text.encode(encoding))
        return path

    def test_order_file_with_bom_crlf_and_spaces_is_read(self):
        path = self.write("﻿# CI order\r\npkg.PolluterTest#p  \r\n\r\npkg.VictimTest#v\r\n")
        self.assertEqual(read_order(path, V), [P, V])

    def test_bad_order_files_are_refused(self):
        for text in ("", "# only a comment\n", "pkg.PolluterTest\npkg.VictimTest#v\n",
                     "pkg.PolluterTest#p\npkg.PolluterTest#p\npkg.VictimTest#v\n", "pkg.PolluterTest#p\n"):
            with self.assertRaises(OrderFileError, msg=text):
                read_order(self.write(text), V)

    def test_missing_order_file_exits_2_before_maven(self):
        with mock.patch("runner.cli.diagnose") as diagnose:
            code, _, err = run_cli(["diagnose", "--project", str(project_with_pom()), "--victim", str(V),
                                    "--order", "no/such/order.txt"])
        self.assertEqual(code, 2)
        self.assertIn("order", err)
        diagnose.assert_not_called()

    def test_negative_shuffles_exits_2(self):
        with mock.patch("runner.cli.diagnose") as diagnose:
            code, _, err = run_cli(["diagnose", "--project", str(project_with_pom()), "--victim", str(V),
                                    "--shuffles", "-1"])
        self.assertEqual(code, 2)
        diagnose.assert_not_called()

    def test_options_reach_diagnose(self):
        order = self.write("pkg.PolluterTest#p\npkg.VictimTest#v\n")
        records = Path(tempfile.mkdtemp())
        with mock.patch("runner.cli.diagnose", return_value=runs(VICTIM_FAILS_ALONE, records / "r.jsonl")) as diagnose:
            run_cli(["diagnose", "--project", str(project_with_pom()), "--victim", str(V),
                     "--order", str(order), "--shuffles", "7", "--seed", "3"])
        kwargs = diagnose.call_args.kwargs
        self.assertEqual((kwargs["original_order"], kwargs["shuffles"], kwargs["seed"]), ([P, V], 7, 3))
```

Summary tests (in `TestReports`):

```python
    def test_summary_names_the_reproducing_shuffle(self):
        report = dict(self.report_with_resource(), order_exploration={
            "order_given": False, "shuffled_orders_tried": 9, "orders_exhausted": False,
            "seed_base": 0, "reproducing_seed": 17})
        self.assertIn("  orders:     reproduced in shuffled order (seed 17) after 9 shuffled orders",
                      summary(report, Path("r.report.json")).splitlines())

    def test_summary_of_not_reproduced_states_the_bound_and_not_proof(self):
        report = dict(self.report_with_resource(), polluters=[], shared_resource=None, outcome="UNRESOLVED",
                      unresolved_reason="NOT_REPRODUCED",
                      reproduction={"successes": 0, "n": 20, "lower": 0.0, "upper": 0.161},
                      victim_alone={"successes": 0, "n": 20},
                      order_exploration={"order_given": True, "shuffled_orders_tried": 31,
                                         "orders_exhausted": False, "seed_base": 0, "reproducing_seed": None})
        text = summary(report, Path("r.report.json")).splitlines()
        self.assertIn("  orders:     given order 20x, 31 distinct shuffled orders, alone 20x: never failed", text)
        self.assertIn("  bound:      failure rate in the given order < 0.161 (95% Wilson), not proof of reliability", text)
```

Real-run tests in `TestCliOnFixture`:

```python
    def test_f4_verified_through_a_shuffled_order(self):
        code, out, err, report = self.diagnose("odfixture.AlwaysEarlyVictimTest#expectsLateFlagUnset", 20)
        self.assertEqual(code, 0, err)
        self.assertEqual(report["outcome"], "VERIFIED")
        self.assertIsNotNone(report["order_exploration"]["reproducing_seed"])
        self.assertIn("reproduced in shuffled order (seed", out)

    def test_n3_not_reproduced_report(self):
        code, out, err, report = self.diagnose("odfixture.EnvDependentNegativeTest#onlyFailsUnderCI", 5)
        self.assertEqual(code, 0, err)
        self.assertEqual((report["outcome"], report["unresolved_reason"]), ("UNRESOLVED", "NOT_REPRODUCED"))
        self.assertIsNone(report["failure_signature"])
        self.assertEqual(report["order_exploration"]["shuffled_orders_tried"], 31)
        self.assertIn("not proof of reliability", out)
```

- [ ] **Step 2: Run to verify they fail** — `ImportError: cannot import name 'OrderFileError'`; real F4/N3 tests fail (exit 3 or no line).

- [ ] **Step 3: Implement in `runner/cli.py`**

```python
class OrderFileError(Exception):
    """A problem with the --order file (exit 2)."""


def read_order(path: Path, victim: TestIdentifier) -> List[TestIdentifier]:
    """One Class#method per line; blank and # lines ignored; BOM and CRLF allowed (ADR-008)."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise OrderFileError(f"cannot read --order file {path}: {error.strerror}")
    order: List[TestIdentifier] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not _VICTIM.fullmatch(line):
            raise OrderFileError(f"--order line {number} is not Class#method: {line!r}")
        class_name, _, method = line.partition("#")
        test = TestIdentifier(class_name, method)
        if test in order:
            raise OrderFileError(f"--order lists {test} twice (line {number})")
        order.append(test)
    if not order:
        raise OrderFileError(f"--order file {path} lists no tests")
    if victim not in order:
        raise OrderFileError(f"--order does not contain the victim {victim}")
    return order
```

In `main()` add `--order` (default `None`), `--shuffles` (`type=int`, default `31`), `--seed` (`type=int`, default `0`) and pass them to `run_diagnose(project, victim_id, n, records, order_path, shuffles, seed)`. In `run_diagnose`, after the victim and `pom.xml` checks: `if shuffles < 0: return _error("--shuffles must be >= 0", 2)`; read the order with `read_order` when given (catch `OrderFileError` → `_error(str(error), 2)`); call `diagnose(project, victim, n=n, record_dir=records, original_order=order, shuffles=shuffles, seed=seed)`.

In `summary()`, after the `minimised:` line:

```python
    explored = report.get("order_exploration")
    if explored and explored["reproducing_seed"] is not None:
        lines.append(f"  orders:     reproduced in shuffled order (seed {explored['reproducing_seed']}) "
                     f"after {explored['shuffled_orders_tried']} shuffled orders")
    if report["unresolved_reason"] == "NOT_REPRODUCED" and explored:
        exhausted = " (all possible)" if explored["orders_exhausted"] else ""
        lines.append(f"  orders:     given order {report['reproduction']['n']}x, "
                     f"{explored['shuffled_orders_tried']} distinct shuffled orders{exhausted}, "
                     f"alone {report['victim_alone']['n']}x: never failed")
        lines.append(f"  bound:      failure rate in the given order < {report['reproduction']['upper']:.3f} "
                     "(95% Wilson), not proof of reliability")
```

- [ ] **Step 4: Run to verify they pass** — `py -m unittest runner.tests.test_cli` → all OK incl. real F4 and N3. Run F4 and N3 by hand and copy both outputs into the evidence log.

- [ ] **Step 5: Mutation check** — on a copy, drop the `victim not in order` check in `read_order` → `test_bad_order_files_are_refused` FAILS; restore.

- [ ] **Step 6: Full suite + docs** — full runner suite OK (record count). Docs: `runner/README.md` (options, exit codes: NOT_REPRODUCED now exit 0 with report; F4/N3 outputs), `docs/04-Implementation/diagnose-cli.md`, demo plan (F4/N3 available; known limitations), iteration plan (new row "W14: ADR-008 runner side"), members, claims ledger (new claim for not-reproduced honesty + shuffles, status OPEN until CI), evidence/GenAI log, register; panel action register A5 note for M3 (F4/N3 widen scenarios — M3 decides). Commit title `[M2] runner: add --order/--shuffles and report F4 and N3 end to end`.

- [ ] **Step 7: Final review** — fresh reviewer agent on the whole branch; Critical/Important fixed test-first before the PR.
