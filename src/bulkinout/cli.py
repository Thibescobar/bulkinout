"""Command-line interface for Bulkinout."""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Sequence
from pathlib import Path

from .errors import BulkinoutError, ConfigurationError
from .output import write_core_outputs, write_request_outputs
from .request.golden import discover_golden_cases, run_golden_case
from .request.reference_catalog import build_catalog

Command = Callable[[argparse.Namespace], None]


def _require_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise ConfigurationError("OPENAI_API_KEY is missing.")


def cmd_core_structure(args: argparse.Namespace) -> None:
    """Run Core extraction and write its output snapshots."""

    _require_api_key()
    from .core.service import build_radiology_case

    output_dir = Path(args.output)
    result = build_radiology_case(Path(args.input), model=args.model)
    write_core_outputs(result, output_dir)
    print(f"Core structuring completed: {output_dir / 'radiology_case.json'}")


def cmd_request_run(args: argparse.Namespace) -> None:
    """Run the complete Request application service and write its snapshots."""

    _require_api_key()
    from .request.service import run_request

    print("Running the Core and Request workflow...")
    result = run_request(
        Path(args.input),
        reference_dir=Path(args.reference) if args.reference else None,
        model=args.model,
        extraction_model=args.extraction_model,
        decision_model=args.decision_model,
        answers_path=Path(args.answers) if args.answers else None,
    )
    write_request_outputs(result, Path(args.output))

    print()
    print(f"Decision: {result.imaging_decision.decision_status}")
    print(
        "Clinician call required: "
        f"{'YES' if result.imaging_decision.clinician_call_required else 'NO'}"
    )
    print(f"Teleradiology request status: {result.teleradiology_request.status}")


def cmd_request_golden(args: argparse.Namespace) -> None:
    """Run deterministic golden cases against the local reference."""

    reference_dir = Path(args.reference) if args.reference else None
    cases = discover_golden_cases(Path(args.cases))
    if not cases:
        raise ConfigurationError("No golden cases found.")

    failed = 0
    for path in cases:
        result = run_golden_case(path, reference_dir)
        print(f"[{'PASS' if result.passed else 'FAIL'}] {result.case_id}")
        if not result.passed:
            failed += 1
            for error in result.errors:
                print(f"  - {error}")
    print(f"\n{len(cases) - failed}/{len(cases)} golden cases passed.")
    if failed:
        raise SystemExit(1)


def cmd_request_catalog(args: argparse.Namespace) -> None:
    """Print a compact inventory of configured reference scenarios."""

    catalog = build_catalog(Path(args.reference) if args.reference else None)
    print(f"{len(catalog)} scenario(s)")
    for item in catalog:
        print(
            f"- {item['id']} v{item['version']} | "
            f"{item['candidate_count']} candidate(s) | "
            f"{item['question_count']} question(s) | "
            f"{item['status']}"
        )


def cmd_report(_args: argparse.Namespace) -> None:
    """Report that the post-exam workflow is not implemented yet."""

    print("Bulkinout Report is reserved for a later phase.")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser without executing a command."""

    parser = argparse.ArgumentParser(
        prog="bulkinout",
        description="Bulkinout — Bulk in. Intelligence out.",
    )
    top = parser.add_subparsers(dest="area", required=True)

    core = top.add_parser("core", help="Multimodal structuring core")
    core_sub = core.add_subparsers(dest="core_cmd", required=True)
    structure = core_sub.add_parser("structure", help="Bulk input -> structured RadiologyCase")
    structure.add_argument(
        "--input", default="input", help="Directory containing source documents (default: input)"
    )
    structure.add_argument(
        "--output", default="output", help="Directory receiving Core JSON files (default: output)"
    )
    structure.add_argument(
        "--model",
        default=None,
        help=("Extraction model (default: BULKINOUT_EXTRACTION_MODEL, then BULKINOUT_MODEL)"),
    )
    structure.set_defaults(func=cmd_core_structure)

    request = top.add_parser("request", help="Pre-exam workflow")
    request_sub = request.add_subparsers(dest="request_cmd", required=True)
    run = request_sub.add_parser("run", help="Run the complete pre-exam workflow")
    run.add_argument(
        "--input", default="input", help="Directory containing source documents (default: input)"
    )
    run.add_argument(
        "--output",
        default="output",
        help="Directory receiving workflow JSON files (default: output)",
    )
    run.add_argument("--answers", default=None, help="Optional JSON file of clinician answers")
    run.add_argument(
        "--reference",
        default=None,
        help="Directory containing scenario YAML files; overrides the packaged reference",
    )
    run.add_argument(
        "--model",
        default=None,
        help="Shared fallback model (default: BULKINOUT_MODEL)",
    )
    run.add_argument(
        "--extraction-model",
        default=None,
        help="Core extraction model (default: BULKINOUT_EXTRACTION_MODEL, then shared fallback)",
    )
    run.add_argument(
        "--decision-model",
        default=None,
        help="Request decision model (default: BULKINOUT_DECISION_MODEL, then shared fallback)",
    )
    run.set_defaults(func=cmd_request_run)

    catalog = request_sub.add_parser("catalog", help="List reference scenarios")
    catalog.add_argument(
        "--reference",
        default=None,
        help="Directory containing scenario YAML files; overrides the packaged reference",
    )
    catalog.set_defaults(func=cmd_request_catalog)

    golden = request_sub.add_parser("golden", help="Run golden cases without an LLM")
    golden.add_argument(
        "--cases",
        default="tests/golden",
        help="Directory containing golden YAML cases (default: tests/golden)",
    )
    golden.add_argument(
        "--reference",
        default=None,
        help="Directory containing scenario YAML files; overrides the packaged reference",
    )
    golden.set_defaults(func=cmd_request_golden)

    report = top.add_parser("report", help="Post-exam workflow (standby)")
    report.set_defaults(func=cmd_report)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Parse arguments, dispatch the command, and render expected errors."""

    parser = build_parser()
    args = parser.parse_args(argv)
    command: Command = args.func
    try:
        command(args)
    except BulkinoutError as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
