import json
import tempfile
import unittest
from pathlib import Path

from eval.baseline import FailureSignature, RunOutcome, TestIdentifier
from eval.tests.fake_runner import FakeOrderRunner
from runner.recording import RecordingRunner

A = TestIdentifier("pkg.ATest", "a")
B = TestIdentifier("pkg.BTest", "b")
SIG = FailureSignature("java.lang.AssertionError", "pkg.BTest.b:3", "boom")


def b_fails_after_a(order, test):
    if test == B and A in order and order.index(A) < order.index(B):
        return RunOutcome(passed=False, failure_signature=SIG)
    return RunOutcome(passed=True)


class TestRecordingRunner(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp(prefix="flaketrace-rec-")) / "nested" / "run.jsonl"
        self.fake = FakeOrderRunner(b_fails_after_a)
        self.recorder = RecordingRunner(self.fake, self.path, {"victim": str(B), "n": 3})

    def lines(self):
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()]

    def test_note_is_written_into_run_lines_while_set(self):
        self.recorder.note = {"seed": 7}
        self.recorder.run_ordered([A])
        self.recorder.note = {}
        self.recorder.run_ordered([A])
        _, first, second = self.lines()
        self.assertEqual((first["seed"], "seed" in second), (7, False))

    def test_header_is_written_first(self):
        self.assertEqual(self.lines(), [{"type": "header", "victim": "pkg.BTest#b", "n": 3}])

    def test_each_run_is_one_labelled_line_and_results_pass_through(self):
        self.recorder.step = "search"
        results = self.recorder.run_ordered([A, B])
        self.recorder.step = "alone"
        self.recorder.run_ordered([B])
        self.assertFalse(results[B].passed)
        self.assertEqual(self.fake.calls, [[A, B], [B]])
        header, first, second = self.lines()
        self.assertEqual(first["step"], "search")
        self.assertEqual(first["order"], ["pkg.ATest#a", "pkg.BTest#b"])
        self.assertEqual(first["outcomes"][0], {"test": "pkg.ATest#a", "passed": True})
        self.assertEqual(
            first["outcomes"][1]["failure_signature"],
            {"exception_type": "java.lang.AssertionError", "message": "boom", "stack_trace": "pkg.BTest.b:3"},
        )
        self.assertEqual(second["step"], "alone")
        self.assertTrue(second["outcomes"][0]["passed"])
        self.assertIn("seconds", second)
        self.assertIn("started", second)


if __name__ == "__main__":
    unittest.main()
