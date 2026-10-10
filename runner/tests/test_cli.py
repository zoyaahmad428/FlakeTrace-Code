import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from eval.baseline import FailureSignature, TestIdentifier
from eval.report import assemble_report
from runner.cli import OrderFileError, combine_fields, main, read_order, resource_fields, summary
from runner.diagnose import (NO_SINGLE_POLLUTER, POLLUTER_FOUND, VICTIM_FAILS_ALONE, DiagnoseInputError,
                             DiagnosisRuns)
from runner.integrity import SourceIntegrity
from runner.order_runner import ToolError

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "fixtures" / "od-fixture"

V = TestIdentifier("pkg.VictimTest", "v")
P = TestIdentifier("pkg.PolluterTest", "p")
REF = FailureSignature("java.lang.AssertionError", "pkg.VictimTest.v:5", "expected <N>")


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def project_with_pom():
    project = Path(tempfile.mkdtemp(prefix="flaketrace-cli-project-"))
    (project / "pom.xml").write_text("<project/>", encoding="utf-8")
    return project


def runs(status, record, **overrides):
    fields = dict(
        status=status, victim=V, original_order=[P, V], reference_signature=REF,
        polluters=[], sequence=[V], sequence_n=20, sequence_successes=20,
        sequence_any_failures=20, alone_n=20, alone_successes=20, search_runs=0,
        source_integrity=SourceIntegrity(True, "3 files hashed; all identical"),
        execution_record=str(record),
    )
    fields.update(overrides)
    return DiagnosisRuns(**fields)


class TestInputErrors(unittest.TestCase):
    def test_malformed_victims_exit_2(self):
        for victim in ("pkg.VictimTest", "pkg.VictimTest#", "#v", " pkg.VictimTest#v", "pkg.VictimTest#v ",
                       "pkg.VictimTest#v:x", "pkg.VictimTest#a#b", "pkg.Victim Test#v", "pkg.VictimTest#<v>"):
            with mock.patch("runner.cli.diagnose") as diagnose:
                code, _, err = run_cli(["diagnose", "--project", str(FIXTURE), "--victim", victim])
            self.assertEqual(code, 2, victim)
            self.assertIn("Class#method", err)
            diagnose.assert_not_called()

    def test_missing_project_exits_2(self):
        with mock.patch("runner.cli.diagnose") as diagnose:
            code, _, err = run_cli(["diagnose", "--project", "no/such/project", "--victim", "a.B#c"])
        self.assertEqual(code, 2)
        self.assertIn("no pom.xml", err)
        diagnose.assert_not_called()

    def test_n_below_one_exits_2_before_maven(self):
        code, _, err = run_cli(["diagnose", "--project", str(FIXTURE), "--victim", "a.B#c", "--n", "0"])
        self.assertEqual(code, 2)
        self.assertIn("n must be >= 1", err)

    def test_records_inside_the_project_exits_2_before_maven(self):
        code, _, err = run_cli(["diagnose", "--project", str(FIXTURE), "--victim", "a.B#c",
                                "--records", str(FIXTURE / "records")])
        self.assertEqual(code, 2)
        self.assertIn("inside the analysed project", err)

    def test_missing_subcommand_is_a_usage_error(self):
        with self.assertRaises(SystemExit) as raised, redirect_stderr(io.StringIO()):
            main([])
        self.assertEqual(raised.exception.code, 2)


