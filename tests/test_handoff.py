from datetime import UTC, datetime

from bulkinout.core.models import (
    AnswerFile,
    AnswerItem,
    CandidateExam,
    CodedConcept,
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


def observed(value, filename="note.md", excerpt=None):
    return ClinicalField(
        value=value,
        status=FieldStatus.observed,
        confidence=0.95,
        sources=[
            SourceRef(
                document_id=f"input:{filename}",
                filename=filename,
                excerpt=excerpt,
            )
        ],
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
    case.current_problem["indication"].coded_concepts.append(
        CodedConcept(
            system="urn:bulkinout:test",
            code="rlq-pain",
            display="Right lower quadrant pain",
            original_text="Douleur de fosse iliaque droite",
        )
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
            alternatives=["Le recours à l’échographie dépend de l’expertise disponible."],
        ),
        secondary=[
            ImagingRecommendation(
                exam_name="Échographie abdomino-pelvienne",
                modality="US",
                body_region="abdomen and pelvis",
                protocol="Étude ciblée de la fosse iliaque droite",
                contrast="no",
                urgency="urgent",
                rationale=["Alternative sans irradiation selon le contexte clinique."],
                safety_considerations=["Dépend de l’expertise et de la fenêtre acoustique."],
            )
        ],
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
    assert handoff.schema_version == 2
    assert handoff.alternative_proposals == decision.secondary
    assert "seule la proposition privilégiée" in handoff.warnings[-1]
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
    assert handoff.supporting_facts[0].coded_concepts[0].code == "rlq-pain"
    assert handoff.clarifications[0].responder_role == "emergency_clinician"
    assert handoff.decision_trace.selected_reference_candidate == "rlq_appendicitis:ct_iv"
    assert handoff.decision_trace.triggered_rules[0]["relationship"] == ("local_rule_triggered")
    assert handoff.citations[0].organization == "ACR"
    assert handoff.citations[0].relationship == "scenario_background"

    html = render_radiology_handoff_html(handoff)
    assert "Proposition à valider par le radiologue" in html
    assert "Demande clinique" in html
    assert "Appendicite\u202f?" in html
    assert "Examen proposé" in html
    assert "Choix à présenter au radiologue" in html
    assert "Proposition privilégiée par Bulkinout" in html
    assert "Alternative 1" in html
    assert "Échographie abdomino-pelvienne" in html
    assert "Étude ciblée de la fosse iliaque droite" in html
    assert "Alternative sans irradiation selon le contexte clinique." in html
    assert "Dépend de l’expertise et de la fenêtre acoustique." in html
    assert html.count("Argumentaire généré par Bulkinout — à vérifier") == 2
    assert "Justification de la proposition" not in html
    assert "Présélection visuelle uniquement" in html
    assert html.count('name="exam-choice"') == 2
    assert html.count(" checked>") == 1
    assert ".exam-option input:checked + .exam-card" in html
    assert "Notes sur les alternatives" in html
    assert "Le recours à l’échographie dépend de l’expertise disponible." in html
    assert "Synthèse clinique transmise" in html
    assert "Douleur aiguë depuis six heures." in html
    assert "DFG estimé (mL/min/1,73 m²)\u202f: 92" in html
    assert "Modifie la stratégie d&#x27;imagerie." in html
    assert "2026-09-04T10:30:00Z" in html
    assert "Médecin urgentiste" in html
    assert "Formulaire interactif" in html
    assert "Réponse interactive" in html
    assert "Informations cliniques retenues et sources" in html
    assert "Indication clinique" in html
    assert "Grossesse possible ou en cours" in html
    assert "Renseigné par le clinicien" in html
    assert "Afficher la traçabilité technique" in html
    assert "urn:bulkinout:test | rlq-pain | Right lower quadrant pain" in html
    assert "Canonical field" in html
    assert "note.md" in html
    assert "Aucune proposition transmissible" not in html
    assert "Right Lower Quadrant Pain" in html
    assert "answers.interactive.1.json" in html
    assert "https://example.test/acr" in html
    assert "Ajouter au bon de demande" in html
    assert 'button type="button" disabled' in html


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
    assert "Ajouter au bon de demande" not in html
    assert 'name="exam-choice"' not in html


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


def test_radiologist_selection_handoff_presents_unselected_options():
    decision = ImagingDecision(
        decision_status="radiologist_selection_required",
        primary=ImagingRecommendation(
            recommended=False,
            exam_name="Angioscanner pulmonaire",
            modality="CT",
            contrast="yes",
        ),
        secondary=[
            ImagingRecommendation(
                recommended=False,
                exam_name="Scintigraphie V/Q",
                modality="NM",
                contrast="no",
            )
        ],
        clinician_call_required=False,
        decision_ready_for_human_approval=True,
    )
    request = TeleradiologyRequest(status="ready_for_human_approval")

    handoff = build_radiology_handoff(
        ClinicalCase(), decision, [], request, {"matched_scenarios": []}
    )
    html = render_radiology_handoff_html(handoff)

    assert handoff.status == "ready_for_radiologist_review"
    assert handoff.radiologist_selection_required is True
    assert "Choix de l’examen par le radiologue requis" in html
    assert "Option 1" in html
    assert "Option 2" in html
    assert 'name="exam-choice"' in html
    assert 'value="primary" checked' not in html
    assert 'value="secondary-1" checked' not in html
    assert "Voir les options présentées ci-dessus" in html
    assert "Appel au téléradiologue requis" not in html


def test_clinical_view_hides_canonical_terms_but_keeps_them_in_technical_trace():
    case = ClinicalCase(
        patient={"age": observed(58), "sex": observed("male")},
        history={
            "relevant_conditions": observed(
                ["hypertension", "dyslipidemia"],
                excerpt="Hypertension artérielle et dyslipidémie.",
            )
        },
        medications={
            "anticoagulation": observed(
                "No usual anticoagulant known.",
                excerpt="Aucun traitement anticoagulant habituel connu.",
            )
        },
        allergies={
            "iodinated_contrast_reaction": ClinicalField(
                value="Diffuse urticaria after iodinated contrast injection",
                status=FieldStatus.observed,
                confidence=0.93,
                sources=[
                    SourceRef(
                        document_id="llm:prior_report.pdf",
                        filename="prior_report.pdf",
                        page=1,
                        excerpt="Urticaire diffus après injection de produit iodé.",
                    )
                ],
            )
        },
        labs={"egfr_ml_min_1_73m2": observed(51)},
        current_problem={
            "indication": observed(
                "Suspected pulmonary embolism",
                excerpt="Suspicion clinique d'embolie pulmonaire.",
            ),
            "laterality": observed("right"),
        },
    )
    decision = ImagingDecision(
        decision_status="insufficient_information",
        primary=ImagingRecommendation(
            contrast="no",
            urgency="urgent",
            relevant_prior_imaging=[
                "Radiographie thoracique du 04/09/2026 : pas d'anomalie aiguë."
            ],
            safety_considerations=["Aucun produit de contraste requis."],
        ),
        clinician_call_required=False,
    )
    request = TeleradiologyRequest(
        status="draft",
        patient_summary="58 ans, male",
        indication="Suspected pulmonary embolism",
        contrast="no",
        urgency="urgent",
        relevant_history=["ATCD pertinents: ['hypertension', 'dyslipidemia']"],
        medications_and_allergies=["Anticoagulation: No usual anticoagulant known."],
        relevant_prior_imaging=[
            "modalité=chest radiograph; région=chest; résultat=No acute abnormality"
        ],
    )
    handoff = build_radiology_handoff(
        case,
        decision,
        [],
        request,
        {"matched_scenarios": []},
    )
    handoff_before_render = handoff.model_dump(mode="json")

    html = render_radiology_handoff_html(handoff)
    clinical_view, technical_trace = html.split("<details>", maxsplit=1)

    assert handoff.model_dump(mode="json") == handoff_before_render
    assert "58 ans, Homme" in clinical_view
    assert "Suspicion clinique d&#x27;embolie pulmonaire." in clinical_view
    assert "Hypertension artérielle et dyslipidémie." in clinical_view
    assert "Aucun traitement anticoagulant habituel connu." in clinical_view
    assert "DFG estimé (mL/min/1,73 m²)\u202f: 51" in clinical_view
    assert (
        "Radiographie thoracique du 04/09/2026\u202f: pas d&#x27;anomalie aiguë." in clinical_view
    )
    assert "Aucun produit de contraste requis." in clinical_view
    assert "Réaction antérieure au produit de contraste iodé" in clinical_view
    assert "Urticaire diffus après injection de produit iodé." in clinical_view
    assert "Côté concerné" in clinical_view
    assert ">Droit<" in clinical_view
    assert "<strong>Contraste\u202f:</strong> Non" in clinical_view
    assert "<strong>Urgence\u202f:</strong> Urgente" in clinical_view
    assert "ATCD pertinents: [" not in clinical_view
    assert "No usual anticoagulant known." not in clinical_view
    assert "modalité=chest radiograph" not in clinical_view
    assert "allergies.iodinated_contrast_reaction" not in clinical_view
    assert "Diffuse urticaria after iodinated contrast injection" not in clinical_view
    assert ">observed<" not in clinical_view
    assert "allergies.iodinated_contrast_reaction" in technical_trace
    assert "Diffuse urticaria after iodinated contrast injection" in technical_trace
    assert ">observed<" in technical_trace


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
    assert "douleur\u202f; nausées" in html
