"""Application service for the complete pre-exam Request workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from ..core.models import (
    ClinicalCase,
    ImagingDecision,
    LLMExtraction,
    MissingQuestion,
    RadiologyCase,
    TeleradiologyRequest,
)
from ..core.service import build_radiology_case
from ..types import JsonObject
from .answers import apply_answers, load_answers
from .decision_guard import enforce_decision_guard
from .decision_llm import OpenAIRequestDecision
from .reference_engine import ReferenceEngine
from .request_builder import build_teleradiology_request
from .rules import generic_missing_questions, recommendation_specific_questions
from .types import ReferenceContext

SAFETY_FIELDS = frozenset(
    {
        "imaging_safety.pacemaker",
        "imaging_safety.implant_or_metal",
        "imaging_safety.pregnancy",
        "allergies.iodinated_contrast_reaction",
        "allergies.gadolinium_reaction",
    }
)


@dataclass(slots=True)
class RequestResult:
    """Typed in-memory result of a Request workflow run."""

    radiology_case: RadiologyCase
    extraction: LLMExtraction
    clinical_case: ClinicalCase
    reference_context: ReferenceContext
    missing_questions: list[MissingQuestion]
    imaging_decision: ImagingDecision
    teleradiology_request: TeleradiologyRequest
    source_paths: list[Path]


def _add_call_reasons(decision: ImagingDecision, questions: list[MissingQuestion]) -> None:
    for question in questions:
        if question.question not in decision.clinician_call_reasons:
            decision.clinician_call_reasons.append(question.question)


def _apply_question_guards(
    decision: ImagingDecision,
    all_questions: list[MissingQuestion],
    specific_questions: list[MissingQuestion],
) -> None:
    blocking = [question for question in all_questions if question.blocking]
    if blocking:
        decision.decision_status = (
            "safety_blocked"
            if any(question.field in SAFETY_FIELDS for question in blocking)
            else "insufficient_information"
        )
        decision.clinician_call_required = True
        decision.decision_ready_for_human_approval = False
        _add_call_reasons(decision, blocking)

    material = [
        question for question in specific_questions if question.importance in {"critical", "high"}
    ]
    if not material:
        return

    decision.clinician_call_required = True
    decision.decision_ready_for_human_approval = False
    if any(question.blocking for question in material):
        decision.decision_status = "safety_blocked"
    elif decision.decision_status == "selected":
        decision.decision_status = "insufficient_information"
    _add_call_reasons(decision, material)


def run_request(
    input_dir: Path,
    *,
    reference_dir: Path = Path("reference/scenarios"),
    model: str | None = None,
    answers_path: Path | None = None,
) -> RequestResult:
    """Run Core, reference matching, decision support, and deterministic safeguards."""

    core_result = build_radiology_case(input_dir, model=model)
    radiology_case = core_result.radiology_case
    case = radiology_case.clinical

    if answers_path is not None:
        case = apply_answers(case, load_answers(answers_path), answers_path.name)
        radiology_case.clinical = case

    initial_questions = generic_missing_questions(case)
    reference_context = ReferenceEngine(reference_dir).build_context(case)
    decision = OpenAIRequestDecision(model=model).decide(
        case,
        [cast(JsonObject, question.model_dump(mode="json")) for question in initial_questions],
        reference_context=reference_context,
    )
    decision = enforce_decision_guard(case, decision)

    specific_questions = recommendation_specific_questions(case, decision)
    questions_by_field = {
        question.field: question for question in initial_questions + specific_questions
    }
    all_questions = list(questions_by_field.values())
    _apply_question_guards(decision, all_questions, specific_questions)

    request = build_teleradiology_request(case, decision, all_questions)
    radiology_case.referral = {
        "reference_context": cast(JsonObject, reference_context),
        "imaging_decision": cast(JsonObject, decision.model_dump(mode="json")),
        "teleradiology_request": cast(JsonObject, request.model_dump(mode="json")),
    }
    radiology_case.audit.append(
        {"event": "request_workflow_completed", "decision_status": decision.decision_status}
    )

    return RequestResult(
        radiology_case=radiology_case,
        extraction=core_result.extraction,
        clinical_case=case,
        reference_context=reference_context,
        missing_questions=all_questions,
        imaging_decision=decision,
        teleradiology_request=request,
        source_paths=core_result.source_paths,
    )