class TestToolErrors(unittest.TestCase):
    def check(self, error, expected_code, expected_text):
        with mock.patch("runner.cli.diagnose", side_effect=error):
            code, _, err = run_cli(["diagnose", "--project", str(project_with_pom()), "--victim", "a.B#c"])
        self.assertEqual(code, expected_code)
        self.assertTrue(err.startswith("error: "), err)
        self.assertIn(expected_text, err)
        self.assertNotIn("Traceback", err)

    def test_victim_not_among_the_tests_exits_2(self):
        self.check(DiagnoseInputError("victim a.B#c is not in the original order"), 2, "a.B#c")

    def test_maven_failure_exits_1(self):
        self.check(subprocess.CalledProcessError(1, ["C:/tools/mvn.cmd", "-B"]), 1, "mvn.cmd failed")

    def test_missing_tool_exits_1(self):
        self.check(ToolError("'javac' not found on PATH"), 1, "'javac' not found on PATH")

    def test_discovery_timeout_exits_1(self):
        self.check(subprocess.TimeoutExpired(["java", "FtHarness", "--list"], 120), 1, "timed out")

    def test_internal_errors_are_not_hidden_as_input_or_tool_errors(self):
        # ADR-005: unexpected exceptions keep their traceback. These are internal, not the user's input.
        for internal in (ValueError("order contains the same test more than once"),
                         UnicodeDecodeError("utf-8", bytes([0xFF]), 0, 1, "bad byte"),
                         RecursionError("maximum recursion depth exceeded")):
            with mock.patch("runner.cli.diagnose", side_effect=internal):
                with self.assertRaises(type(internal)), redirect_stderr(io.StringIO()):
                    main(["diagnose", "--project", str(project_with_pom()), "--victim", "a.B#c"])

    def test_extractor_failure_exits_1(self):
        project = project_with_pom()  # no target/ folders, so Project() raises ExtractError(..., 2)
        found = runs(POLLUTER_FOUND, project / "r.jsonl", polluters=[P], sequence=[P, V],
                     alone_successes=0, search_runs=1)
        with mock.patch("runner.cli.diagnose", return_value=found):
            code, _, err = run_cli(["diagnose", "--project", str(project), "--victim", str(V)])
        self.assertEqual(code, 1)
        self.assertIn("error: resource evidence failed", err)


def pair(polluter, *resource_ids, depth=1):
    location = {"class": polluter.class_name, "method": polluter.method, "bytecode_offset": 1, "depth": depth}
    return {
        "polluter": polluter.to_dict(), "victim": V.to_dict(),
        "edges": [{"resource_id": rid, "resource": {"kind": "static-field", "class": rid.split("#")[0],
                                                     "field": rid.split("#")[1]},
                   "polluter_write_locations": [location], "victim_read_locations": [dict(location, method="v")]}
                  for rid in resource_ids],
        "limitations": ["Static analysis only; no runtime evidence (Iteration 2)."],
    }


Q = TestIdentifier("pkg.SecondPolluterTest", "q")


class TestCombineFields(unittest.TestCase):
    def test_one_polluter_is_unchanged(self):
        from evidence.extract import report_fields
        single = pair(P, "pkg.T#flagA")
        self.assertEqual(combine_fields([single]), report_fields(single))

    def test_every_polluter_with_an_edge_shows_the_first_and_names_the_rest(self):
        fields = combine_fields([pair(P, "pkg.T#flagA"), pair(Q, "pkg.T#flagB")])
        self.assertEqual(fields["shared_resource"], {"kind": "static-field", "class": "pkg.T", "field": "flagA"})
        self.assertEqual(fields["polluter_write_location"]["class"], "pkg.PolluterTest")
        self.assertIn("Polluter pkg.SecondPolluterTest#q: shared resource pkg.T#flagB is not shown in this report",
                      fields["limitations"])
        self.assertEqual(fields["limitations"].count("Static analysis only; no runtime evidence (Iteration 2)."), 1)

    def test_second_polluter_without_edge_shows_no_resource(self):
        fields = combine_fields([pair(P, "pkg.T#flagA"), pair(Q)])
        self.assertIsNone(fields["shared_resource"])
        self.assertIsNone(fields["polluter_write_location"])
        self.assertIsNone(fields["victim_read_location"])
        self.assertIn("No polluter-write/victim-read resource edge was found for polluter pkg.SecondPolluterTest#q",
                      fields["limitations"])
        self.assertIn("Polluter pkg.PolluterTest#p: shared resource pkg.T#flagA was found, "
                      "but not every polluter has evidence", fields["limitations"])

    def test_resource_written_by_both_polluters_is_not_called_hidden(self):
        fields = combine_fields([pair(P, "pkg.T#flag"), pair(Q, "pkg.T#flag")])
        self.assertEqual(fields["shared_resource"]["field"], "flag")
        self.assertFalse(any("pkg.T#flag is not shown" in line for line in fields["limitations"]), fields["limitations"])

    def test_deep_evidence_of_a_later_polluter_is_named_with_its_depth(self):
        fields = combine_fields([pair(P, "pkg.T#a"), pair(Q, "pkg.T#b", depth=5)])
        self.assertIn("Polluter pkg.SecondPolluterTest#q: shared resource pkg.T#b is not shown in this report "
                      "(evidence at depth 5, above the default 2)", fields["limitations"])

    def test_mixed_evidence_report_does_not_also_say_no_edge_was_found(self):
        fields = combine_fields([pair(P, "pkg.T#a"), pair(Q)])
        self.assertTrue(fields["any_edge_found"])
        runs_ = runs(POLLUTER_FOUND, "r.jsonl", polluters=[P, Q], sequence=[P, Q, V], alone_successes=0)
        report = assemble_report(runs_, fields)
        self.assertEqual((report["outcome"], report["unresolved_reason"]), ("UNRESOLVED", "NO_SUPPORTED_RESOURCE_EVIDENCE"))
        self.assertNotIn("No polluter-write/victim-read resource edge was found by static analysis.",
                         report["limitations"])

    def test_resource_fields_asks_analyse_pair_once_per_polluter(self):
        project = project_with_pom()
        for folder in ("classes", "test-classes"):
            (project / "target" / folder).mkdir(parents=True)
        found = runs(POLLUTER_FOUND, project / "r.jsonl", polluters=[P, Q], sequence=[P, Q, V])
        with mock.patch("runner.cli.analyse_pair", side_effect=[pair(P, "pkg.T#a"), pair(Q, "pkg.T#b")]) as analyse:
            fields = resource_fields(project, found)
        self.assertEqual([c.args[1:] for c in analyse.call_args_list], [(str(P), str(V)), (str(Q), str(V))])
        self.assertEqual(fields["shared_resource"]["field"], "a")

    def test_extra_resource_of_a_later_polluter_is_named_once(self):
        fields = combine_fields([pair(P, "pkg.T#a"), pair(Q, "pkg.T#b", "pkg.T#c")])
        self.assertEqual(sum("pkg.T#c" in line for line in fields["limitations"]), 1, fields["limitations"])

    def test_first_polluter_without_edge_shows_no_resource(self):
        fields = combine_fields([pair(P), pair(Q, "pkg.T#flagB")])
        self.assertIsNone(fields["shared_resource"])
        self.assertIn("No polluter-write/victim-read resource edge was found for polluter pkg.PolluterTest#p",
                      fields["limitations"])


