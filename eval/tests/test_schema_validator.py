import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import jsonschema

from eval.schema_validator import load_schema, validate_report

VALID_REPORT = {
    "victim": {"class": "odfixture.ConfigVictimTest", "method": "expectsDefaultMode"},
    "polluters": [{"class": "odfixture.ConfigPolluterTest", "method": "pollute"}],
    "original_failing_order": [
        {"class": "odfixture.ConfigPolluterTest", "method": "pollute"},
        {"class": "odfixture.ConfigVictimTest", "method": "expectsDefaultMode"},
    ],
    "reduced_sequence": [
        {"class": "odfixture.ConfigPolluterTest", "method": "pollute"},
        {"class": "odfixture.ConfigVictimTest", "method": "expectsDefaultMode"},
    ],
    "reproduction": {"successes": 20, "n": 20, "confidence": 0.95, "lower": 0.838, "upper": 1.0},
    "sequence_any_signature_failures": 20,
    "victim_alone": {"successes": 0, "n": 20, "confidence": 0.95, "lower": 0.0, "upper": 0.161},
    "shared_resource": {"kind": "static-field", "class": "odfixture.Config", "field": "mode"},
    "polluter_write_location": {"class": "odfixture.ConfigPolluterTest", "method": "pollute", "bytecode_offset": 3},
    "victim_read_location": {"class": "odfixture.ConfigVictimTest", "method": "expectsDefaultMode", "bytecode_offset": 5},
    "failure_signature": {
        "exception_type": "java.lang.AssertionError",
        "message": "expected:<0> but was:<1>",
        "stack_trace": "at odfixture.ConfigVictimTest.expectsDefaultMode(ConfigVictimTest.java:10)",
    },
    "instrumentation_level": "static-only",
    "execution_record_reference": "exec-123",
    "source_integrity": {"passed": True, "details": "ok"},
    "outcome": "VERIFIED",
    "unresolved_reason": None,
    "limitations": [],
}


class TestSchemaItself(unittest.TestCase):
    def test_schema_loads_and_is_itself_valid_json_schema(self):
        schema = load_schema()
        jsonschema.Draft202012Validator.check_schema(schema)


class TestValidateReport(unittest.TestCase):
    def test_valid_report_passes(self):
        validate_report(VALID_REPORT)  # must not raise

    def test_missing_required_field_fails(self):
        bad = copy.deepcopy(VALID_REPORT)
        del bad["victim"]
        with self.assertRaises(jsonschema.exceptions.ValidationError):
            validate_report(bad)

    def test_unknown_outcome_value_fails(self):
        bad = copy.deepcopy(VALID_REPORT)
        bad["outcome"] = "DEFINITELY_A_BUG"
        with self.assertRaises(jsonschema.exceptions.ValidationError):
            validate_report(bad)

    def test_unresolved_without_reason_fails(self):
        bad = copy.deepcopy(VALID_REPORT)
        bad["outcome"] = "UNRESOLVED"
        bad["unresolved_reason"] = None
        with self.assertRaises(jsonschema.exceptions.ValidationError):
            validate_report(bad)

    def test_verified_with_a_reason_fails(self):
        bad = copy.deepcopy(VALID_REPORT)
        bad["outcome"] = "VERIFIED"
        bad["unresolved_reason"] = "NOT_REPRODUCED"
        with self.assertRaises(jsonschema.exceptions.ValidationError):
            validate_report(bad)

    def test_unresolved_with_reason_passes(self):
        ok = copy.deepcopy(VALID_REPORT)
        ok["outcome"] = "UNRESOLVED"
        ok["unresolved_reason"] = "VICTIM_FAILS_ALONE"
        validate_report(ok)  # must not raise

    def test_additional_property_rejected(self):
        bad = copy.deepcopy(VALID_REPORT)
        bad["totally_made_up_field"] = 1
        with self.assertRaises(jsonschema.exceptions.ValidationError):
            validate_report(bad)

    def test_not_reproduced_requires_null_failure_signature(self):
        """ADR-008: a failure that never reproduced has no signature to report."""
        bad = copy.deepcopy(VALID_REPORT)
        bad["outcome"] = "UNRESOLVED"
        bad["unresolved_reason"] = "NOT_REPRODUCED"
        # failure_signature still the real object inherited from VALID_REPORT -- must fail.
        with self.assertRaises(jsonschema.exceptions.ValidationError):
            validate_report(bad)

    def test_not_reproduced_with_null_failure_signature_passes(self):
        ok = copy.deepcopy(VALID_REPORT)
        ok["outcome"] = "UNRESOLVED"
        ok["unresolved_reason"] = "NOT_REPRODUCED"
        ok["failure_signature"] = None
        validate_report(ok)  # must not raise

    def test_null_failure_signature_requires_not_reproduced(self):
        """The inverse: a real reason (e.g. VICTIM_FAILS_ALONE) must still carry a real signature."""
        bad = copy.deepcopy(VALID_REPORT)
        bad["outcome"] = "UNRESOLVED"
        bad["unresolved_reason"] = "VICTIM_FAILS_ALONE"
        bad["failure_signature"] = None
        with self.assertRaises(jsonschema.exceptions.ValidationError):
            validate_report(bad)

    def test_infrastructure_failure_requires_null_failure_signature(self):
        """runner.diagnose always sets reference_signature=None for the NOT_REPRODUCED
        status that INFRASTRUCTURE_FAILURE is decided from -- so, like NOT_REPRODUCED,
        it never has a real signature to report."""
        bad = copy.deepcopy(VALID_REPORT)
        bad["outcome"] = "UNRESOLVED"
        bad["unresolved_reason"] = "INFRASTRUCTURE_FAILURE"
        with self.assertRaises(jsonschema.exceptions.ValidationError):
            validate_report(bad)

        ok = copy.deepcopy(VALID_REPORT)
        ok["outcome"] = "UNRESOLVED"
        ok["unresolved_reason"] = "INFRASTRUCTURE_FAILURE"
        ok["failure_signature"] = None
        validate_report(ok)  # must not raise

    def test_order_exploration_is_optional_but_validated_when_present(self):
        ok = copy.deepcopy(VALID_REPORT)
        ok["order_exploration"] = {
            "order_given": True, "shuffled_orders_tried": 5,
            "orders_exhausted": False, "seed_base": 0, "reproducing_seed": 3,
        }
        validate_report(ok)  # must not raise

        bad = copy.deepcopy(VALID_REPORT)
        bad["order_exploration"] = {"order_given": True}  # missing required sub-fields
        with self.assertRaises(jsonschema.exceptions.ValidationError):
            validate_report(bad)


if __name__ == "__main__":
    unittest.main()
