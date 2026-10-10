import json
import os
import platform
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from eval.baseline import FailureSignature, RunOutcome, TestIdentifier
from eval.tests.fake_runner import FakeOrderRunner
from runner.recording import RecordingRunner
from runner.diagnose import (
    NO_SINGLE_POLLUTER,
    NOT_REPRODUCED,
    POLLUTER_FOUND,
    VICTIM_FAILS_ALONE,
    DiagnoseInputError,
    diagnose,
    environment,
    run_steps,
)

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "od-fixture"

A = TestIdentifier("pkg.ATest", "a")
B = TestIdentifier("pkg.BTest", "b")
V = TestIdentifier("pkg.VictimTest", "v")
LATER = TestIdentifier("pkg.ZTest", "z")
REF = FailureSignature("java.lang.AssertionError", "pkg.VictimTest.v:5", "expected 0")
PASS = RunOutcome(passed=True)
FAIL = RunOutcome(passed=False, failure_signature=REF)


def victim_fails_when(condition):
    return FakeOrderRunner(lambda order, test: FAIL if test == V and condition(order) else PASS)


class TestRunSteps(unittest.TestCase):
    def test_single_polluter_found_and_verified(self):
        runner = victim_fails_when(lambda order: B in order)
        runs = run_steps(runner, [A, B, V, LATER], V, n=4)
        self.assertEqual(runs.status, POLLUTER_FOUND)
        self.assertEqual(runs.original_order, [A, B, V])
        self.assertEqual(runs.reference_signature, REF)
        self.assertEqual(runs.polluters, [B])
        self.assertEqual(runs.sequence, [B, V])
        self.assertEqual((runs.sequence_n, runs.sequence_successes, runs.sequence_any_failures), (4, 4, 4))
        self.assertEqual((runs.alone_n, runs.alone_successes), (4, 0))
        self.assertEqual(runs.search_runs, 2)
        self.assertEqual(len(runner.calls), 1 + 4 + 2 + 4)

    def test_victim_failing_alone_stops_before_the_search(self):
        runner = victim_fails_when(lambda order: True)
        runs = run_steps(runner, [A, V], V, n=3)
        self.assertEqual(runs.status, VICTIM_FAILS_ALONE)
        self.assertEqual((runs.polluters, runs.sequence), ([], [V]))
        self.assertEqual((runs.sequence_n, runs.sequence_successes, runs.sequence_any_failures), (3, 3, 3))
        self.assertEqual((runs.alone_n, runs.alone_successes, runs.search_runs), (3, 3, 0))
        self.assertEqual(len(runner.calls), 1 + 3)

    def test_two_polluters_needed_are_minimised_and_verified(self):
        runner = victim_fails_when(lambda order: A in order and B in order)
        runs = run_steps(runner, [A, B, V], V, n=2)
        self.assertEqual(runs.status, POLLUTER_FOUND)
        self.assertEqual((runs.polluters, runs.sequence), ([A, B], [A, B, V]))
        self.assertEqual((runs.sequence_n, runs.sequence_successes), (2, 2))
        self.assertEqual((runs.alone_n, runs.alone_successes, runs.search_runs, runs.minimise_runs), (2, 0, 2, 3))
        self.assertEqual(len(runner.calls), 1 + 2 + 2 + (1 + 2) + 2)

    def test_flaky_failure_is_not_blamed_on_the_whole_prefix(self):
        # The victim fails only in the very first run (the reproduce step), never again.
        calls = []
        runner = FakeOrderRunner(lambda order, test: (calls.append(1) or FAIL) if test == V and not calls else PASS)
        runs = run_steps(runner, [A, B, LATER, V], V, n=2)
        self.assertEqual(runs.status, NO_SINGLE_POLLUTER)
        self.assertEqual(runs.polluters, [])
        self.assertEqual(runs.minimise_runs, 1)

    def test_one_test_prefix_that_passed_in_the_search_blames_nothing(self):
        calls = []
        runner = FakeOrderRunner(lambda order, test: (calls.append(1) or FAIL) if test == V and not calls else PASS)
        runs = run_steps(runner, [A, V], V, n=2)
        self.assertEqual(runs.status, NO_SINGLE_POLLUTER)
        self.assertEqual((runs.polluters, runs.minimise_runs), ([], 0))

    def test_minimise_runs_are_recorded_as_their_own_step(self):
        record = Path(tempfile.mkdtemp(prefix="flaketrace-rec-")) / "r.jsonl"
        runner = RecordingRunner(victim_fails_when(lambda order: A in order and B in order), record, {})
        run_steps(runner, [A, LATER, B, V], V, n=1)
        steps = [json.loads(line)["step"] for line in record.read_text(encoding="utf-8").splitlines()[1:]]
        self.assertIn("minimise", steps)
        self.assertEqual(steps.index("minimise"), steps.index("search") + steps.count("search"))

    def test_single_polluter_does_not_minimise(self):
        runs = run_steps(victim_fails_when(lambda order: B in order), [A, B, V], V, n=2)
        self.assertEqual(runs.minimise_runs, 0)

    def test_never_failing_without_shuffles_runs_reproduce_and_alone_only(self):
        runner = victim_fails_when(lambda order: False)
        runs = run_steps(runner, [A, V], V, n=3)
        self.assertEqual(runs.status, NOT_REPRODUCED)
        self.assertIsNone(runs.reference_signature)
        self.assertEqual((runs.sequence, runs.sequence_n, runs.sequence_successes), ([A, V], 3, 0))
        self.assertEqual((runs.alone_n, runs.alone_successes, runs.search_runs), (3, 0, 0))
        self.assertEqual(len(runner.calls), 3 + 3)

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
        # Cut orders of three one-method classes: [V], [A,V], [B,V], [A,B,V], [B,A,V]; the starting
        # order [A,B,V] already ran, so 4 are new.
        self.assertEqual(runs.shuffled_orders, 4)
        self.assertTrue(runs.orders_exhausted)

    def test_failing_alone_without_a_reference_is_victim_fails_alone(self):
        runner = FakeOrderRunner(lambda order, test: FAIL if test == V and order == [V] else PASS)
        runs = run_steps(runner, [A, V], V, n=3, shuffles=0)
        self.assertEqual(runs.status, VICTIM_FAILS_ALONE)
        self.assertEqual(runs.reference_signature, REF)
        self.assertEqual((runs.alone_n, runs.alone_successes), (3, 3))
        # The only order that failed is the victim alone; the starting order never did.
        self.assertEqual(runs.original_order, [V])

    def test_crash_only_alone_and_shuffles_are_counted_not_called_never_failed(self):
        timeout = RunOutcome(passed=False, failure_signature=FailureSignature("flaketrace.Timeout", "", "120s"))
        crash = RunOutcome(passed=False, failure_signature=FailureSignature("flaketrace.JvmCrash", "", "code 1"))
        def outcome(order, test):
            if test != V or order == [A, B, V]:
                return PASS
            return timeout if order == [V] else crash
        runs = run_steps(FakeOrderRunner(outcome), [A, B, V], V, n=3, shuffles=31)
        self.assertEqual(runs.status, NOT_REPRODUCED)
        self.assertEqual(runs.infrastructure_failures, 0)
        self.assertEqual(runs.shuffle_infrastructure_failures, runs.shuffled_orders)
        self.assertEqual(runs.alone_infrastructure_failures, 3)

    def test_unknown_test_in_a_given_order_is_refused_and_says_why(self):
        project = Path(tempfile.mkdtemp(prefix="flaketrace-project-"))
        with mock.patch("runner.diagnose.maven_test_classpath", return_value=[]), \
                mock.patch("runner.diagnose.OrderRunner"), \
                mock.patch("runner.diagnose.discover_order", return_value=[A, V]):
            with self.assertRaises(DiagnoseInputError) as raised:
                diagnose(project, V, original_order=[LATER, A, V], record_dir=tempfile.mkdtemp())
        self.assertIn("1 test(s)", str(raised.exception))
        self.assertIn(str(LATER), str(raised.exception))
        self.assertIn("Surefire", str(raised.exception))

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
        self.assertEqual(len(runner.calls), 2 + 2)

    def test_shuffle_runs_record_their_seed(self):
        record = Path(tempfile.mkdtemp(prefix="flaketrace-rec-")) / "r.jsonl"
        runner = RecordingRunner(victim_fails_when(lambda order: False), record, {})
        run_steps(runner, [A, B, V], V, n=1, shuffles=5, seed_base=40)
        lines = [json.loads(l) for l in record.read_text(encoding="utf-8").splitlines()[1:]]
        shuffles = [l for l in lines if l["step"] == "shuffle"]
        self.assertTrue(shuffles and all(isinstance(l["seed"], int) and l["seed"] >= 40 for l in shuffles))
        self.assertTrue(all("seed" not in l for l in lines if l["step"] != "shuffle"))

    def test_given_order_with_a_duplicate_is_refused_before_maven_runs(self):
        with self.assertRaises(DiagnoseInputError):
            diagnose(Path("does-not-exist"), V, original_order=[A, A, V])

    def test_bad_input_is_rejected_before_any_run(self):
        runner = victim_fails_when(lambda order: True)
        with self.assertRaises(DiagnoseInputError):
            run_steps(runner, [A, B], V, n=3)
        with self.assertRaises(DiagnoseInputError):
            run_steps(runner, [A, V], V, n=0)
        self.assertEqual(runner.calls, [])

    def test_victim_first_in_order_has_no_candidates(self):
        outcomes = [FAIL] + [PASS] * 10
        runner = FakeOrderRunner(lambda order, test: outcomes.pop(0))
        runs = run_steps(runner, [V, A], V, n=2)
        self.assertEqual(runs.status, NO_SINGLE_POLLUTER)
        self.assertEqual((runs.search_runs, runs.sequence), (0, [V]))

    def test_explicit_order_without_the_victim_fails_before_maven_runs(self):
        with self.assertRaises(DiagnoseInputError):
            diagnose(Path("does-not-exist"), V, original_order=[A, B])

    def test_record_folder_inside_the_project_is_refused_before_maven_runs(self):
        project = Path(tempfile.mkdtemp(prefix="flaketrace-project-"))
        with self.assertRaises(DiagnoseInputError):
            diagnose(project, V, original_order=[V], record_dir=project / "records")

    def test_record_folder_that_is_a_file_is_refused_before_maven_runs(self):
        project = Path(tempfile.mkdtemp(prefix="flaketrace-project-"))
        a_file = Path(tempfile.mkdtemp(prefix="flaketrace-records-")) / "records.txt"
        a_file.write_text("not a folder", encoding="utf-8")
        with self.assertRaises(DiagnoseInputError):
            diagnose(project, V, original_order=[V], record_dir=a_file)

    def test_crash_only_original_order_counts_as_failed_but_not_reproduced(self):
        crash = RunOutcome(passed=False, failure_signature=FailureSignature("flaketrace.JvmCrash", "", "code 1"))
        runner = FakeOrderRunner(lambda order, test: crash if test == V else PASS)
        runs = run_steps(runner, [A, V], V, n=3)
        self.assertEqual(runs.status, NOT_REPRODUCED)
        self.assertEqual((runs.sequence_n, runs.sequence_successes, runs.sequence_any_failures), (3, 0, 3))
        self.assertEqual(runs.infrastructure_failures, 3)