class TestOrderFile(unittest.TestCase):
    def write(self, text, encoding="utf-8"):
        path = Path(tempfile.mkdtemp(prefix="flaketrace-order-")) / "order.txt"
        path.write_bytes(text.encode(encoding))
        return path

    def test_order_file_with_bom_crlf_and_spaces_is_read(self):
        path = self.write("\ufeff# CI order\r\npkg.PolluterTest#p  \r\n\r\npkg.VictimTest#v\r\n")
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


class TestReports(unittest.TestCase):
    def test_victim_fails_alone_writes_a_report_and_skips_the_extractor(self):
        records = Path(tempfile.mkdtemp(prefix="flaketrace-cli-records-"))
        record = records / "20261010T000000Z-pkg.VictimTest#v.jsonl"
        with mock.patch("runner.cli.diagnose", return_value=runs(VICTIM_FAILS_ALONE, record)), \
                mock.patch("runner.cli.analyse_pair") as analyse:
            code, out, _ = run_cli(["diagnose", "--project", str(project_with_pom()), "--victim", str(V)])
        self.assertEqual(code, 0)
        analyse.assert_not_called()
        report_path = records / "20261010T000000Z-pkg.VictimTest#v.report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual((report["outcome"], report["unresolved_reason"]), ("UNRESOLVED", "VICTIM_FAILS_ALONE"))
        self.assertEqual(report["execution_record_reference"], str(record))
        self.assertTrue(out.startswith("UNRESOLVED (VICTIM_FAILS_ALONE)  pkg.VictimTest#v"), out)
        self.assertIn("alone: 20/20", out)
        self.assertIn(str(report_path), out)
        out.encode("ascii")  # the summary must print on any console

    def test_summary_names_the_minimisation_when_ddmin_ran(self):
        report = dict(self.report_with_resource(), polluters=[P.to_dict(), Q.to_dict()])
        text = summary(report, Path("r.report.json"), minimised=(12, 10))
        self.assertIn("  minimised:  12 earlier tests -> 2 polluters in 10 runs "
                      "(1-minimal, not necessarily the minimum)", text.splitlines())
        self.assertNotIn("minimised:", summary(report, Path("r.report.json")))

    def test_command_shows_the_minimisation_only_when_ddmin_found_polluters(self):
        records = Path(tempfile.mkdtemp(prefix="flaketrace-cli-records-"))
        earlier = [TestIdentifier(f"pkg.T{i}Test", "t") for i in range(10)]
        found = runs(POLLUTER_FOUND, records / "r.jsonl", original_order=earlier + [P, Q, V],
                     polluters=[P, Q], sequence=[P, Q, V], alone_successes=0, search_runs=12, minimise_runs=10)
        fields = combine_fields([pair(P, "pkg.T#a"), pair(Q, "pkg.T#b")])
        with mock.patch("runner.cli.diagnose", return_value=found), \
                mock.patch("runner.cli.resource_fields", return_value=fields):
            code, out, _ = run_cli(["diagnose", "--project", str(project_with_pom()), "--victim", str(V)])
        self.assertEqual(code, 0)
        self.assertIn("minimised:  12 earlier tests -> 2 polluters in 10 runs", out)
        single = runs(POLLUTER_FOUND, records / "s.jsonl", polluters=[P], sequence=[P, V], alone_successes=0)
        with mock.patch("runner.cli.diagnose", return_value=single), \
                mock.patch("runner.cli.resource_fields", return_value=combine_fields([pair(P, "pkg.T#a")])):
            _, out, _ = run_cli(["diagnose", "--project", str(project_with_pom()), "--victim", str(V)])
        self.assertNotIn("minimised:", out)

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

    def test_summary_says_discovered_order_when_no_order_was_given(self):
        report = dict(self.report_with_resource(), polluters=[], shared_resource=None, outcome="UNRESOLVED",
                      unresolved_reason="NOT_REPRODUCED",
                      reproduction={"successes": 0, "n": 20, "lower": 0.0, "upper": 0.161},
                      victim_alone={"successes": 0, "n": 20},
                      order_exploration={"order_given": False, "shuffled_orders_tried": 31,
                                         "orders_exhausted": False, "seed_base": 0, "reproducing_seed": None})
        text = summary(report, Path("r.report.json")).splitlines()
        self.assertIn("  orders:     discovered order 20x, 31 distinct shuffled orders, alone 20x: never failed", text)
        self.assertIn("  bound:      failure rate in the discovered order < 0.161 (95% Wilson), not proof of reliability", text)

    def test_summary_shows_the_resource_and_both_locations(self):
        report = self.report_with_resource()
        line = [l for l in summary(report, Path("r.report.json")).splitlines() if "resource:" in l][0]
        self.assertEqual(line, "  resource:   static-field odfixture.Config mode "
                               "(write pkg.PolluterTest#p@1 -> read pkg.VictimTest#v@4)")

    def test_summary_survives_a_resource_without_locations(self):
        report = self.report_with_resource()
        report["polluter_write_location"] = report["victim_read_location"] = None
        text = summary(report, Path("r.report.json"))
        self.assertIn("  resource:   static-field odfixture.Config mode", text.splitlines())

    @staticmethod
    def report_with_resource():
        return {
            "victim": V.to_dict(), "polluters": [P.to_dict()], "outcome": "VERIFIED", "unresolved_reason": None,
            "shared_resource": {"kind": "static-field", "class": "odfixture.Config", "field": "mode"},
            "polluter_write_location": {"class": "pkg.PolluterTest", "method": "p", "bytecode_offset": 1},
            "victim_read_location": {"class": "pkg.VictimTest", "method": "v", "bytecode_offset": 4},
            "reproduction": {"successes": 20, "n": 20, "lower": 0.839},
            "victim_alone": {"successes": 0, "n": 20}, "execution_record_reference": "r.jsonl",
        }

    def test_no_single_polluter_exits_3_without_a_report(self):
        records = Path(tempfile.mkdtemp(prefix="flaketrace-cli-records-"))
        record = records / "20261010T000000Z-pkg.VictimTest#v.jsonl"
        unhandled = runs(NO_SINGLE_POLLUTER, record, sequence=[P, V], alone_successes=0, search_runs=1)
        with mock.patch("runner.cli.diagnose", return_value=unhandled):
            code, out, _ = run_cli(["diagnose", "--project", str(project_with_pom()), "--victim", str(V)])
        self.assertEqual(code, 3)
        self.assertEqual(list(records.glob("*.report.json")), [])
        self.assertIn("No report: NO_SINGLE_POLLUTER", out)
        self.assertIn(str(record), out)


