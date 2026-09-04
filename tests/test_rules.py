from bulkinout.core.models import (
    ClinicalCase, ClinicalField, FieldStatus,
    ImagingDecision, ImagingRecommendation
)
from bulkinout.request.rules import generic_missing_questions, recommendation_specific_questions


def observed(v):
    return ClinicalField(value=v, status=FieldStatus.observed, confidence=1.0)


def test_generic_missing_indication():
    case = ClinicalCase()
    qs = generic_missing_questions(case)
    fields = {q.field for q in qs}
    assert "current_problem.indication" in fields


def test_ct_contrast_adds_specific_checks():
    case = ClinicalCase()
    case.current_problem["indication"] = observed("douleur abdominale aiguë")
    case.patient["sex"] = observed("M")

    decision = ImagingDecision(
        primary=ImagingRecommendation(
            modality="CT",
            exam_name="TDM abdomino-pelvienne",
            contrast="yes",
            urgency="urgent",
            confidence=0.8,
        )
    )
    qs = recommendation_specific_questions(case, decision)
    fields = {q.field for q in qs}
    assert "allergies.iodinated_contrast_reaction" in fields
    assert "labs.egfr_ml_min_1_73m2" in fields
    assert "imaging_safety.pregnancy" not in fields


def test_mri_requires_device_information():
    case = ClinicalCase()
    case.current_problem["indication"] = observed("céphalées")
    decision = ImagingDecision(
        primary=ImagingRecommendation(
            modality="MRI",
            exam_name="IRM cérébrale",
            contrast="no",
            urgency="routine",
            confidence=0.8,
        )
    )
    qs = recommendation_specific_questions(case, decision)
    fields = {q.field for q in qs}
    assert "imaging_safety.pacemaker" in fields
    assert "imaging_safety.implant_or_metal" in fields
