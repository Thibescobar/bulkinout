from __future__ import annotations

from typing import Literal, cast

from ..core.models import (
    ClinicalCase,
    ClinicalField,
    FieldStatus,
    ImagingDecision,
    MissingQuestion,
    PriorImaging,
    TeleradiologyRequest,
)
from ..types import JsonValue


def _clean_value(section: dict[str, ClinicalField], key: str) -> JsonValue:
    f = section.get(key)
    if not f or f.status in {FieldStatus.unknown, FieldStatus.conflicting}:
        return None
    return f.value


def _patient_summary(case: ClinicalCase) -> str | None:
    parts: list[str] = []
    age = _clean_value(case.patient, "age")
    sex = _clean_value(case.patient, "sex")
    if age is not None:
        parts.append(f"{age} ans")
    if sex:
        parts.append(str(sex))
    return ", ".join(parts) or None


def _labeled_values(
    fields: list[tuple[dict[str, ClinicalField], str, str]],
    *,
    omit_falsy: bool = False,
) -> list[str]:
    values: list[str] = []
    for section, key, label in fields:
        value = _clean_value(section, key)
        if value is not None and (not omit_falsy or bool(value)):
            values.append(f"{label}: {value}")
    return values


def _prior_imaging_summary(prior_imaging: list[PriorImaging]) -> list[str]:
    summaries: list[str] = []
    for item in prior_imaging:
        parts = [
            f"{label}={field.value}"
            for label, field in [
                ("modalité", item.modality),
                ("région", item.region),
                ("date", item.date),
                ("résultat", item.result),
            ]
            if field.status not in {FieldStatus.unknown, FieldStatus.conflicting} and field.value
        ]
        if parts:
            summaries.append("; ".join(parts))
    return summaries


def _request_status(
    decision: ImagingDecision, questions: list[MissingQuestion]
) -> Literal["draft", "ready_for_human_approval", "blocked"]:
    if any(question.blocking for question in questions) or decision.clinician_call_required:
        return "blocked"
    if decision.decision_ready_for_human_approval:
        return "ready_for_human_approval"
    return "draft"


def build_teleradiology_request(
    case: ClinicalCase,
    decision: ImagingDecision,
    questions: list[MissingQuestion],
) -> TeleradiologyRequest:
    primary = decision.primary
    history = _labeled_values(
        [
            (case.history, "oncology", "Oncologie"),
            (case.history, "surgery", "Chirurgie"),
            (case.history, "trauma", "Traumatisme"),
            (case.history, "relevant_conditions", "ATCD pertinents"),
        ],
        omit_falsy=True,
    )
    medications_and_allergies = _labeled_values(
        [
            (case.medications, "anticoagulation", "Anticoagulation"),
            (case.medications, "metformin", "Metformine"),
            (case.allergies, "iodinated_contrast_reaction", "Réaction contraste iodé"),
            (case.allergies, "gadolinium_reaction", "Réaction gadolinium"),
        ]
    )
    labs = _labeled_values(
        [
            (case.labs, "egfr_ml_min_1_73m2", "DFG/eGFR"),
            (case.labs, "creatinine", "Créatinine"),
            (case.labs, "pregnancy_test", "Test grossesse"),
        ]
    )
    safety = _labeled_values(
        [
            (case.imaging_safety, "pregnancy", "Grossesse"),
            (case.imaging_safety, "pacemaker", "Pacemaker/DAI"),
            (case.imaging_safety, "implant_or_metal", "Implant/métal"),
            (case.imaging_safety, "mri_compatibility", "Compatibilité IRM"),
            (case.imaging_safety, "claustrophobia", "Claustrophobie"),
        ]
    )

    return TeleradiologyRequest(
        status=_request_status(decision, questions),
        patient_summary=_patient_summary(case),
        indication=cast(str | None, _clean_value(case.current_problem, "indication")),
        requested_exam=primary.exam_name
        or " ".join(filter(None, [primary.modality, primary.body_region])),
        protocol_requested=primary.protocol,
        contrast=primary.contrast,
        urgency=primary.urgency,
        clinical_question=primary.clinical_question_for_radiologist,
        relevant_history=history,
        medications_and_allergies=medications_and_allergies,
        relevant_labs=labs,
        relevant_prior_imaging=_prior_imaging_summary(case.prior_imaging),
        safety_information=safety,
        unresolved_items=[question.question for question in questions],
        rationale_for_exam=primary.rationale,
    )
