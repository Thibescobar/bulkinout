from bulkinout.request.decision_guard import enforce_decision_guard
from bulkinout.core.models import (
    ClinicalCase, ClinicalField, FieldStatus, CandidateExam,
    DiscriminatingQuestion, ImagingDecision, ImagingRecommendation
)


def test_unanswered_required_discriminator_blocks_selection():
    case = ClinicalCase()
    decision = ImagingDecision(
        decision_status="selected",
        candidates=[
            CandidateExam(
                candidate_id="a",
                exam_name="CT A",
                modality="CT",
                body_region="abdomen",
                fit_score=0.7,
            )
        ],
        discriminating_questions=[
            DiscriminatingQuestion(
                question_id="q1",
                field="current_problem.location",
                question="Où est la douleur ?",
                why_it_matters="Change le protocole",
                priority=1,
                candidate_ids_affected=["a"],
                possible_decision_impact="Peut changer l'examen",
                required_to_choose=True,
            )
        ],
        primary=ImagingRecommendation(
            recommended=True,
            modality="CT",
            exam_name="CT A",
            contrast="yes",
            confidence=0.7,
        ),
        clinician_call_required=False,
        decision_ready_for_human_approval=True,
    )

    out = enforce_decision_guard(case, decision)
    assert out.decision_status == "insufficient_information"
    assert out.primary.recommended is False
    assert out.clinician_call_required is True
    assert out.decision_ready_for_human_approval is False


def test_answered_discriminator_allows_selected_state():
    case = ClinicalCase()
    case.current_problem["location"] = ClinicalField(
        value="flanc droit",
        status=FieldStatus.observed,
        confidence=1.0,
    )
    decision = ImagingDecision(
        decision_status="selected",
        discriminating_questions=[
            DiscriminatingQuestion(
                question_id="q1",
                field="current_problem.location",
                question="Où est la douleur ?",
                why_it_matters="Change le protocole",
                priority=1,
                candidate_ids_affected=["a"],
                possible_decision_impact="Peut changer l'examen",
                required_to_choose=True,
            )
        ],
        primary=ImagingRecommendation(
            recommended=True,
            modality="CT",
            exam_name="CT A",
            contrast="yes",
            confidence=0.8,
        ),
        clinician_call_required=False,
        decision_ready_for_human_approval=True,
    )

    out = enforce_decision_guard(case, decision)
    assert out.decision_status == "selected"
    assert out.primary.recommended is True
    assert out.decision_ready_for_human_approval is True
