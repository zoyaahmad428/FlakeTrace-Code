"""Execution record (W7, ADR-004): RecordingRunner wraps an OrderRunner and appends every run
to a JSON-lines file, one line per JVM run, written as soon as the run finishes."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from eval.baseline import RunOutcome, TestIdentifier


class RecordingRunner:
    """Satisfies eval.baseline.OrderRunner. Set `step` before a phase to label its runs."""

    def __init__(self, runner, path, header: dict):
        self._runner = runner
        self.path = Path(path)
        self.step = "unlabelled"
        self.note: dict = {}  # extra fields for the next run lines, e.g. a shuffle seed (ADR-008)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write({"type": "header", **header})

    def run_ordered(self, order: List[TestIdentifier]) -> Dict[TestIdentifier, RunOutcome]:
        started = datetime.now(timezone.utc).isoformat()
        clock = time.monotonic()
        results = self._runner.run_ordered(order)
        entry = {
            "type": "run",
            "step": self.step,
            "started": started,
            "seconds": round(time.monotonic() - clock, 3),
            "order": [str(test) for test in order],
            "outcomes": [_outcome(test, results[test]) for test in order],
        }
        entry.update(self.note)
        self._write(entry)
        return results

    def _write(self, entry: dict) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


def _outcome(test: TestIdentifier, outcome: RunOutcome) -> dict:
    entry = {"test": str(test), "passed": outcome.passed}
    if outcome.failure_signature is not None:
        signature = outcome.failure_signature
        entry["failure_signature"] = {
            "exception_type": signature.exception_type,
            "message": signature.message,
            "stack_trace": signature.stack_trace,
        }
    return entry
