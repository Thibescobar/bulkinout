from __future__ import annotations

from ..core.models import ClinicalCase, DiscriminatingQuestion, FieldStatus, ImagingDecision
from ..types import JsonValue


def _get_case_value(case: ClinicalCase, field_path: str) -> tuple[JsonValue, bool]:
    if "." not in field_path:
        return None, True
    section_name, key = field_path.split(".", 1)
    section = getattr(case, section_name, None)
    if not isinstance(section, dict):
        return None, True
    f = section.get(key)
    if f is None or f.status in {FieldStatus.unknown, FieldStatus.conflicting}:
        return None, True
    return f.value, False


def _unresolved_required_questions(
    case: ClinicalCase, decision: ImagingDecision
) -> list[DiscriminatingQuestion]:
    return [
        question
        for question in decision.discriminating_questions
        if question.required_to_choose and _get_case_value(case, question.field)[1]
    ]


def _block_unresolved_questions(
    decision: ImagingDecision, questions: list[DiscriminatingQuestion]
) -> None:
    decision.decision_status = "insufficient_information"
    decision.primary.recommended = False
    decision.decision_ready_for_human_approval = False
    decision.clinician_call_required = True
    decision.primary.missing_information = list(
        dict.fromkeys(
            decision.primary.missing_information + [question.question for question in questions]
        )
    )
    for question in questions:
        reason = f"{question.question} — {question.why_it_matters}"
        if reason not in decision.clinician_call_reasons:
            decision.clinician_call_reasons.append(reason)


def _normalize_readiness(decision: ImagingDecision) -> None:
    if decision.decision_status == "selected" and decision.primary.recommended:
        decision.decision_ready_for_human_approval = True
    elif decision.decision_status in {"insufficient_information", "safety_blocked"}:
        decision.clinician_call_required = True
        decision.decision_ready_for_human_approval = False
    elif decision.decision_status == "no_imaging_recommended":
        decision.primary.recommended = False
        decision.decision_ready_for_human_approval = True


def enforce_decision_guard(case: ClinicalCase, decision: ImagingDecision) -> ImagingDecision:
    """Prevent selection while a required discriminating question is unresolved."""

    unresolved = _unresolved_required_questions(case, decision)
    if unresolved:
        _block_unresolved_questions(decision, unresolved)
    _normalize_readiness(decision)
    return decision
