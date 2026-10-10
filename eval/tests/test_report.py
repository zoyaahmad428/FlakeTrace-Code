import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eval.baseline import FailureSignature, TestIdentifier
from eval.report import UnhandledStatus, assemble_report
from eval.schema_validator import validate_report
from evidence.extract import find_edges, report_fields
from runner.diagnose import DiagnosisRuns, NOT_REPRODUCED, NO_SINGLE_POLLUTER, POLLUTER_FOUND, VICTIM_FAILS_ALONE
from runner.integrity import SourceIntegrity

POLLUTER = TestIdentifier("odfixture.ConfigPolluterTest", "pollute")
VICTIM = TestIdentifier("odfixture.ConfigVictimTest", "expectsDefaultMode")
REF = FailureSignature("java.lang.AssertionError", "odfixture.ConfigVictimTest.expectsDefaultMode:10",
                        "expected:<0> but was:<1>")
INTEGRITY_OK = SourceIntegrity(True, "19 files hashed; all identical")
INTEGRITY_FAILED = SourceIntegrity(False, "changed: src/main/java/odfixture/Config.java")

# Literal Output-1 shapes exactly as evidence.extract.find_edges expects them (as produced by
# evidence.extract.analyse_test) -- hand-written here to drive Member 1's real find_edges/
# report_fields with known inputs, not a fake of Member 1's extractor.
POLLUTER_ID = "odfixture.ConfigPolluterTest#pollute"
VICTIM_ID = "odfixture.ConfigVictimTest#expectsDefaultMode"
POLLUTER_ACCESS = {
    "test": {"class": "odfixture.ConfigPolluterTest", "method": "pollute"},
    "accesses": [{
        "category": "static-field", "resource_id": "odfixture.Config#mode",
        "resource": {"kind": "static-field", "class": "odfixture.Config", "field": "mode"},
        "access": "WRITE", "class": "odfixture.ConfigPolluterTest", "method": "pollute",
        "bytecode_offset": 1, "depth": 1,
    }],
    "unsupported_observations": [],
}
VICTIM_ACCESS = {
    "test": {"class": "odfixture.ConfigVictimTest", "method": "expectsDefaultMode"},
    "accesses": [{
        "category": "static-field", "resource_id": "odfixture.Config#mode",
        "resource": {"kind": "static-field", "class": "odfixture.Config", "field": "mode"},
        "access": "READ", "class": "odfixture.ConfigVictimTest", "method": "expectsDefaultMode",
        "bytecode_offset": 1, "depth": 1,
    }],
    "unsupported_observations": [],
}
NO_SHARED_RESOURCE_ACCESS = {
    "test": {"class": "odfixture.ConfigVictimTest", "method": "expectsDefaultMode"},
    "accesses": [],
    "unsupported_observations": [],
}


def resource_fields(polluter_access, victim_access):
    """Drive the report fields through Member 1's real pair-mode functions, the way
    eval/tools/run_w9_integration.py does -- not through a local correlation function."""
    pair = find_edges(POLLUTER_ID, polluter_access, VICTIM_ID, victim_access)
    return report_fields(pair)


class TestResourceFieldsViaM1(unittest.TestCase):
    """find_edges/report_fields are Member 1's; these tests only check this module calls
    them correctly and reads their output the way assemble_report expects."""

    def test_finds_the_shared_resource(self):
        fields = resource_fields(POLLUTER_ACCESS, VICTIM_ACCESS)
        self.assertEqual(fields["shared_resource"], {"kind": "static-field", "class": "odfixture.Config", "field": "mode"})
        self.assertEqual(fields["polluter_write_location"],
                          {"class": "odfixture.ConfigPolluterTest", "method": "pollute", "bytecode_offset": 1})
        self.assertEqual(fields["victim_read_location"],
                          {"class": "odfixture.ConfigVictimTest", "method": "expectsDefaultMode", "bytecode_offset": 1})
        self.assertIn("Static analysis only; no runtime evidence (Iteration 2).", fields["limitations"])

    def test_no_shared_resource_gives_none_fields(self):
        fields = resource_fields(POLLUTER_ACCESS, NO_SHARED_RESOURCE_ACCESS)
        self.assertIsNone(fields["shared_resource"])


def _diagnosis(status, **overrides):
    defaults = dict(
        status=status, victim=VICTIM, original_order=[POLLUTER, VICTIM],
        reference_signature=REF, polluters=[POLLUTER], sequence=[POLLUTER, VICTIM],
        sequence_n=20, sequence_successes=20, sequence_any_failures=20,
        alone_n=20, alone_successes=0, search_runs=1,
        source_integrity=INTEGRITY_OK, execution_record="/tmp/record.jsonl",
    )
    defaults.update(overrides)
    return DiagnosisRuns(**defaults)


