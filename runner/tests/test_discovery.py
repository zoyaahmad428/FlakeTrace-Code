import os
import re
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

    def test_every_fixture_test_method_once_in_alphabetical_class_order(self):
        # Expected set read from the fixture's sources (every @Test method), independent of the
        # discovery code under test, so adding a fixture case does not break this.
        expected = set()
        for source in (FIXTURE / "src" / "test" / "java").rglob("*.java"):
            text = source.read_text(encoding="utf-8")
            package = re.search(r"^package\s+([\w.]+);", text, re.M).group(1)
            for method in re.findall(r"@Test\s+public\s+void\s+(\w+)\s*\(", text):
                expected.add(TestIdentifier(f"{package}.{source.stem}", method))
        self.assertGreater(len(expected), 0)
        self.assertEqual(len(self.order), len(set(self.order)))
        self.assertEqual(set(self.order), expected)
        classes = [t.class_name for t in self.order]
        self.assertEqual(classes, sorted(classes))

    def test_class_with_two_methods_lists_both(self):
        math = [t.method for t in self.order if t.class_name == "odfixture.MathUtilTest"]
        self.assertEqual(sorted(math), ["addsTwoNumbers", "squaresANumber"])

    def test_class_without_tests_or_unloadable_is_left_out(self):
        runner = OrderRunner(maven_test_classpath(FIXTURE), working_dir=FIXTURE)
        self.assertEqual(runner.list_methods(["odfixture.Config", "odfixture.NoSuchTest"]), [])


if __name__ == "__main__":
    unittest.main()
