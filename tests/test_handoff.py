from datetime import UTC, datetime

from bulkinout.core.models import (
    AnswerFile,
    AnswerItem,
    CandidateExam,
    ClinicalCase,
    ClinicalField,
    FieldStatus,
    ImagingDecision,
    ImagingRecommendation,
    MissingQuestion,
    SourceRef,
    TeleradiologyRequest,
)
from bulkinout.request.answers import apply_answers
from bulkinout.request.handoff import build_radiology_handoff, render_radiology_handoff_html


def observed(value, filename="note.md"):
    return ClinicalField(
        value=value,
        status=FieldStatus.observed,
        confidence=0.95,
        sources=[SourceRef(document_id=f"input:{filename}", filename=filename)],
    )


def reference_context():
    return {
        "matched_scenarios": [
            {
                "id": "rlq_appendicitis",
                "title": "Right lower quadrant pain",
                "match_score": 1.0,
                "version": "0.1.0",
                "status": "needs_local_validation",
                "sources": [
                    {
                        "organization": "ACR",
                        "title": "Right Lower Quadrant Pain",
                        "url": "https://example.test/acr",
                    }
                ],
                "candidate_exams": [
                    {
                        "id": "ct_iv",
                        "exam_name": "TDM abdomino-pelvienne avec injection IV",
                        "modality": "CT",
                        "contrast": "yes",
                        "appropriateness": "usually_appropriate",
                    }
                ],
                "unresolved_material_questions": [],
                "rules_triggered": [
                    {"rule_id": "LOCAL_RULE", "result": {"preferred_candidate": "ct_iv"}}
                ],
            }
        ]
    }


def test_handoff_follows_clinical_facts_answers_reference_and_proposal():
    case = ClinicalCase(
        current_problem={"indication": observed("Douleur de fosse iliaque droite")},
        labs={"egfr_ml_min_1_73m2": observed(92, "laboratory.pdf")},
    )
    case = apply_answers(
        case,
        AnswerFile(
            answers=[
                AnswerItem(
                    question_id="pregnancy",
                    field="imaging_safety.pregnancy",
                    value=False,
                    question="Une grossesse est-elle possible ou en cours ?",
                    possible_decision_impact="Modifie la stratégie d'imagerie.",
                    responder_role="emergency_clinician",
                    answered_at=datetime(2026, 9, 4, 10, 30, tzinfo=UTC),
                    response_method="interactive_browser",
                )
            ]
        ),
        "answers.interactive.1.json",
    )
    decision = ImagingDecision(
        decision_status="selected",
        candidates=[
            CandidateExam(
                candidate_id="ct_iv",
                exam_name="TDM abdomino-pelvienne avec injection IV",
                modality="CT",
                body_region="abdomen and pelvis",
                contrast="yes",
                fit_score=0.9,
            )
        ],
        primary=ImagingRecommendation(
            exam_name="TDM abdomino-pelvienne avec injection IV",
            modality="CT",
            contrast="yes",
            rationale=["Tableau compatible avec une appendicite."],
            alternatives=["Échographie selon le contexte."],
        ),
        clinician_call_required=False,
        decision_ready_for_human_approval=True,
    )
    request = TeleradiologyRequest(
        status="ready_for_human_approval",
        patient_summary="Adulte, douleur aiguë",
        indication="Douleur de fosse iliaque droite",
        clinical_question="Appendicite ?",
        contrast="Injection IV proposée",
        relevant_history=["Douleur aiguë depuis six heures."],
        relevant_labs=["DFG : 92"],
    )

    handoff = build_radiology_handoff(case, decision, [], request, reference_context())

    assert handoff.status == "ready_for_radiologist_review"
    assert {fact.field for fact in handoff.supporting_facts} == {
        "current_problem.indication",
        "imaging_safety.pregnancy",
        "labs.egfr_ml_min_1_73m2",
    }
    assert {fact.field for fact in handoff.safety_facts} == {
        "imaging_safety.pregnancy",
        "labs.egfr_ml_min_1_73m2",
    }
    assert handoff.clarifications[0].answer is False
    assert handoff.clarifications[0].responder_role == "emergency_clinician"
    assert handoff.decision_trace.selected_reference_candidate == "rlq_appendicitis:ct_iv"
    assert handoff.decision_trace.triggered_rules[0]["relationship"] == ("local_rule_triggered")
    assert handoff.citations[0].organization == "ACR"
    assert handoff.citations[0].relationship == "scenario_background"

    html = render_radiology_handoff_html(handoff)
    assert "Proposition à valider par le radiologue" in html
    assert "Demande clinique" in html
    assert "Appendicite ?" in html
    assert "Examen proposé" in html
    assert "Examen proposé au radiologue" in html
    assert "Synthèse clinique transmise" in html
    assert "Douleur aiguë depuis six heures." in html
    assert "DFG : 92" in html
    assert "Modifie la stratégie d&#x27;imagerie." in html
    assert "2026-09-04T10:30:00Z" in html
    assert "note.md" in html
    assert "Aucune proposition transmissible" not in html
    assert "Right Lower Quadrant Pain" in html
    assert "answers.interactive.1.json" in html
    assert "https://example.test/acr" in html