class TestCliOnFixture(unittest.TestCase):
    """Real Maven/JVM/javap runs on fixtures/od-fixture, checked against ground_truth.json."""

    @classmethod
    def setUpClass(cls):
        missing = [tool for tool in ("java", "javac", "javap", "mvn") if shutil.which(tool) is None]
        if missing:
            if os.environ.get("FLAKETRACE_REQUIRE_JVM"):
                raise RuntimeError(f"FLAKETRACE_REQUIRE_JVM is set but {missing} not on PATH")
            raise unittest.SkipTest(f"{missing} not on PATH")
        cls.records = tempfile.mkdtemp(prefix="flaketrace-cli-records-")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.records, ignore_errors=True)

    def diagnose(self, victim, n):
        code, out, err = run_cli(["diagnose", "--project", str(FIXTURE), "--victim", victim,
                                  "--n", str(n), "--records", self.records])
        reports = sorted(Path(self.records).glob(f"*-{victim}.report.json"))
        report = json.loads(reports[-1].read_text(encoding="utf-8")) if reports else None
        return code, out, err, report

    def test_f1_command_line_end_to_end(self):
        work = Path(tempfile.mkdtemp(prefix="flaketrace-cli-cwd-"))
        finished = subprocess.run(
            [sys.executable, "-m", "runner", "diagnose", "--project", str(FIXTURE),
             "--victim", "odfixture.ConfigVictimTest#expectsDefaultMode"],
            cwd=work, env=dict(os.environ, PYTHONPATH=str(REPO)),
            capture_output=True, text=True, timeout=900,
        )
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("VERIFIED", finished.stdout)
        reports = list((work / "flaketrace-records").glob("*.report.json"))
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text(encoding="utf-8"))
        self.assertEqual(report["outcome"], "VERIFIED")
        self.assertEqual(report["shared_resource"],
                         {"kind": "static-field", "class": "odfixture.Config", "field": "mode"})
        self.assertEqual((report["reproduction"]["successes"], report["victim_alone"]["successes"]), (20, 0))
        record = Path(report["execution_record_reference"])
        self.assertFalse(record.is_absolute())
        self.assertTrue((work / record).is_file())
        self.assertEqual(reports[0], work / record.with_suffix(".report.json"))
        shutil.rmtree(work, ignore_errors=True)

    def test_f2_depth_two_edge(self):
        code, _, err, report = self.diagnose("odfixture.FeatureVictimTest#expectsTurboDisabled", 20)
        self.assertEqual(code, 0, err)
        self.assertEqual(report["outcome"], "VERIFIED")
        self.assertEqual(report["shared_resource"], {"kind": "system-property", "key": "odfixture.turbo"})
        self.assertEqual(report["victim_read_location"],
                         {"class": "odfixture.FeatureFlags", "method": "isTurboEnabled", "bytecode_offset": 2})

    def test_f3_two_polluters_verified(self):
        code, out, err, report = self.diagnose("odfixture.ToggleVictimTest#expectsNotBothFlagsSet", 20)
        self.assertEqual(code, 0, err)
        self.assertEqual(report["outcome"], "VERIFIED")
        self.assertEqual(report["polluters"], [{"class": "odfixture.ToggleAPolluterTest", "method": "setFlagA"},
                                               {"class": "odfixture.ToggleBPolluterTest", "method": "setFlagB"}])
        self.assertEqual(report["shared_resource"], {"kind": "static-field", "class": "odfixture.Toggles", "field": "flagA"})
        self.assertTrue(any("odfixture.Toggles#flagB" in line for line in report["limitations"]), report["limitations"])
        self.assertIn("polluter:   odfixture.ToggleAPolluterTest#setFlagA, odfixture.ToggleBPolluterTest#setFlagB", out)
        earlier = len(report["original_failing_order"]) - 1  # from the real order, not the fixture's size today
        self.assertIn(f"minimised:  {earlier} earlier tests -> 2 polluters in", out)

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
        self.assertIn("discovered order", out)

    def test_n1_fails_alone(self):
        code, _, err, report = self.diagnose("odfixture.NegativeAloneFailTest#alwaysFails", 5)
        self.assertEqual(code, 0, err)
        self.assertEqual((report["outcome"], report["unresolved_reason"]), ("UNRESOLVED", "VICTIM_FAILS_ALONE"))
        self.assertEqual(report["polluters"], [])

    def test_unknown_victim_exits_2(self):
        code, _, err, report = self.diagnose("odfixture.ConfigVictimTest#noSuchTest", 3)
        self.assertEqual(code, 2)
        self.assertIn("odfixture.ConfigVictimTest#noSuchTest", err)
        self.assertIsNone(report)
        self.assertEqual(list(Path(self.records).glob("*noSuchTest*")), [])  # no empty record left behind


if __name__ == "__main__":
    unittest.main()
