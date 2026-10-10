import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eval.benchmark.yield_report import generate_yield_report, LOGS_DIR, MANIFEST_PATH

REPO_ROOT = Path(__file__).resolve().parents[2]
GROUND_TRUTH_PATH = REPO_ROOT / "fixtures" / "od-fixture" / "ground_truth.json"


def _write_manifest(dir_path: Path, case_ids):
    manifest = {
        "cases": [
            {"case_id": cid, "source": "fixture", "project": "synthetic", "project_path": None,
             "sha": None, "victim": {"class": "X", "method": "y"}, "polluters": []}
            for cid in case_ids
        ]
    }
    path = dir_path / "manifest.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    return path


def _write_log(logs_dir: Path, case_id: str, log: dict):
    with open(logs_dir / f"{case_id}.json", "w", encoding="utf-8") as f:
        json.dump(log, f)


class TestYieldReportSynthetic(unittest.TestCase):
    """Uses temp manifests/logs -- synthetic scenarios, not real benchmark data."""

    def test_no_logs_at_all_shows_not_yet_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = _write_manifest(tmp_path, ["A", "B", "C"])
            logs_dir = tmp_path / "logs"
            logs_dir.mkdir()

            report = generate_yield_report(manifest_path=manifest_path, logs_dir=logs_dir)

            self.assertEqual(report["total_cases"], 3)
            self.assertEqual(report["attempted"], 3)
            self.assertEqual(report["not_yet_run"], 3)
            self.assertEqual(report["built"], 0)
            self.assertEqual(report["reproduced"], 0)
            self.assertEqual(report["excluded"], 0)
            for case in report["cases"]:
                self.assertTrue(case["not_yet_run"])
                self.assertIsNone(case["built"])

    def test_mixed_logs_produce_correct_funnel_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = _write_manifest(tmp_path, ["A", "B", "C", "D"])
            logs_dir = tmp_path / "logs"
            logs_dir.mkdir()

            _write_log(logs_dir, "A", {"built": True, "victim_passes_alone": True, "reproduced": True, "excluded_reason": None})
            _write_log(logs_dir, "B", {"built": False, "victim_passes_alone": None, "reproduced": None, "excluded_reason": "build failed"})
            _write_log(logs_dir, "C", {"built": True, "victim_passes_alone": False, "reproduced": None, "excluded_reason": "VICTIM_FAILS_ALONE"})
            # D has no log file at all -> not_yet_run.

            report = generate_yield_report(manifest_path=manifest_path, logs_dir=logs_dir)

            self.assertEqual(report["total_cases"], 4)
            self.assertEqual(report["attempted"], 4)
            self.assertEqual(report["not_yet_run"], 1)
            self.assertEqual(report["built"], 2)          # A, C
            self.assertEqual(report["build_failed"], 1)   # B
            self.assertEqual(report["victim_passes_alone"], 1)  # A
            self.assertEqual(report["victim_fails_alone"], 1)   # C
            self.assertEqual(report["reproduced"], 1)      # A
            self.assertEqual(report["not_reproduced"], 0)
            self.assertEqual(report["excluded"], 2)        # B, C

            by_id = {c["case_id"]: c for c in report["cases"]}
            self.assertFalse(by_id["D"]["not_yet_run"] is False)  # D is not_yet_run
            self.assertTrue(by_id["D"]["not_yet_run"])
            self.assertIsNone(by_id["B"]["victim_passes_alone"])


