"""W9 command line (ADR-005): py -m runner diagnose --project DIR --victim Class#method.

Runs runner.diagnose.diagnose(), Member 1's resource evidence for a found polluter and
Member 3's assemble_report(), then writes the report next to its execution record.
Exit codes: 0 report written, 2 input wrong, 1 tool failed, 3 no report can be built yet.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from eval.baseline import TestIdentifier
from eval.report import UnhandledStatus, assemble_report
from evidence.extract import DEFAULT_DEPTH, ExtractError, Project, analyse_pair, report_fields
from runner.diagnose import NO_SINGLE_POLLUTER, NOT_REPRODUCED, POLLUTER_FOUND, DiagnoseInputError, diagnose
from runner.order_runner import ToolError

_VICTIM = re.compile(r"[\w.$]+#[\w$]+")

_NO_REPORT_WHY = {
    NO_SINGLE_POLLUTER: "the victim failed in the original order but not again (alone, after any single "
                        "earlier test, or in the full order once more), so no test is blamed; likely flaky",
    NOT_REPRODUCED: "the victim never failed with a real failure in n runs of the original order",
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="py -m runner")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("diagnose", help="diagnose one failing test and write its report")
    command.add_argument("--project", required=True, help="Maven project folder (contains pom.xml)")
    command.add_argument("--victim", required=True, help="failing test as Class#method")
    command.add_argument("--n", type=int, default=20, help="repeat count (default 20)")
    command.add_argument("--records", default="flaketrace-records",
                         help="folder for the execution record and the report")
    command.add_argument("--order", default=None,
                         help="file with the real failing order, one Class#method per line (ADR-008)")
    command.add_argument("--shuffles", type=int, default=31,
                         help="distinct shuffled orders to try if the order never fails (default 31)")
    command.add_argument("--seed", type=int, default=0, help="first shuffle seed (default 0)")
    args = parser.parse_args(argv)
    return run_diagnose(Path(args.project), args.victim, args.n, args.records,
                        Path(args.order) if args.order else None, args.shuffles, args.seed)


def run_diagnose(project: Path, victim_id: str, n: int, records: str, order_path: Optional[Path] = None,
                 shuffles: int = 31, seed: int = 0) -> int:
    # Java names only: the victim also becomes part of the record's file name.
    if not _VICTIM.fullmatch(victim_id):
        return _error(f"--victim must be Class#method (Java names, no spaces), got {victim_id!r}", 2)
    class_name, _, method = victim_id.partition("#")
    if not (project / "pom.xml").is_file():
        return _error(f"no pom.xml in {project}; --project must be a Maven project folder", 2)
    if shuffles < 0:
        return _error(f"--shuffles must be >= 0, got {shuffles}", 2)
    victim = TestIdentifier(class_name, method)
    order = None
    if order_path is not None:
        try:
            order = read_order(order_path, victim)
        except OrderFileError as error:
            return _error(str(error), 2)

    try:
        runs = diagnose(project, victim, n=n, record_dir=records, original_order=order,
                        shuffles=shuffles, seed=seed)
    except DiagnoseInputError as error:
        return _error(str(error), 2)
    except subprocess.CalledProcessError as error:
        tool = Path(str(error.cmd[0])).name
        return _error(f"{tool} failed with exit code {error.returncode} on {project}; run it there to see why", 1)
    except subprocess.TimeoutExpired as error:
        return _error(f"{Path(str(error.cmd[0])).name} timed out after {error.timeout:g} s on {project}", 1)
    except ToolError as error:
        return _error(str(error), 1)

    try:
        fields = resource_fields(project, runs) if runs.status == POLLUTER_FOUND else None
    except ExtractError as error:
        return _error(f"resource evidence failed: {error}", 1)

    try:
        report = assemble_report(runs, fields)
    except UnhandledStatus:
        why = _NO_REPORT_WHY.get(runs.status, "eval.report cannot build this report yet")
        print(f"No report: {runs.status} - {why}\n  record: {runs.execution_record}")
        return 3

    report_path = Path(runs.execution_record).with_suffix(".report.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    ddmin_ran = runs.minimise_runs and runs.polluters
    crashes = runs.infrastructure_failures + runs.shuffle_infrastructure_failures + runs.alone_infrastructure_failures
    print(summary(report, report_path, (len(runs.original_order) - 1, runs.minimise_runs) if ddmin_ran else None,
                  crashes))
    return 0


def resource_fields(project: Path, runs) -> dict:
    """Member 1's pair-mode evidence for each polluter and the victim, combined (ADR-007).
    analyse_pair deepens each pair on its own when nothing is found at the default depth (ADR-006)."""
    classes = Project([str(project / "target" / "classes"), str(project / "target" / "test-classes")])
    victim = str(runs.victim)
    return combine_fields([analyse_pair(classes, str(p), victim) for p in runs.polluters])


def combine_fields(pairs: list) -> dict:
    """Report fields from one pair per polluter. One polluter: M1's report_fields unchanged.
    Several: the first polluter's edge is shown and the others named in limitations, but only if
    every polluter has an edge -- VERIFIED must mean every blamed test has a found mechanism."""
    fields = [report_fields(pair) for pair in pairs]
    if len(fields) == 1:
        return fields[0]
    # The first polluter's projected lines, plus only M1's fixed lines from the others: their own
    # "not shown" lines would name a resource a second time.
    lines = list(fields[0]["limitations"])
    for pair in pairs[1:]:
        lines += [line for line in pair["limitations"] if line not in lines]
    if all(pair["edges"] for pair in pairs):
        shown = pairs[0]["edges"][0]["resource_id"]
        others = [f"Polluter {_test(pair['polluter'])}: shared resource {edge['resource_id']} is not shown in this report"
                  + _depth_note(edge) for pair in pairs[1:] for edge in pair["edges"] if edge["resource_id"] != shown]
        return dict(fields[0], limitations=lines + others)
    found = [f"Polluter {_test(pair['polluter'])}: shared resource {edge['resource_id']} was found, "
             "but not every polluter has evidence" + _depth_note(edge) for pair in pairs for edge in pair["edges"]]
    missing = [f"No polluter-write/victim-read resource edge was found for polluter {_test(pair['polluter'])}"
               for pair in pairs if not pair["edges"]]
    # any_edge_found tells M3's assemble_report not to add its generic "no edge was found" line.
    return dict(fields[0], shared_resource=None, polluter_write_location=None, victim_read_location=None,
                limitations=lines + found + missing, any_edge_found=bool(found))


def _depth_note(edge: dict) -> str:
    """The depth of an edge that is only named, measured like M1's report_fields does for the shown one."""
    depth = max(edge["polluter_write_locations"][0]["depth"], edge["victim_read_locations"][0]["depth"])
    return f" (evidence at depth {depth}, above the default {DEFAULT_DEPTH})" if depth > DEFAULT_DEPTH else ""


