from __future__ import annotations

from ..core.models import (
    ClinicalCase,
    FieldStatus,
    ImagingDecision,
    MissingQuestion,
    TeleradiologyRequest,
)


def _clean_value(section, key):
    f = section.get(key)
    if not f or f.status in {FieldStatus.unknown, FieldStatus.conflicting}:
        return None
    return f.value


def _fmt(label, value):
    return f"{label}: {value}" if value not in (None, "", []) else None


def build_teleradiology_request(
    case: ClinicalCase,
    decision: ImagingDecision,
    questions: list[MissingQuestion],
) -> TeleradiologyRequest:
    p = decision.primary

    patient_bits = []
    age = _clean_value(case.patient, "age")
    sex = _clean_value(case.patient, "sex")
    if age is not None:
        patient_bits.append(f"{age} ans")
    if sex:
        patient_bits.append(str(sex))

    hist = []
    for k, label in [
        ("oncology", "Oncologie"),
        ("surgery", "Chirurgie"),
        ("trauma", "Traumatisme"),
        ("relevant_conditions", "ATCD pertinents"),
    ]:
        v = _clean_value(case.history, k)
        if v:
            hist.append(f"{label}: {v}")

    meds_allergies = []
    for section, k, label in [
        (case.medications, "anticoagulation", "Anticoagulation"),
        (case.medications, "metformin", "Metformine"),
        (case.allergies, "iodinated_contrast_reaction", "Réaction contraste iodé"),
        (case.allergies, "gadolinium_reaction", "Réaction gadolinium"),
    ]:
        v = _clean_value(section, k)
        if v is not None:
            meds_allergies.append(f"{label}: {v}")

    labs = []
    for k, label in [
        ("egfr_ml_min_1_73m2", "DFG/eGFR"),
        ("creatinine", "Créatinine"),
        ("pregnancy_test", "Test grossesse"),
    ]:
        v = _clean_value(case.labs, k)
        if v is not None:
            labs.append(f"{label}: {v}")

    safety = []
    for k, label in [
        ("pregnancy", "Grossesse"),
        ("pacemaker", "Pacemaker/DAI"),
        ("implant_or_metal", "Implant/métal"),
        ("mri_compatibility", "Compatibilité IRM"),
        ("claustrophobia", "Claustrophobie"),
    ]:
        v = _clean_value(case.imaging_safety, k)
        if v is not None:
            safety.append(f"{label}: {v}")

    priors = []
    for x in case.prior_imaging:
        parts = []
        for label, f in [
            ("modalité", x.modality), ("région", x.region), ("date", x.date), ("résultat", x.result)
        ]:
            if f.status not in {FieldStatus.unknown, FieldStatus.conflicting} and f.value:
                parts.append(f"{label}={f.value}")
        if parts:
            priors.append("; ".join(parts))

    unresolved = [q.question for q in questions]
    blocking = any(q.blocking for q in questions)

    if blocking or decision.clinician_call_required:
        status = "blocked"
    elif decision.decision_ready_for_human_approval:
        status = "ready_for_human_approval"
    else:
        status = "draft"

    return TeleradiologyRequest(
        status=status,
        patient_summary=", ".join(patient_bits) or None,
        indication=_clean_value(case.current_problem, "indication"),
        requested_exam=p.exam_name or " ".join(filter(None, [p.modality, p.body_region])),
        protocol_requested=p.protocol,
        contrast=p.contrast,
        urgency=p.urgency,
        clinical_question=p.clinical_question_for_radiologist,
        relevant_history=hist,
        medications_and_allergies=meds_allergies,
        relevant_labs=labs,
        relevant_prior_imaging=priors,
        safety_information=safety,
        unresolved_items=unresolved,
        rationale_for_exam=p.rationale,
    )
