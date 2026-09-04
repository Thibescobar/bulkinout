from bulkinout.core.models import (
    ClinicalCase,
    ClinicalField,
    FieldStatus,
    ImagingDecision,
    ImagingRecommendation,
    MissingQuestion,
    PriorImaging,
)
from bulkinout.request.request_builder import _fmt, build_teleradiology_request


def field(value, status=FieldStatus.observed):
    return ClinicalField(value=value, status=status, confidence=1.0)


def recommendation(**overrides):
    values = {
        "modality": "CT",
        "body_region": "abdomen",
        "exam_name": "CT abdomen",
        "protocol": "portal phase",
        "contrast": "yes",
        "urgency": "urgent",
        "clinical_question_for_radiologist": "Appendicitis?",
        "rationale": ["Right lower quadrant pain"],
    }
    values.update(overrides)
    return ImagingRecommendation(**values)


def test_format_helper_omits_empty_values():
    assert _fmt("Age", 42) == "Age: 42"
    assert _fmt("Age", None) is None
    assert _fmt("Age", []) is None


def test_build_request_collects_relevant_clinical_information():
    case = ClinicalCase(
        patient={"age": field(42), "sex": field("F")},
        current_problem={"indication": field("Right lower quadrant pain")},
        history={
            "oncology": field("breast cancer"),
            "surgery": field(None, FieldStatus.unknown),
            "trauma": field("none"),
        },
        medications={"anticoagulation": field(False), "metformin": field(True)},
        allergies={
            "iodinated_contrast_reaction": field("urticaria"),
            "gadolinium_reaction": field("uncertain", FieldStatus.conflicting),
        },
        labs={"egfr_ml_min_1_73m2": field(80), "creatinine": field(70)},
        imaging_safety={"pregnancy": field(False), "pacemaker": field(False)},
        prior_imaging=[
            PriorImaging(
                modality=field("US"),
                region=field("abdomen"),
                date=field("2025-01-02"),
                result=field("normal"),
            ),
            PriorImaging(modality=field(None, FieldStatus.unknown)),
        ],
    )
    decision = ImagingDecision(
        decision_status="selected",
        primary=recommendation(),
        clinician_call_required=False,
        decision_ready_for_human_approval=True,
    )

    result = build_teleradiology_request(case, decision, [])

    assert result.status == "ready_for_human_approval"
    assert result.patient_summary == "42 ans, F"
    assert result.indication == "Right lower quadrant pain"
    assert result.requested_exam == "CT abdomen"
    assert result.relevant_history == ["Oncologie: breast cancer", "Traumatisme: none"]
    assert result.medications_and_allergies == [
        "Anticoagulation: False",
        "Metformine: True",
        "Réaction contraste iodé: urticaria",
    ]
    assert result.relevant_labs == ["DFG/eGFR: 80", "Créatinine: 70"]
    assert result.safety_information == ["Grossesse: False", "Pacemaker/DAI: False"]
    assert result.relevant_prior_imaging == [
        "modalité=US; région=abdomen; date=2025-01-02; résultat=normal"
    ]


def test_blocking_question_blocks_request():
    question = MissingQuestion(
        field="imaging_safety.pregnancy",
        question="Pregnancy?",
        importance="high",
        reason="Radiation safety",
        blocking=True,
    )
    decision = ImagingDecision(
        primary=recommendation(),
        clinician_call_required=False,
        decision_ready_for_human_approval=True,
    )

    result = build_teleradiology_request(ClinicalCase(), decision, [question])

    assert result.status == "blocked"
    assert result.patient_summary is None
    assert result.unresolved_items == ["Pregnancy?"]


def test_request_uses_modality_and_region_fallback_and_draft_status():
    decision = ImagingDecision(
        primary=recommendation(exam_name=None, modality="MRI", body_region="brain"),
        clinician_call_required=False,
        decision_ready_for_human_approval=False,
    )

    result = build_teleradiology_request(ClinicalCase(), decision, [])

    assert result.status == "draft"
    assert result.requested_exam == "MRI brain"