class TestEnvironment(unittest.TestCase):
    """Panel action A7: each execution record names the project's commit and the OS."""

    def test_folder_without_git_records_unknown_commit_and_still_names_the_os(self):
        folder = Path(tempfile.mkdtemp(prefix="flaketrace-nogit-"))
        env = environment(folder)
        self.assertEqual((env["project_commit"], env["project_dirty"]), (None, None))
        self.assertEqual(env["os"], platform.platform())

    @unittest.skipUnless(shutil.which("git"), "git not on PATH")
    def test_git_project_records_its_commit_and_whether_it_has_uncommitted_changes(self):
        repo = Path(tempfile.mkdtemp(prefix="flaketrace-git-"))
        git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "A.java").write_text("class A {}", encoding="utf-8")
        subprocess.run(git + ["add", "A.java"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "one"], check=True)
        head = subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual((environment(repo)["project_commit"], environment(repo)["project_dirty"]), (head, False))
        (repo / "A.java").write_text("class A { int x; }", encoding="utf-8")
        self.assertTrue(environment(repo)["project_dirty"])


class TestDiagnoseOnFixture(unittest.TestCase):
    """Real JVM runs on fixtures/od-fixture, checked against ground_truth.json."""

    @classmethod
    def setUpClass(cls):
        missing = [tool for tool in ("java", "javac", "mvn") if shutil.which(tool) is None]
        if missing:
            if os.environ.get("FLAKETRACE_REQUIRE_JVM"):
                raise RuntimeError(f"FLAKETRACE_REQUIRE_JVM is set but {missing} not on PATH")
            raise unittest.SkipTest(f"{missing} not on PATH")
        cls.records = tempfile.mkdtemp(prefix="flaketrace-records-")
        cls.truth = {c["id"]: c for c in json.loads((FIXTURE / "ground_truth.json").read_text())["cases"]}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.records, ignore_errors=True)

    def diagnose_case(self, case_id, n):
        victim = TestIdentifier.from_dict(self.truth[case_id]["victim"])
        runs = diagnose(FIXTURE, victim, n=n, record_dir=self.records)
        self.assertTrue(runs.source_integrity.passed, runs.source_integrity.details)
        self.assertTrue(Path(runs.execution_record).exists())
        return runs

    def expected_polluters(self, case_id):
        return [TestIdentifier.from_dict(p) for p in self.truth[case_id]["polluters"]]

    def test_f1_single_static_field_polluter(self):
        runs = self.diagnose_case("F1", n=20)
        self.assertEqual(runs.status, POLLUTER_FOUND)
        self.assertEqual(runs.polluters, self.expected_polluters("F1"))
        self.assertEqual((runs.sequence_successes, runs.sequence_n), (20, 20))
        self.assertEqual((runs.alone_successes, runs.alone_n), (0, 20))
        record = Path(runs.execution_record).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(record), 1 + 1 + 20 + runs.search_runs + 20)
        header = json.loads(record[0])
        self.assertRegex(header["project_commit"], r"^[0-9a-f]{40}$")
        self.assertIsInstance(header["project_dirty"], bool)
        self.assertEqual(header["os"], platform.platform())

    def test_f2_single_system_property_polluter(self):
        runs = self.diagnose_case("F2", n=5)
        self.assertEqual(runs.status, POLLUTER_FOUND)
        self.assertEqual(runs.polluters, self.expected_polluters("F2"))
        self.assertEqual(runs.sequence_successes, 5)

    def test_f3_two_polluters_are_found_by_minimisation(self):
        runs = self.diagnose_case("F3", n=5)
        self.assertEqual(runs.status, POLLUTER_FOUND)
        self.assertEqual(runs.polluters, self.expected_polluters("F3"))
        # One search run per earlier test; counted from the order, so new fixture cases don't break it.
        self.assertEqual(runs.search_runs, len(runs.original_order) - 1)
        self.assertGreater(runs.minimise_runs, 0)
        self.assertEqual(runs.sequence_successes, 5)

    def test_n1_fails_alone(self):
        runs = self.diagnose_case("N1", n=20)
        self.assertEqual(runs.status, VICTIM_FAILS_ALONE)
        self.assertEqual((runs.alone_successes, runs.alone_n), (20, 20))

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

    def test_n2_intermittent_failure_fails_alone_and_blames_no_polluter(self):
        # N2 fails ~50% of runs (Random.nextBoolean, PR #14); 20 runs with no failure ~ 1e-6.
        runs = self.diagnose_case("N2", n=20)
        self.assertEqual(runs.status, VICTIM_FAILS_ALONE)
        self.assertEqual(runs.polluters, [])
        self.assertGreaterEqual(runs.alone_successes, 1)


if __name__ == "__main__":
    unittest.main()
