"""Application service for the complete pre-exam Request workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .. import __version__
from ..core.models import (
    ClinicalCase,
    FieldStatus,
    ImagingDecision,
    LLMExtraction,
    MissingQuestion,
    RadiologyCase,
    TeleradiologyRequest,
)
from ..core.interfaces import CoreExtractor
from ..core.service import build_radiology_case
from ..run_manifest import UNREPORTED, RunManifest, build_run_manifest
from ..types import JsonObject
from .answers import apply_answers, load_answers
from .decision_guard import enforce_decision_guard
from .decision_llm import OpenAIRequestDecision
from .interfaces import RequestDecisionEngine
from .reference_engine import ReferenceEngine
from .request_builder import build_teleradiology_request
from .rules import generic_missing_questions, recommendation_specific_questions
from .types import ReferenceContext, ReferenceScenario

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
    run_manifest: RunManifest | None = None


def _record_missing_requirements(
    decision: ImagingDecision, questions: list[MissingQuestion]
) -> None:
    for question in questions:
        if question.question not in decision.primary.missing_information:
            decision.primary.missing_information.append(question.question)
        if question.question not in decision.clinician_call_reasons:
            decision.clinician_call_reasons.append(question.question)


def _reference_missing_questions(reference_context: ReferenceContext) -> list[MissingQuestion]:
    questions: list[MissingQuestion] = []
    for scenario in reference_context["matched_scenarios"]:
        for reference_question in scenario["unresolved_material_questions"]:
            blocking = reference_question.get("blocking", False)
            required = reference_question.get("required_to_choose", False) or blocking
            if not required:
                continue
            questions.append(
                MissingQuestion(
                    question_id=reference_question["id"],
                    field=reference_question["field"],
                    question=reference_question["question"],
                    importance="critical" if blocking else "high",
                    reason=reference_question.get(
                        "reason", "Required by the matched reference scenario."
                    ),
                    material=reference_question.get("material", False),
                    required_to_choose=required,
                    blocking=blocking,
                )
            )
    return questions


def _llm_missing_questions(case: ClinicalCase, decision: ImagingDecision) -> list[MissingQuestion]:
    questions: list[MissingQuestion] = []
    for question in decision.discriminating_questions:
        section_name, separator, key = question.field.partition(".")
        section = getattr(case, section_name, None)
        field = section.get(key) if separator and isinstance(section, dict) else None
        if field is not None and field.status not in {FieldStatus.unknown, FieldStatus.conflicting}:
            continue
        questions.append(
            MissingQuestion(
                question_id=question.question_id,
                field=question.field,
                question=question.question,
                importance="high" if question.required_to_choose else "medium",
                reason=question.why_it_matters,
                material=True,
                required_to_choose=question.required_to_choose,
            )
        )
    return questions


_IMPORTANCE = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _merge_questions(*groups: list[MissingQuestion]) -> list[MissingQuestion]:
    """Deduplicate by canonical field while retaining the strongest constraints."""

    merged: dict[str, MissingQuestion] = {}
    for question in (question for group in groups for question in group):
        existing = merged.get(question.field)
        if existing is None:
            merged[question.field] = question.model_copy(
                update={"required_to_choose": question.required_to_choose or question.blocking}
            )
            continue
        strongest = max(
            (existing, question),
            key=lambda item: (
                item.blocking,
                item.required_to_choose,
                item.material,
                _IMPORTANCE[item.importance],
            ),
        )
        merged[question.field] = strongest.model_copy(
            update={
                "importance": max(
                    (existing.importance, question.importance), key=_IMPORTANCE.__getitem__
                ),
                "material": existing.material or question.material,
                "required_to_choose": (
                    existing.required_to_choose
                    or question.required_to_choose
                    or existing.blocking
                    or question.blocking
                ),
                "blocking": existing.blocking or question.blocking,
                "answerable_from_existing_docs": (
                    existing.answerable_from_existing_docs or question.answerable_from_existing_docs
                ),
            }
        )
    return list(merged.values())


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
        decision.primary.recommended = False
        _record_missing_requirements(decision, blocking)

    modality_required_fields = {
        question.field
        for question in specific_questions
        if question.importance in {"critical", "high"}
    }
    required = [
        question
        for question in all_questions
        if (question.required_to_choose or question.field in modality_required_fields)
        and not question.blocking
    ]
    if not required:
        return

    decision.clinician_call_required = True
    decision.decision_ready_for_human_approval = False
    decision.primary.recommended = False
    if decision.decision_status == "selected":
        decision.decision_status = "insufficient_information"
    _record_missing_requirements(decision, required)


def run_request(
    input_dir: Path,
    *,
    reference_dir: Path | None = None,
    model: str | None = None,
    extraction_model: str | None = None,
    decision_model: str | None = None,
    answers_path: Path | None = None,
    extractor: CoreExtractor | None = None,
    decision_engine: RequestDecisionEngine | None = None,
) -> RequestResult:
    """Run Core, reference matching, decision support, and deterministic safeguards."""

    core_result = build_radiology_case(
        input_dir,
        model=extraction_model or model,
        extractor=extractor,
    )
    radiology_case = core_result.radiology_case
    case = radiology_case.clinical

    if answers_path is not None:
        case = apply_answers(case, load_answers(answers_path), answers_path.name)
        radiology_case.clinical = case

    initial_questions = generic_missing_questions(case)
    reference_engine = ReferenceEngine(reference_dir)
    reference_context = reference_engine.build_context(case)
    reference_questions = _reference_missing_questions(reference_context)
    selected_decision_engine = decision_engine or OpenAIRequestDecision(
        model=decision_model or model
    )
    decision = selected_decision_engine.decide(
        case,
        [cast(JsonObject, question.model_dump(mode="json")) for question in initial_questions],
        reference_context=reference_context,
    )
    decision = enforce_decision_guard(case, decision)

    llm_questions = _llm_missing_questions(case, decision)
    specific_questions = recommendation_specific_questions(case, decision)
    all_questions = _merge_questions(
        initial_questions,
        reference_questions,
        llm_questions,
        specific_questions,
    )
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
    recorded_core_model = case.metadata.get("model")
    recorded_core_component = case.metadata.get("extractor_manifest")
    recorded_reference_revision = getattr(reference_engine, "reference_revision", UNREPORTED)
    loaded_scenarios = getattr(reference_engine, "scenarios", [])
    manifest_inputs = core_result.source_paths + (
        [answers_path] if answers_path is not None else []
    )
    run_manifest = build_run_manifest(
        package_version=__version__,
        source_paths=manifest_inputs,
        core_component=(
            recorded_core_component if isinstance(recorded_core_component, dict) else {}
        ),
        core_model=recorded_core_model if isinstance(recorded_core_model, str) else None,
        request_component=selected_decision_engine,
        reference_revision=(
            recorded_reference_revision
            if isinstance(recorded_reference_revision, str)
            else UNREPORTED
        ),
        reference_scenarios=cast(list[ReferenceScenario], loaded_scenarios),
        reference_context=reference_context,
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
        run_manifest=run_manifest,
    )
