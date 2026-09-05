"""Command-line interface for Bulkinout."""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, cast

from .evaluation import evaluate_e2e_case
from .errors import BulkinoutError, ConfigurationError
from .output import write_core_outputs, write_json, write_request_outputs
from .request.golden import discover_golden_cases, run_golden_case
from .request.reference_catalog import build_catalog
from .types import JsonObject

Command = Callable[[argparse.Namespace], None]

if TYPE_CHECKING:
    from .clarification_browser import BrowserClarification
    from .core.models import MissingQuestion
    from .request.service import RequestResult


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
    from .request.clarification import required_clarification_questions
    from .request.service import run_request

    print("Running the Core and Request workflow...")
    if getattr(args, "interactive", False):
        result = _run_interactive_request(args)
    else:
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
    _print_proposed_examination(result)
    handoff_path = Path(args.output) / "radiology_handoff.html"
    print(f"Radiology handoff: {handoff_path}")
    questions = required_clarification_questions(result.missing_questions)
    if questions:
        _print_clarification_guidance(questions, Path(args.output))


def _print_proposed_examination(result: RequestResult) -> None:
    """Display the clinically safe examination summary for the operator."""

    decision = result.imaging_decision
    if (
        decision.decision_status == "selected"
        and decision.primary.recommended
        and decision.primary.exam_name
        and not decision.clinician_call_required
        and result.teleradiology_request.status == "ready_for_human_approval"
        and not any(
            question.required_to_choose or question.blocking
            for question in result.missing_questions
        )
    ):
        print(f"Examen proposé au radiologue : {decision.primary.exam_name}")
    elif decision.decision_status == "no_imaging_recommended":
        print("Examen proposé au radiologue : aucun — imagerie initiale non recommandée")
    else:
        print("Examen proposé au radiologue : aucun à ce stade — échange direct requis")


def _run_interactive_request(args: argparse.Namespace) -> RequestResult:
    """Run one optional browser clarification round without repeating Core."""

    from .clarification_browser import (
        collect_clinician_answers,
        next_interactive_answer_path,
        write_interactive_answers,
    )
    from .core.service import build_radiology_case
    from .request.clarification import required_clarification_questions
    from .request.service import run_request_from_core

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    reference_dir = Path(args.reference) if args.reference else None
    core_result = build_radiology_case(
        input_dir,
        model=args.extraction_model or args.model,
    )
    result = run_request_from_core(
        core_result,
        reference_dir=reference_dir,
        model=args.model,
        decision_model=args.decision_model,
    )
    write_request_outputs(result, output_dir)
    questions = required_clarification_questions(result.missing_questions)
    if not questions:
        return result

    print(f"Opening a local clarification form for {len(questions)} required question(s)...")

    def finish_interaction(clarification: BrowserClarification) -> str:
        nonlocal result
        from .request.handoff import render_radiology_handoff_html

        answer_path = next_interactive_answer_path(output_dir)
        write_interactive_answers(answer_path, clarification.answer_file)
        print(f"Clinician answers saved: {answer_path}")
        has_answer = any(
            item.value is not None and not (isinstance(item.value, str) and not item.value.strip())
            for item in clarification.answer_file.answers
        )
        if clarification.escalated or not has_answer:
            print("No new clinical answer was supplied; contact the teleradiologist directly.")
        else:
            print("Recalculating Request from the existing Core result...")
            result = run_request_from_core(
                core_result,
                reference_dir=reference_dir,
                model=args.model,
                decision_model=args.decision_model,
                answers_path=answer_path,
            )
            write_request_outputs(result, output_dir)
        if result.radiology_handoff is None:
            return "<!doctype html><html lang=fr><body><p>Résultat disponible dans le terminal.</p></body></html>"
        return render_radiology_handoff_html(result.radiology_handoff)

    outcome = collect_clinician_answers(questions, on_submit=finish_interaction)
    if outcome is None:
        print("Interactive clarification was unavailable or timed out.")
        return result
    return result


def _print_clarification_guidance(questions: list[MissingQuestion], output_dir: Path) -> None:
    """Tell a non-interactive operator exactly what remains and where to answer."""

    print(f"\nDecision paused: {len(questions)} required clinical answer(s).")
    for index, question in enumerate(questions, start=1):
        print(f"  {index}. {question.question}")
    template = output_dir / "answers.template.json"
    print(f"Complete {template}, save the result as answers.json, then rerun with:")
    print("  bulkinout request run ... --answers answers.json --output <new-output-directory>")


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


def cmd_request_evaluate(args: argparse.Namespace) -> None:
    """Evaluate saved Request artifacts against one E2E expectation file."""

    report = evaluate_e2e_case(Path(args.case), Path(args.run))
    for name, stage in (("Core", report.core), ("Request", report.request)):
        print(f"[{'PASS' if stage.passed else 'FAIL'}] {name} ({stage.checks} checks)")
        for failure in stage.failures:
            print(f"  - {failure.assertion}: {failure.message}")
    if args.report:
        write_json(
            Path(args.report),
            cast(JsonObject, report.model_dump(mode="json")),
        )
    if not report.passed:
        raise SystemExit(1)


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
    clarification = run.add_mutually_exclusive_group()
    clarification.add_argument(
        "--answers", default=None, help="Optional JSON file of clinician answers"
    )
    clarification.add_argument(
        "--interactive",
        action="store_true",
        help="Open a short-lived local browser form for required clinical answers",
    )
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

    evaluate = request_sub.add_parser(
        "evaluate", help="Evaluate saved E2E artifacts without calling an LLM"
    )
    evaluate.add_argument(
        "--case",
        required=True,
        help="E2E case directory containing expected.json",
    )
    evaluate.add_argument(
        "--run",
        required=True,
        help="Run directory containing generated Request artifacts",
    )
    evaluate.add_argument(
        "--report",
        default=None,
        help="Optional path receiving the machine-readable evaluation report",
    )
    evaluate.set_defaults(func=cmd_request_evaluate)

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
