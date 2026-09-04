from __future__ import annotations

from ..core.models import ImagingDecision, FieldStatus, ClinicalCase


def _get_case_value(case: ClinicalCase, field_path: str):
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


def enforce_decision_guard(case: ClinicalCase, decision: ImagingDecision) -> ImagingDecision:
    """
    Deterministic guard:
    an unanswered discriminating question marked required_to_choose prevents selection.
    """
    unresolved_required = []
    for q in decision.discriminating_questions:
        _, unknown = _get_case_value(case, q.field)
        if q.required_to_choose and unknown:
            unresolved_required.append(q)

    if unresolved_required:
        decision.decision_status = "insufficient_information"
        decision.primary.recommended = False
        decision.decision_ready_for_human_approval = False
        decision.clinician_call_required = True
        decision.primary.missing_information = list(dict.fromkeys(
            decision.primary.missing_information + [q.question for q in unresolved_required]
        ))
        for q in unresolved_required:
            reason = f"{q.question} — {q.why_it_matters}"
            if reason not in decision.clinician_call_reasons:
                decision.clinician_call_reasons.append(reason)

    if decision.decision_status == "selected":
        # A selected decision cannot simultaneously claim a required unanswered discriminator.
        if unresolved_required:
            decision.decision_status = "insufficient_information"
        elif decision.primary.recommended:
            decision.decision_ready_for_human_approval = True

    if decision.decision_status in {"insufficient_information", "safety_blocked"}:
        decision.clinician_call_required = True
        decision.decision_ready_for_human_approval = False

    if decision.decision_status == "no_imaging_recommended":
        decision.primary.recommended = False
        decision.decision_ready_for_human_approval = True

    return decision