class TestAssembleReport(unittest.TestCase):
    def test_polluter_found_with_edge_gives_verified(self):
        fields = resource_fields(POLLUTER_ACCESS, VICTIM_ACCESS)
        report = assemble_report(_diagnosis(POLLUTER_FOUND), fields)
        self.assertEqual(report["outcome"], "VERIFIED")
        self.assertIsNone(report["unresolved_reason"])
        self.assertEqual(report["shared_resource"], fields["shared_resource"])
        self.assertEqual(report["polluters"], [POLLUTER.to_dict()])
        self.assertIn("Static analysis only; no runtime evidence (Iteration 2).", report["limitations"])
        validate_report(report)  # must not raise

    def test_polluter_found_without_edge_gives_no_supported_resource_evidence(self):
        report = assemble_report(_diagnosis(POLLUTER_FOUND), resource_fields=None)
        self.assertEqual(report["outcome"], "UNRESOLVED")
        self.assertEqual(report["unresolved_reason"], "NO_SUPPORTED_RESOURCE_EVIDENCE")
        self.assertIsNone(report["shared_resource"])
        self.assertIn(
            "No polluter-write/victim-read resource edge was found by static analysis.",
            report["limitations"],
        )
        validate_report(report)

    def test_several_polluters_partial_evidence_suppresses_the_generic_no_edge_line(self):
        """W10 (ADR-007): a caller combining several polluters' pair-mode results can set
        shared_resource=None (not every polluter has an edge, so none is shown as the primary
        resource) while any_edge_found=True (some polluter did have one) and name the specifics
        in limitations. The generic blanket line would contradict that and must not appear."""
        fields = {
            "shared_resource": None, "polluter_write_location": None, "victim_read_location": None,
            "instrumentation_level": "static-only", "any_edge_found": True,
            "limitations": [
                "Polluter odfixture.ToggleAPolluterTest#setFlagA: shared resource "
                "odfixture.Toggles#flagA was found, but not every polluter has evidence",
                "No polluter-write/victim-read resource edge was found for polluter "
                "odfixture.ToggleBPolluterTest#setFlagB",
            ],
        }
        diagnosis = _diagnosis(POLLUTER_FOUND, polluters=[POLLUTER, TestIdentifier("x", "y")])
        report = assemble_report(diagnosis, fields)
        self.assertEqual(report["unresolved_reason"], "NO_SUPPORTED_RESOURCE_EVIDENCE")
        self.assertIsNone(report["shared_resource"])
        self.assertNotIn(
            "No polluter-write/victim-read resource edge was found by static analysis.",
            report["limitations"],
        )
        self.assertIn(
            "Polluter odfixture.ToggleAPolluterTest#setFlagA: shared resource "
            "odfixture.Toggles#flagA was found, but not every polluter has evidence",
            report["limitations"],
        )
        validate_report(report)

    def test_several_polluters_zero_evidence_keeps_the_generic_no_edge_line(self):
        """Same shape as above, but no polluter had any edge at all (any_edge_found=False) --
        the generic line is the correct, non-contradictory thing to say here."""
        fields = {
            "shared_resource": None, "polluter_write_location": None, "victim_read_location": None,
            "instrumentation_level": "static-only", "any_edge_found": False,
            "limitations": ["No polluter-write/victim-read resource edge was found for polluter x#y"],
        }
        diagnosis = _diagnosis(POLLUTER_FOUND, polluters=[POLLUTER, TestIdentifier("x", "y")])
        report = assemble_report(diagnosis, fields)
        self.assertIn(
            "No polluter-write/victim-read resource edge was found by static analysis.",
            report["limitations"],
        )
        validate_report(report)

    def test_polluter_found_weak_reproduction_gives_candidate(self):
        diagnosis = _diagnosis(POLLUTER_FOUND, sequence_successes=12, sequence_any_failures=12)
        fields = resource_fields(POLLUTER_ACCESS, VICTIM_ACCESS)
        report = assemble_report(diagnosis, fields)
        self.assertEqual(report["outcome"], "CANDIDATE")
        validate_report(report)

    def test_source_integrity_failed_overrides_everything(self):
        diagnosis = _diagnosis(POLLUTER_FOUND, source_integrity=INTEGRITY_FAILED)
        fields = resource_fields(POLLUTER_ACCESS, VICTIM_ACCESS)
        report = assemble_report(diagnosis, fields)
        self.assertEqual(report["outcome"], "UNRESOLVED")
        self.assertEqual(report["unresolved_reason"], "SOURCE_INTEGRITY_FAILED")
        self.assertFalse(report["source_integrity"]["passed"])
        validate_report(report)

    def test_victim_fails_alone_gives_unresolved(self):
        diagnosis = _diagnosis(
            VICTIM_FAILS_ALONE, polluters=[], sequence=[VICTIM],
            sequence_n=20, sequence_successes=20, sequence_any_failures=20,
            alone_n=20, alone_successes=20,
        )
        report = assemble_report(diagnosis)  # no resource_fields argument -- not relevant here
        self.assertEqual(report["outcome"], "UNRESOLVED")
        self.assertEqual(report["unresolved_reason"], "VICTIM_FAILS_ALONE")
        self.assertEqual(report["polluters"], [])
        self.assertIsNone(report["shared_resource"])
        validate_report(report)

    def test_victim_fails_alone_ignores_a_passed_in_edge(self):
        """Even if a caller mistakenly passes resource_fields for a VICTIM_FAILS_ALONE
        diagnosis, it must not be used -- the gate fires before resource evidence matters."""
        diagnosis = _diagnosis(
            VICTIM_FAILS_ALONE, polluters=[], sequence=[VICTIM],
            alone_n=20, alone_successes=5,
        )
        fields = resource_fields(POLLUTER_ACCESS, VICTIM_ACCESS)
        report = assemble_report(diagnosis, resource_fields=fields)
        self.assertIsNone(report["shared_resource"])
        self.assertEqual(report["unresolved_reason"], "VICTIM_FAILS_ALONE")

    def test_not_reproduced_with_todays_real_shape_is_unhandled_not_a_crash(self):
        """Today, runner.diagnose() short-circuits before running the isolation check when
        nothing reproduces at all, so a REAL NOT_REPRODUCED diagnosis has alone_n=0.
        eval.outcome.DecisionInput would reject that outright (isolation_n must be > 0) as a
        bare ValueError, which the CLI does not catch -- so assemble_report raises
        UnhandledStatus for this specific case instead, keeping the CLI's "exit 3, no report
        yet" behaviour safe regardless of which of this module's or Member 2's diagnose()
        change merges first (flagged by Member 2, see docs/evidence-m3.md)."""
        diagnosis = _diagnosis(
            NOT_REPRODUCED, polluters=[], sequence=[POLLUTER, VICTIM], reference_signature=None,
            sequence_n=5, sequence_successes=0, sequence_any_failures=0,
            alone_n=0, alone_successes=0,
        )
        with self.assertRaises(UnhandledStatus):
            assemble_report(diagnosis)

    def test_not_reproduced_with_isolation_data_gives_unresolved(self):
        """ADR-008's intended shape, once Member 2's diagnose() always runs the alone check:
        alone_n > 0 even though nothing ever reproduced. Hand-built ahead of that real
        dependency landing, per this project's established testing convention."""
        diagnosis = _diagnosis(
            NOT_REPRODUCED, polluters=[], sequence=[POLLUTER, VICTIM], reference_signature=None,
            sequence_n=20, sequence_successes=0, sequence_any_failures=0,
            alone_n=20, alone_successes=0,
        )
        report = assemble_report(diagnosis)
        self.assertEqual(report["outcome"], "UNRESOLVED")
        self.assertEqual(report["unresolved_reason"], "NOT_REPRODUCED")
        self.assertIsNone(report["failure_signature"])
        self.assertIsNone(report["shared_resource"])
        self.assertEqual(report["polluters"], [])
        self.assertTrue(any("Not reproduced:" in line for line in report["limitations"]))
        validate_report(report)

    def test_infrastructure_failure_gives_unresolved_with_null_signature(self):
        """Hand-built DiagnosisRuns with infrastructure_failures set, simulating Member 2's
        diagnose() once it tracks crash/timeout-only sequences separately (ADR-008). Not yet
        real: DiagnosisRuns has no such field today, so assemble_report's getattr(...,
        default 0) is exercised instead via a plain object standing in for it."""
        class _WithInfraFailures:
            """Minimal stand-in: real attribute access, not a dict -- not a fake of
            DiagnosisRuns, just adding the one field it doesn't have yet."""
            def __init__(self, base, infrastructure_failures):
                self._base = base
                self.infrastructure_failures = infrastructure_failures

            def __getattr__(self, name):
                return getattr(self._base, name)

        base = _diagnosis(
            NOT_REPRODUCED, polluters=[], sequence=[POLLUTER, VICTIM], reference_signature=None,
            sequence_n=20, sequence_successes=0, sequence_any_failures=5,
            alone_n=20, alone_successes=0,
        )
        diagnosis = _WithInfraFailures(base, infrastructure_failures=5)
        report = assemble_report(diagnosis)
        self.assertEqual(report["outcome"], "UNRESOLVED")
        self.assertEqual(report["unresolved_reason"], "INFRASTRUCTURE_FAILURE")
        self.assertIsNone(report["failure_signature"])
        self.assertTrue(any("crashed or timed out" in line for line in report["limitations"]))
        validate_report(report)

    def test_no_single_polluter_is_unhandled(self):
        diagnosis = _diagnosis(NO_SINGLE_POLLUTER, polluters=[], sequence=[POLLUTER, VICTIM])
        with self.assertRaises(UnhandledStatus):
            assemble_report(diagnosis)


if __name__ == "__main__":
    unittest.main()
