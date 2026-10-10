import os
import shutil
import tempfile
import unittest
from pathlib import Path

from eval.baseline import TestIdentifier
from runner.discovery import discover_order, is_surefire_test_class, test_class_names
from runner.order_runner import OrderRunner, maven_test_classpath

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "od-fixture"


class TestClassSelection(unittest.TestCase):
    def test_surefire_default_patterns(self):
        for name in ("TestFoo", "FooTest", "FooTests", "FooTestCase"):
            self.assertTrue(is_surefire_test_class(name), name)
        for name in ("Foo", "FooTestHelper", "FooTest$Inner", "Testing$1"):
            self.assertFalse(is_surefire_test_class(name), name)

    def test_class_names_are_fully_qualified_and_sorted(self):
        root = Path(tempfile.mkdtemp(prefix="flaketrace-classes-"))
        for rel in ("b/ZTest.class", "a/x/YTest.class", "a/Helper.class", "a/x/YTest$1.class",
                    "a/notes.txt", "TestTop.class"):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes(b"")
        self.assertEqual(test_class_names(root), ["TestTop", "a.x.YTest", "b.ZTest"])

    def test_missing_test_classes_folder_gives_no_classes(self):
        self.assertEqual(test_class_names(Path(tempfile.mkdtemp()) / "target" / "test-classes"), [])


class TestDiscoveryOnFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [tool for tool in ("java", "javac", "mvn") if shutil.which(tool) is None]
        if missing:
            if os.environ.get("FLAKETRACE_REQUIRE_JVM"):
                raise RuntimeError(f"FLAKETRACE_REQUIRE_JVM is set but {missing} not on PATH")
            raise unittest.SkipTest(f"{missing} not on PATH")
        runner = OrderRunner(maven_test_classpath(FIXTURE), working_dir=FIXTURE)
        cls.order = discover_order(runner, FIXTURE / "target" / "test-classes")

    def test_all_fixture_methods_in_alphabetical_class_order(self):
        # 16, not 13: ADR-008 added AlwaysEarlyVictimTest/ZzzLatePolluterTest (F4) and
        # EnvDependentNegativeTest (N3), chosen to sort first and last/near-last respectively.
        self.assertEqual(len(self.order), 16)
        classes = [t.class_name for t in self.order]
        self.assertEqual(classes, sorted(classes))
        self.assertEqual(self.order[:2], [
            TestIdentifier("odfixture.AlwaysEarlyVictimTest", "expectsLateFlagUnset"),
            TestIdentifier("odfixture.ConfigPolluterTest", "pollute"),
        ])
        self.assertEqual(self.order[-1], TestIdentifier("odfixture.ZzzLatePolluterTest", "setLateFlag"))

    def test_class_with_two_methods_lists_both(self):
        math = [t.method for t in self.order if t.class_name == "odfixture.MathUtilTest"]
        self.assertEqual(sorted(math), ["addsTwoNumbers", "squaresANumber"])

    def test_class_without_tests_or_unloadable_is_left_out(self):
        runner = OrderRunner(maven_test_classpath(FIXTURE), working_dir=FIXTURE)
        self.assertEqual(runner.list_methods(["odfixture.Config", "odfixture.NoSuchTest"]), [])


if __name__ == "__main__":
    unittest.main()