def summary(report: dict, report_path: Path, minimised: Optional[Tuple[int, int]] = None,
            crashes: int = 0) -> str:
    """`minimised` = (earlier tests, ddmin runs) when ddmin found the polluters (ADR-007); the report's
    schema has no field for it, so only the summary says how far the order was shrunk."""
    reason = f" ({report['unresolved_reason']})" if report["unresolved_reason"] else ""
    lines = [f"{report['outcome']}{reason}  {_test(report['victim'])}"]
    if report["polluters"]:
        lines.append("  polluter:   " + ", ".join(_test(p) for p in report["polluters"]))
    if minimised:
        earlier, runs = minimised
        count = len(report["polluters"])
        lines.append(f"  minimised:  {earlier} earlier tests -> {count} polluter{'s' if count != 1 else ''} "
                     f"in {runs} runs (1-minimal, not necessarily the minimum)")
    explored = report.get("order_exploration")
    if explored and explored["reproducing_seed"] is not None:
        lines.append(f"  orders:     reproduced in shuffled order (seed {explored['reproducing_seed']}) "
                     f"after {explored['shuffled_orders_tried']} shuffled orders")
    if report["unresolved_reason"] == "NOT_REPRODUCED" and explored:
        exhausted = " (no further distinct order found)" if explored["orders_exhausted"] else ""
        # A crash or timeout is not a pass: never say "never failed" when runs only crashed.
        result = f"no real failure ({crashes} runs crashed or timed out)" if crashes else "never failed"
        # "given" only for an order from --order; otherwise FlakeTrace discovered it.
        source = "given" if explored["order_given"] else "discovered"
        lines.append(f"  orders:     {source} order {report['reproduction']['n']}x, "
                     f"{explored['shuffled_orders_tried']} distinct shuffled orders{exhausted}, "
                     f"alone {report['victim_alone']['n']}x: {result}")
        lines.append(f"  bound:      failure rate in the {source} order < {report['reproduction']['upper']:.3f} "
                     "(95% Wilson), not proof of reliability")
    if report["shared_resource"]:
        resource = " ".join(str(value) for value in report["shared_resource"].values())
        write, read = report["polluter_write_location"], report["victim_read_location"]
        if write and read:
            resource += (f" (write {_test(write)}@{write['bytecode_offset']}"
                         f" -> read {_test(read)}@{read['bytecode_offset']})")
        lines.append(f"  resource:   {resource}")
    reproduced, alone = report["reproduction"], report["victim_alone"]
    lines.append(f"  reproduced: {reproduced['successes']}/{reproduced['n']} (lower bound "
                 f"{reproduced['lower']:.3f})   alone: {alone['successes']}/{alone['n']}")
    lines.append(f"  report:     {report_path}")
    lines.append(f"  record:     {report['execution_record_reference']}")
    return "\n".join(lines)


class OrderFileError(Exception):
    """A problem with the --order file (exit 2)."""


def read_order(path: Path, victim: TestIdentifier) -> List[TestIdentifier]:
    """One Class#method per line; blank and # lines ignored; BOM and CRLF allowed (ADR-008)."""
    try:
        data = path.read_bytes()
    except OSError as error:
        raise OrderFileError(f"cannot read --order file {path}: {error.strerror}")
    try:
        # Windows PowerShell 5.1's `>` writes UTF-16 with a BOM; everything else is UTF-8 (BOM optional).
        text = data.decode("utf-16") if data[:2] in (b"\xff\xfe", b"\xfe\xff") else data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise OrderFileError(f"--order file {path} is not UTF-8 or UTF-16 text")
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


def _test(location: dict) -> str:
    return f"{location['class']}#{location['method']}"


def _error(message: str, code: int) -> int:
    print(f"error: {message}", file=sys.stderr)
    return code