class TestRealManifest(unittest.TestCase):
    """Checks the real eval/benchmark/manifest.json and the real (empty)
    logs directory -- this is the actual deliverable, not a synthetic test."""

    def test_real_manifest_matches_fixture_ground_truth(self):
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            manifest = json.load(f)["cases"]
        with open(GROUND_TRUTH_PATH, encoding="utf-8") as f:
            ground_truth = {c["id"]: c for c in json.load(f)["cases"]}

        fixture_cases = [c for c in manifest if c["source"] == "fixture"]
        self.assertEqual({c["case_id"] for c in fixture_cases}, set(ground_truth.keys()))

        for case in fixture_cases:
            with self.subTest(case_id=case["case_id"]):
                gt = ground_truth[case["case_id"]]
                self.assertEqual(case["victim"], gt["victim"])
                self.assertEqual(case["polluters"], gt["polluters"])
                self.assertEqual(case["ground_truth_outcome"], gt["expected_outcome"])
                self.assertEqual(case["ground_truth_reason"], gt.get("expected_outcome_reason_free_text"))

    def test_poc_case_has_pinned_sha_and_null_ground_truth(self):
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            manifest = json.load(f)["cases"]
        poc_cases = [c for c in manifest if c["source"] == "poc-recorded"]
        self.assertEqual(len(poc_cases), 1)
        poc_case = poc_cases[0]
        self.assertIsNotNone(poc_case["sha"])
        self.assertEqual(len(poc_case["sha"]), 40)  # full SHA, not abbreviated
        # We never authored ground truth for this case ourselves -- must stay null.
        self.assertIsNone(poc_case["ground_truth_outcome"])

    def test_idoft_cases_have_pinned_shas_and_null_ground_truth(self):
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            manifest = json.load(f)["cases"]
        idoft_cases = [c for c in manifest if c["source"] == "idoft"]
        # 5 real cases pulled from idoft/odr-tests.csv -- see manifest.json's
        # idoft_source block for provenance.
        self.assertEqual(len(idoft_cases), 5)
        projects = {c["project"] for c in idoft_cases}
        self.assertEqual(len(projects), 5)  # 5 distinct real projects, not duplicates
        for case in idoft_cases:
            with self.subTest(case_id=case["case_id"]):
                self.assertIsNotNone(case["sha"])
                self.assertEqual(len(case["sha"]), 40, "idoft SHAs must be full 40-char hashes")
                self.assertRegex(case["sha"], r"^[0-9a-f]{40}$")
                # Pulled as metadata only -- we have not run these ourselves,
                # so ground truth must stay null, not copied from idoft's listing.
                self.assertIsNone(case["ground_truth_outcome"])
                self.assertTrue(case["victim"]["class"])
                self.assertTrue(case["victim"]["method"])
                self.assertGreaterEqual(len(case["polluters"]), 1)

    def test_real_logs_exist_only_for_the_5_manually_run_fixture_cases(self):
        """F1-F3/N1/N2 were actually run via plain Maven (eval/tools/run_real_reps.sh,
        2026-10-09) and have real logs. F4, N3, POC-DEMO-1 and the 5 idoft cases have
        never been run by any pipeline and must have no log file."""
        json_logs = {p.stem for p in Path(LOGS_DIR).glob("*.json")}
        self.assertEqual(json_logs, {"F1", "F2", "F3", "N1", "N2"})

    def test_yield_report_shows_real_funnel_for_run_cases_and_not_yet_run_for_the_rest(self):
        report = generate_yield_report()
        self.assertEqual(report["total_cases"], 13)
        self.assertEqual(report["not_yet_run"], 8)  # F4, N3 (ADR-008), POC-DEMO-1 + 5 idoft
        self.assertEqual(report["built"], 5)        # F1,F2,F3,N1,N2 all compiled fine
        self.assertEqual(report["reproduced"], 3)   # F1,F2,F3 verified
        self.assertEqual(report["victim_fails_alone"], 2)  # N1,N2
        self.assertEqual(report["excluded"], 2)     # N1,N2, both VICTIM_FAILS_ALONE

        by_id = {c["case_id"]: c for c in report["cases"]}
        for case_id in ("F1", "F2", "F3"):
            self.assertTrue(by_id[case_id]["reproduced"], case_id)
        for case_id in ("N1", "N2"):
            self.assertEqual(by_id[case_id]["excluded_reason"], "VICTIM_FAILS_ALONE", case_id)
        for case_id in ("POC-DEMO-1", "IDOFT-DROPWIZARD-1", "IDOFT-HTTP-REQUEST-1",
                        "IDOFT-MARINE-API-1", "IDOFT-OPENPOJO-1", "IDOFT-SPRING-BOOT-1"):
            self.assertTrue(by_id[case_id]["not_yet_run"], case_id)


if __name__ == "__main__":
    unittest.main()