def test_blocked_handoff_keeps_unanswered_questions_and_escapes_html():
    question = MissingQuestion(
        field="current_problem.onset",
        question="Début <script>alert('x')</script> ?",
        importance="critical",
        reason="Changes urgency.",
        required_to_choose=True,
        clinical_reason="Modifie l'urgence.",
    )
    decision = ImagingDecision(
        decision_status="insufficient_information",
        primary=ImagingRecommendation(recommended=False),
        clinician_call_required=True,
    )
    request = TeleradiologyRequest(status="blocked")

    handoff = build_radiology_handoff(
        ClinicalCase(), decision, [question], request, {"matched_scenarios": []}
    )
    html = render_radiology_handoff_html(handoff)

    assert handoff.status == "clinician_contact_required"
    assert handoff.clarifications[0].state == "unanswered"
    assert handoff.unresolved_questions == [question]
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Aucun fait structuré disponible" in html
    assert "Aucune référence documentaire associée" in html
    assert "Aucune proposition transmissible à ce stade" in html
    assert "Examen envisagé, non proposé" in html


def test_blocked_handoff_does_not_present_raw_model_exam_as_a_recommendation():
    decision = ImagingDecision(
        decision_status="safety_blocked",
        primary=ImagingRecommendation(
            recommended=True,
            exam_name="TDM envisagée par le modèle",
            rationale=["Raisonnement brut conservé pour audit."],
        ),
        clinician_call_required=True,
    )
    handoff = build_radiology_handoff(
        ClinicalCase(),
        decision,
        [],
        TeleradiologyRequest(status="blocked", requested_exam="TDM envisagée"),
        {"matched_scenarios": []},
    )

    html = render_radiology_handoff_html(handoff)

    assert "Aucune proposition transmissible à ce stade" in html
    assert "Examen envisagé, non proposé" in html
    assert "<strong>Examen proposé" not in html


def test_draft_handoff_skips_unknown_and_malformed_metadata_without_losing_values():
    case = ClinicalCase(
        medications={"metformin": observed(True)},
        current_problem={
            "symptoms": observed(["douleur", "nausées"]),
            "unknown_detail": ClinicalField(),
        },
        metadata={
            "clarifications": [
                "invalid",
                {"field": 42},
                {
                    "field": "current_problem.detail",
                    "question": "Détail ?",
                    "value": "réponse",
                    "state": "answered",
                },
            ]
        },
    )
    repeated_question = MissingQuestion(
        field="current_problem.detail",
        question="Détail ?",
        importance="high",
        reason="Changes selection.",
        required_to_choose=True,
    )
    decision = ImagingDecision(
        decision_status="insufficient_information",
        primary=ImagingRecommendation(),
        clinician_call_required=False,
        decision_ready_for_human_approval=False,
    )

    handoff = build_radiology_handoff(
        case,
        decision,
        [repeated_question],
        TeleradiologyRequest(status="draft"),
        {"matched_scenarios": []},
    )
    html = render_radiology_handoff_html(handoff)

    assert handoff.status == "draft"
    assert [item.field for item in handoff.clarifications] == ["current_problem.detail"]
    assert "current_problem.unknown_detail" not in {fact.field for fact in handoff.supporting_facts}
    assert "Oui" in html
    assert "[&quot;douleur&quot;, &quot;nausées&quot;]" in html
