"""Command-line interface for Bulkinout."""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
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
    from .clarification_browser import BrowserClarification, BrowserReview
    from .core.models import MissingQuestion
    from .core.service import CoreResult
    from .request.service import RequestResult


def _require_api_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise ConfigurationError("OPENAI_API_KEY is missing.")


def cmd_core_structure(args: argparse.Namespace) -> None:
    """Run Core extraction and write its output snapshots."""

    _require_api_key()
    from .core.service import build_radiology_case

    output_dir = Path(args.output)
    result = build_radiology_case(
        Path(args.input),
        model=args.model,
        cold=getattr(args, "cold", False),
    )
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
            decision_mode=getattr(args, "decision_mode", "llm"),
            cold=getattr(args, "cold", False),
            answers_path=Path(args.answers) if args.answers else None,
        )
        write_request_outputs(result, Path(args.output))

    print()
    print(f"Decision: {result.imaging_decision.decision_status}")
    review = result.teleradiology_request.clinician_review
    print(
        "Clinician call required: "
        f"{'YES' if result.imaging_decision.clinician_call_required or (review and review.action == 'contact_teleradiologist') else 'NO'}"
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
    review = result.teleradiology_request.clinician_review
    if review and review.action == "contact_teleradiologist":
        print("Examen proposé au radiologue : aucun — échange direct demandé par le clinicien")
        return
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
    elif decision.decision_status == "radiologist_selection_required":
        options = [decision.primary, *decision.secondary]
        names = [option.exam_name for option in options if option.exam_name]
        print(f"Choix transmis au radiologue : {' | '.join(names)}")
    else:
        print("Examen proposé au radiologue : aucun à ce stade — échange direct requis")


@dataclass(slots=True)
class _InteractiveRequestSession:
    args: argparse.Namespace
    core_result: CoreResult
    output_dir: Path
    reference_dir: Path | None
    result: RequestResult
    responder_role: str | None = None

    def reviewable(self) -> bool:
        return bool(
            self.result.radiology_handoff is not None
            and self.result.radiology_handoff.status == "ready_for_radiologist_review"
            and self.result.teleradiology_request.imaging_options
        )

    def render_review(self, review_action: str, nonce: str) -> str:
        from .request.handoff import render_radiology_handoff_html

        if self.result.radiology_handoff is None:
            return "<!doctype html><html lang=fr><body><p>Résultat disponible dans le terminal.</p></body></html>"
        return render_radiology_handoff_html(
            self.result.radiology_handoff,
            review_action=review_action if self.reviewable() else None,
            csp_nonce=nonce,
            responder_role=self.responder_role,
        )

    def finish_interaction(
        self,
        clarification: BrowserClarification,
        review_action: str,
        nonce: str,
    ) -> tuple[str, bool]:
        from .clarification_browser import (
            next_interactive_answer_path,
            write_interactive_answers,
        )
        from .request.service import run_request_from_core

        answer_path = next_interactive_answer_path(self.output_dir)
        write_interactive_answers(answer_path, clarification.answer_file)
        self.responder_role = next(
            (
                answer.responder_role
                for answer in clarification.answer_file.answers
                if answer.responder_role is not None
            ),
            None,
        )
        print(f"Clinician answers saved: {answer_path}")
        has_answer = any(
            item.value is not None and not (isinstance(item.value, str) and not item.value.strip())
            for item in clarification.answer_file.answers
        )
        if clarification.escalated or not has_answer:
            print("No new clinical answer was supplied; contact the teleradiologist directly.")
        else:
            print("Recalculating Request from the existing Core result...")
            self.result = run_request_from_core(
                self.core_result,
                reference_dir=self.reference_dir,
                model=self.args.model,
                decision_model=self.args.decision_model,
                decision_mode=getattr(self.args, "decision_mode", "llm"),
                cold=getattr(self.args, "cold", False),
                answers_path=answer_path,
            )
            write_request_outputs(self.result, self.output_dir)
        return self.render_review(review_action, nonce), self.reviewable()

    def record_review(self, browser_review: BrowserReview) -> str:
        from .clarification_browser import InvalidReviewError
        from .core.models import ClinicianRequestReview

        options = self.result.teleradiology_request.imaging_options
        index = browser_review.preferred_option_index
        if index is not None and index >= len(options):
            raise InvalidReviewError("invalid option")
        preference = options[index] if index is not None else None
        review = ClinicianRequestReview(
            action=browser_review.action,
            preferred_option=(preference if browser_review.action == "add_to_request" else None),
            responder_role=browser_review.responder_role,
            recorded_at=datetime.now(UTC),
        )
        request = self.result.teleradiology_request
        request.clinician_review = review
        if browser_review.action == "contact_teleradiologist":
            request.status = "blocked"
            request.warning = (
                "Demande automatique écartée par le clinicien. "
                "Échange direct avec le téléradiologue requis."
            )
        if self.result.radiology_handoff is not None:
            self.result.radiology_handoff.request = request
            if browser_review.action == "contact_teleradiologist":
                self.result.radiology_handoff.status = "clinician_contact_required"
                self.result.radiology_handoff.warnings.append(
                    "Le clinicien a écarté la demande automatique et demandé un échange direct."
                )
            self.result.radiology_case.referral["teleradiology_request"] = cast(
                JsonObject, request.model_dump(mode="json")
            )
            self.result.radiology_case.referral["radiology_handoff"] = cast(
                JsonObject, self.result.radiology_handoff.model_dump(mode="json")
            )
        write_request_outputs(self.result, self.output_dir)
        print(
            "Clinician preference saved."
            if browser_review.action == "add_to_request"
            else "Automatic request declined; contact the teleradiologist directly."
        )
        if self.result.radiology_handoff is None:
            return "<!doctype html><html lang=fr><body><p>Résultat enregistré.</p></body></html>"
        from .request.handoff import render_radiology_handoff_html

        return render_radiology_handoff_html(self.result.radiology_handoff)


def _run_interactive_request(args: argparse.Namespace) -> RequestResult:
    """Run one optional browser clarification round without repeating Core."""

    from .clarification_browser import collect_clinician_answers
    from .core.service import build_radiology_case
    from .request.clarification import required_clarification_questions
    from .request.service import run_request_from_core

    output_dir = Path(args.output)
    reference_dir = Path(args.reference) if args.reference else None
    core_result = build_radiology_case(
        Path(args.input),
        model=args.extraction_model or args.model,
        cold=getattr(args, "cold", False),
    )
    result = run_request_from_core(
        core_result,
        reference_dir=reference_dir,
        model=args.model,
        decision_model=args.decision_model,
        decision_mode=getattr(args, "decision_mode", "llm"),
        cold=getattr(args, "cold", False),
    )
    write_request_outputs(result, output_dir)
    session = _InteractiveRequestSession(args, core_result, output_dir, reference_dir, result)
    questions = required_clarification_questions(result.missing_questions)
    if questions:
        print(f"Opening a local clarification form for {len(questions)} required question(s)...")
    elif session.reviewable():
        print("Opening the local imaging-request review...")
    else:
        return result

    outcome = collect_clinician_answers(
        questions,
        on_submit=session.finish_interaction if questions else None,
        render_review=session.render_review,
        on_review=session.record_review,
    )
    if outcome is None:
        print("Interactive clarification was unavailable or timed out.")
    return session.result


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
    structure.add_argument(
        "--cold",
        action="store_true",
        help="Request temperature 0 when the selected model supports it",
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
        help="Open the local clarification and imaging-request review session",
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
    run.add_argument(
        "--decision-mode",
        choices=("llm", "deterministic", "shadow"),
        default="llm",
        help="Request decision engine mode (default: llm)",
    )
    run.add_argument(
        "--cold",
        action="store_true",
        help="Request temperature 0 for each compatible OpenAI model stage",
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
