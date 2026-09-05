"""Build the evidence-backed handoff presented to the teleradiologist."""

from __future__ import annotations

import json
from html import escape
from typing import Literal

from pydantic import BaseModel, Field

from ..core.models import (
    ClinicalCase,
    FieldStatus,
    ImagingDecision,
    ImagingRecommendation,
    MissingQuestion,
    SourceRef,
    TeleradiologyRequest,
)
from ..types import JsonObject, JsonValue
from .types import ReferenceContext

_CLINICAL_SECTIONS = (
    "patient",
    "current_problem",
    "history",
    "medications",
    "allergies",
    "labs",
    "imaging_safety",
)
_SAFETY_PREFIXES = ("allergies.", "imaging_safety.")
_SAFETY_FIELDS = {
    "labs.creatinine",
    "labs.egfr_ml_min_1_73m2",
    "labs.pregnancy_test",
    "medications.anticoagulation",
    "medications.metformin",
}
_HISTORY_SUMMARY_FIELDS = {
    "history.oncology",
    "history.surgery",
    "history.trauma",
    "history.relevant_conditions",
}
_MEDICATION_ALLERGY_SUMMARY_FIELDS = {
    "medications.anticoagulation",
    "medications.metformin",
    "allergies.iodinated_contrast_reaction",
    "allergies.gadolinium_reaction",
}
_LAB_SUMMARY_FIELDS = {
    "labs.egfr_ml_min_1_73m2",
    "labs.creatinine",
    "labs.pregnancy_test",
}
_FIELD_LABELS = {
    "patient.age": "Âge",
    "patient.sex": "Sexe",
    "current_problem.indication": "Indication clinique",
    "current_problem.symptoms": "Symptômes",
    "current_problem.onset": "Début des symptômes",
    "current_problem.location": "Localisation",
    "current_problem.laterality": "Côté concerné",
    "current_problem.severity": "Gravité clinique",
    "current_problem.red_flags": "Signes de gravité",
    "current_problem.suspected_diagnosis": "Diagnostic suspecté",
    "current_problem.known_diagnosis": "Diagnostic connu",
    "current_problem.pe_pretest_probability": (
        "Probabilité clinique pré-test d'embolie pulmonaire"
    ),
    "current_problem.hematuria": "Hématurie",
    "current_problem.pain_extent": "Étendue de la douleur",
    "current_problem.gcs": "Score de Glasgow",
    "current_problem.head_ct_rule_positive": "Critère clinique pour une TDM cérébrale",
    "current_problem.detail": "Précision clinique",
    "current_problem.required_fact": "Information clinique requise",
    "history.oncology": "Antécédent oncologique",
    "history.surgery": "Antécédents chirurgicaux",
    "history.trauma": "Contexte traumatique",
    "history.relevant_conditions": "Antécédents pertinents",
    "medications.anticoagulation": "Traitement anticoagulant",
    "medications.metformin": "Traitement par metformine",
    "allergies.iodinated_contrast_reaction": ("Réaction antérieure au produit de contraste iodé"),
    "allergies.gadolinium_reaction": "Réaction antérieure au gadolinium",
    "labs.egfr_ml_min_1_73m2": "DFG estimé (mL/min/1,73 m²)",
    "labs.creatinine": "Créatininémie",
    "labs.d_dimer": "D-dimères",
    "labs.pregnancy_test": "Test de grossesse",
    "imaging_safety.pregnancy": "Grossesse possible ou en cours",
    "imaging_safety.pacemaker": "Stimulateur cardiaque",
    "imaging_safety.implant_or_metal": "Implant ou matériel métallique",
    "imaging_safety.mri_compatibility": "Compatibilité avec l'IRM",
    "imaging_safety.claustrophobia": "Claustrophobie",
    "imaging_safety.custom_device": "Autre dispositif implanté",
}
_FIELD_SECTION_LABELS = {
    "patient": "Patient",
    "current_problem": "Problème actuel",
    "history": "Antécédents",
    "medications": "Traitements",
    "allergies": "Allergies",
    "labs": "Biologie",
    "imaging_safety": "Sécurité de l'imagerie",
}
_STATUS_LABELS = {
    FieldStatus.observed: "Documenté",
    FieldStatus.inferred: "Déduit — à vérifier",
    FieldStatus.unknown: "Non renseigné",
    FieldStatus.conflicting: "Données contradictoires",
}
_CANONICAL_VALUE_LABELS = {
    "right": "Droit",
    "left": "Gauche",
    "bilateral": "Bilatéral",
    "male": "Homme",
    "female": "Femme",
    "low": "Faible",
    "intermediate": "Intermédiaire",
    "high": "Élevée",
    "yes": "Oui",
    "no": "Non",
    "conditional": "Selon les conditions",
    "unknown": "Non renseigné",
    "emergent": "Immédiate",
    "urgent": "Urgente",
    "routine": "Programmée",
    "pulmonary_embolism": "Embolie pulmonaire",
}
_RESPONDER_LABELS = {
    "clinician": "Clinicien prescripteur",
    "emergency_clinician": "Médecin urgentiste",
}
_RESPONSE_METHOD_LABELS = {
    "answer_file": "Fichier de réponses",
    "interactive_browser": "Formulaire interactif",
}


class HandoffFact(BaseModel):
    field: str
    value: JsonValue
    status: FieldStatus
    confidence: float = Field(ge=0.0, le=1.0)
    validated: bool
    sources: list[SourceRef] = Field(default_factory=list)


class HandoffClarification(BaseModel):
    question_id: str | None = None
    field: str
    question: str
    clinical_reason: str | None = None
    state: Literal["answered", "unanswered"]
    answer: JsonValue = None
    responder_role: str | None = None
    answered_at: str | None = None
    response_method: str | None = None
    answer_source: str | None = None


class HandoffCitation(BaseModel):
    citation_id: str
    scenario_id: str
    organization: str | None = None
    title: str | None = None
    url: str | None = None
    locator: str | None = None
    relationship: Literal["scenario_background"] = "scenario_background"
    reference_status: str | None = None


class HandoffScenario(BaseModel):
    scenario_id: str
    title: str
    version: JsonValue = None
    validation_status: JsonValue = None
    match_score: float
    reference_candidate_ids: list[str] = Field(default_factory=list)
    triggered_rule_ids: list[str] = Field(default_factory=list)


class HandoffDecisionTrace(BaseModel):
    matched_scenarios: list[HandoffScenario] = Field(default_factory=list)
    selected_reference_candidate: str | None = None
    model_candidate_ids: list[str] = Field(default_factory=list)
    triggered_rules: list[JsonObject] = Field(default_factory=list)


class RadiologyHandoff(BaseModel):
    schema_version: int = 1
    status: Literal["ready_for_radiologist_review", "clinician_contact_required", "draft"]
    request: TeleradiologyRequest
    proposal: ImagingRecommendation
    supporting_facts: list[HandoffFact] = Field(default_factory=list)
    safety_facts: list[HandoffFact] = Field(default_factory=list)
    clarifications: list[HandoffClarification] = Field(default_factory=list)
    unresolved_questions: list[MissingQuestion] = Field(default_factory=list)
    decision_trace: HandoffDecisionTrace
    citations: list[HandoffCitation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    human_approval_required: bool = True
    run_manifest_filename: str = "run_manifest.json"


def _handoff_status(
    decision: ImagingDecision, request: TeleradiologyRequest
) -> Literal["ready_for_radiologist_review", "clinician_contact_required", "draft"]:
    if decision.clinician_call_required or request.status == "blocked":
        return "clinician_contact_required"
    if decision.decision_ready_for_human_approval and request.status == "ready_for_human_approval":
        return "ready_for_radiologist_review"
    return "draft"


def _known_facts(case: ClinicalCase) -> list[HandoffFact]:
    facts: list[HandoffFact] = []
    for section_name in _CLINICAL_SECTIONS:
        section = getattr(case, section_name)
        for key, clinical_field in section.items():
            if clinical_field.status == FieldStatus.unknown:
                continue
            facts.append(
                HandoffFact(
                    field=f"{section_name}.{key}",
                    value=clinical_field.value,
                    status=clinical_field.status,
                    confidence=clinical_field.confidence,
                    validated=clinical_field.validated,
                    sources=clinical_field.sources,
                )
            )
    return sorted(facts, key=lambda fact: fact.field)


def _is_safety_fact(fact: HandoffFact) -> bool:
    return fact.field.startswith(_SAFETY_PREFIXES) or fact.field in _SAFETY_FIELDS


def _text(record: JsonObject, key: str) -> str | None:
    value = record.get(key)
    return value if isinstance(value, str) else None


def _clarifications(
    case: ClinicalCase, questions: list[MissingQuestion]
) -> list[HandoffClarification]:
    entries: list[HandoffClarification] = []
    represented_fields: set[str] = set()
    records = case.metadata.get("clarifications", [])
    if isinstance(records, list):
        for raw in records:
            if not isinstance(raw, dict):
                continue
            record = raw
            field = record.get("field")
            if not isinstance(field, str):
                continue
            represented_fields.add(field)
            entries.append(
                HandoffClarification(
                    question_id=_text(record, "question_id"),
                    field=field,
                    question=_text(record, "question") or field,
                    clinical_reason=_text(record, "possible_decision_impact"),
                    state="answered" if record.get("state") == "answered" else "unanswered",
                    answer=record.get("value"),
                    responder_role=_text(record, "responder_role"),
                    answered_at=_text(record, "answered_at"),
                    response_method=_text(record, "response_method"),
                    answer_source=_text(record, "answer_source"),
                )
            )
    for question in questions:
        if question.field in represented_fields:
            continue
        entries.append(
            HandoffClarification(
                question_id=question.question_id,
                field=question.field,
                question=question.question,
                clinical_reason=question.clinical_reason,
                state="unanswered",
            )
        )
    return entries


def _scenario_trace(reference_context: ReferenceContext) -> HandoffDecisionTrace:
    scenarios: list[HandoffScenario] = []
    rules: list[JsonObject] = []
    for scenario in reference_context["matched_scenarios"]:
        rule_items = scenario["rules_triggered"]
        scenarios.append(
            HandoffScenario(
                scenario_id=scenario["id"],
                title=scenario["title"],
                version=scenario["version"],
                validation_status=scenario["status"],
                match_score=scenario["match_score"],
                reference_candidate_ids=[
                    str(candidate["id"]) for candidate in scenario["candidate_exams"]
                ],
                triggered_rule_ids=[rule["rule_id"] for rule in rule_items],
            )
        )
        rules.extend(
            {
                "scenario_id": scenario["id"],
                "rule_id": rule["rule_id"],
                "result": rule["result"],
                "relationship": "local_rule_triggered",
            }
            for rule in rule_items
        )
    return HandoffDecisionTrace(matched_scenarios=scenarios, triggered_rules=rules)


def _reference_candidate(
    decision: ImagingDecision, reference_context: ReferenceContext
) -> str | None:
    exam_name = decision.primary.exam_name
    if not exam_name:
        return None
    for scenario in reference_context["matched_scenarios"]:
        for candidate in scenario["candidate_exams"]:
            if candidate.get("exam_name") == exam_name:
                return f"{scenario['id']}:{candidate['id']}"
    return None


def _citations(reference_context: ReferenceContext) -> list[HandoffCitation]:
    citations: list[HandoffCitation] = []
    for scenario in reference_context["matched_scenarios"]:
        for index, raw_source in enumerate(scenario["sources"], start=1):
            source = raw_source if isinstance(raw_source, dict) else {}
            source_id = source.get("id")
            citations.append(
                HandoffCitation(
                    citation_id=(
                        source_id
                        if isinstance(source_id, str)
                        else f"{scenario['id']}:source:{index}"
                    ),
                    scenario_id=scenario["id"],
                    organization=_text(source, "organization"),
                    title=_text(source, "title"),
                    url=_text(source, "url"),
                    locator=_text(source, "locator"),
                    reference_status=(
                        str(scenario["status"]) if scenario["status"] is not None else None
                    ),
                )
            )
    return citations


def build_radiology_handoff(
    case: ClinicalCase,
    decision: ImagingDecision,
    questions: list[MissingQuestion],
    request: TeleradiologyRequest,
    reference_context: ReferenceContext,
) -> RadiologyHandoff:
    """Build an additive, review-oriented trace without claiming clinical approval."""

    facts = _known_facts(case)
    trace = _scenario_trace(reference_context)
    trace.selected_reference_candidate = _reference_candidate(decision, reference_context)
    trace.model_candidate_ids = [candidate.candidate_id for candidate in decision.candidates]
    return RadiologyHandoff(
        status=_handoff_status(decision, request),
        request=request,
        proposal=decision.primary,
        supporting_facts=facts,
        safety_facts=[fact for fact in facts if _is_safety_fact(fact)],
        clarifications=_clarifications(case, questions),
        unresolved_questions=questions,
        decision_trace=trace,
        citations=_citations(reference_context),
        warnings=[
            "Proposition d'aide à la décision : validation par un radiologue requise.",
            "Les références citées ont informé le référentiel local ; elles ne constituent pas une approbation de cette proposition particulière.",
            "Les réponses déclarées ne constituent ni une authentification ni une signature clinique.",
        ],
    )


def _display_value(value: JsonValue) -> str:
    if value is True:
        return "Oui"
    if value is False:
        return "Non"
    if value is None:
        return "Non renseigné"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _field_label(field: str) -> str:
    label = _FIELD_LABELS.get(field)
    if label:
        return label
    section, separator, _key = field.partition(".")
    if separator:
        section_label = _FIELD_SECTION_LABELS.get(section, "Information clinique")
        return f"{section_label} — autre information"
    return "Autre information clinique"


def _translated_canonical_value(value: JsonValue) -> str | None:
    if isinstance(value, str):
        return _CANONICAL_VALUE_LABELS.get(value.strip().casefold())
    if isinstance(value, list):
        translated = [_translated_canonical_value(item) for item in value]
        if all(item is not None for item in translated):
            return " ; ".join(item for item in translated if item is not None)
    return None


def _clinical_value(value: JsonValue) -> str:
    return _translated_canonical_value(value) or _display_value(value)


def _clinical_fact_value(fact: HandoffFact) -> str:
    translated = _translated_canonical_value(fact.value)
    if translated is not None:
        return translated
    if isinstance(fact.value, (int, float)) or fact.value is None:
        return _display_value(fact.value)
    excerpts = [source.excerpt for source in fact.sources if source.excerpt]
    if excerpts and not any(source.document_id.startswith("answers:") for source in fact.sources):
        return " ; ".join(excerpts)
    if isinstance(fact.value, list):
        return " ; ".join(_display_value(item) for item in fact.value)
    return _display_value(fact.value)


def _clinical_fact_status(fact: HandoffFact) -> str:
    if fact.status == FieldStatus.observed and any(
        source.document_id.startswith("answers:") for source in fact.sources
    ):
        return "Renseigné par le clinicien"
    return _STATUS_LABELS[fact.status]


def _fact_for_field(facts: list[HandoffFact], field: str) -> HandoffFact | None:
    return next((fact for fact in facts if fact.field == field), None)


def _clinical_summary_items(
    facts: list[HandoffFact], fields: set[str], *, omit_falsy: bool = False
) -> list[str]:
    return [
        f"{_field_label(fact.field)} : {_clinical_fact_value(fact)}"
        for fact in facts
        if fact.field in fields and (not omit_falsy or bool(fact.value))
    ]


def _clinical_patient_summary(handoff: RadiologyHandoff) -> str | None:
    age = _fact_for_field(handoff.supporting_facts, "patient.age")
    sex = _fact_for_field(handoff.supporting_facts, "patient.sex")
    parts: list[str] = []
    if age is not None:
        parts.append(f"{_clinical_fact_value(age)} ans")
    if sex is not None:
        parts.append(_clinical_fact_value(sex))
    return ", ".join(parts) or handoff.request.patient_summary


def _clinical_indication(handoff: RadiologyHandoff) -> str | None:
    indication = _fact_for_field(handoff.supporting_facts, "current_problem.indication")
    return _clinical_fact_value(indication) if indication else handoff.request.indication


def _clinical_source(source: SourceRef) -> str:
    if source.document_id.startswith("answers:"):
        return "Réponse du clinicien"
    page = f", p. {source.page}" if source.page is not None else ""
    return f"{source.filename}{page}"


def _exact_source(source: SourceRef) -> str:
    page = f", p. {source.page}" if source.page is not None else ""
    excerpt = f" — {source.excerpt}" if source.excerpt else ""
    return f"{source.filename}{page}{excerpt}"


def _items(values: list[str], empty: str = "Aucun élément") -> str:
    if not values:
        return f"<p class=muted>{escape(empty)}</p>"
    return "<ul>" + "".join(f"<li>{escape(value)}</li>" for value in values) + "</ul>"


def _clinical_fact_table(facts: list[HandoffFact]) -> str:
    if not facts:
        return "<p class=muted>Aucun fait structuré disponible.</p>"
    rows = []
    for fact in facts:
        sources = [_clinical_source(source) for source in fact.sources]
        rows.append(
            "<tr>"
            f"<td>{escape(_field_label(fact.field))}</td>"
            f"<td>{escape(_clinical_fact_value(fact))}</td>"
            f"<td>{escape(_clinical_fact_status(fact))}</td>"
            f"<td>{escape('; '.join(sources) or 'source non renseignée')}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Information clinique</th><th>Élément retenu</th>"
        "<th>Statut</th><th>Source</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _technical_fact_table(facts: list[HandoffFact]) -> str:
    if not facts:
        return "<p class=muted>Aucun fait structuré disponible.</p>"
    rows = []
    for fact in facts:
        sources = [_exact_source(source) for source in fact.sources]
        rows.append(
            "<tr>"
            f"<td><code>{escape(fact.field)}</code></td>"
            f"<td>{escape(_display_value(fact.value))}</td>"
            f"<td>{escape(fact.status.value)}</td>"
            f"<td>{fact.confidence:.2f}</td>"
            f"<td>{'true' if fact.validated else 'false'}</td>"
            f"<td>{escape('; '.join(sources) or 'source unavailable')}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Canonical field</th><th>Canonical value</th>"
        "<th>Internal status</th><th>Confidence</th><th>Validated</th>"
        "<th>Exact provenance</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _clarification_table(entries: list[HandoffClarification]) -> str:
    if not entries:
        return "<p class=muted>Aucune clarification demandée.</p>"
    rows = []
    for entry in entries:
        state = "Répondu" if entry.state == "answered" else "Non renseigné"
        response_method = _RESPONSE_METHOD_LABELS.get(
            entry.response_method or "", "Méthode non renseignée"
        )
        answer_source = (
            "Réponse interactive"
            if entry.answer_source and entry.answer_source.startswith("answers.interactive.")
            else "Fichier de réponses"
            if entry.answer_source
            else "Source non renseignée"
        )
        trace = " — ".join(
            value for value in [entry.answered_at, response_method, answer_source] if value
        )
        rows.append(
            "<tr>"
            f"<td>{escape(entry.question)}</td>"
            f"<td>{escape(entry.clinical_reason or 'Non renseigné')}</td>"
            f"<td>{escape(_clinical_value(entry.answer))}</td>"
            f"<td>{state}</td>"
            f"<td>{escape(_RESPONDER_LABELS.get(entry.responder_role or '', 'Non authentifié'))}</td>"
            f"<td>{escape(trace or 'non renseignée')}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Question</th><th>Impact possible</th><th>Réponse</th>"
        "<th>État</th><th>Répondant déclaré</th><th>Traçabilité</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _citation_list(citations: list[HandoffCitation]) -> str:
    if not citations:
        return "<p class=muted>Aucune référence documentaire associée.</p>"
    items = []
    for citation in citations:
        label = " — ".join(
            value for value in [citation.organization, citation.title, citation.locator] if value
        )
        url = f" — {citation.url}" if citation.url else ""
        items.append(
            f"<li>{escape(label or citation.citation_id)}{escape(url)}"
            "<br><small>Référence utilisée comme fondement du scénario local.</small></li>"
        )
    return "<ol>" + "".join(items) + "</ol>"


def _technical_scenario_list(trace: HandoffDecisionTrace) -> str:
    if not trace.matched_scenarios:
        return "<p class=muted>No matched scenario.</p>"
    scenarios = [
        f"{item.title} ({item.scenario_id}, version {item.version}, "
        f"status {item.validation_status})"
        for item in trace.matched_scenarios
    ]
    return _items(scenarios, empty="No matched scenario")


def render_radiology_handoff_html(handoff: RadiologyHandoff) -> str:
    """Render a self-contained, escaped French review page without remote assets."""

    status = {
        "ready_for_radiologist_review": "Proposition à valider par le radiologue",
        "clinician_contact_required": "Appel au téléradiologue requis",
        "draft": "Dossier en préparation",
    }[handoff.status]
    proposal = handoff.proposal
    request = handoff.request
    proposal_is_reviewable = (
        handoff.status == "ready_for_radiologist_review" and proposal.recommended
    )
    proposal_label = "Examen proposé" if proposal_is_reviewable else "Examen envisagé, non proposé"
    proposal_name = proposal.exam_name or request.requested_exam or "Aucun examen renseigné"
    contrast = _clinical_value(request.contrast or proposal.contrast)
    urgency = _clinical_value(request.urgency or proposal.urgency)
    history = (
        _clinical_summary_items(handoff.supporting_facts, _HISTORY_SUMMARY_FIELDS, omit_falsy=True)
        or request.relevant_history
    )
    medications_and_allergies = (
        _clinical_summary_items(handoff.supporting_facts, _MEDICATION_ALLERGY_SUMMARY_FIELDS)
        or request.medications_and_allergies
    )
    labs = _clinical_summary_items(handoff.supporting_facts, _LAB_SUMMARY_FIELDS) or (
        request.relevant_labs
    )
    prior_imaging = proposal.relevant_prior_imaging or request.relevant_prior_imaging
    safety_information = (
        proposal.safety_considerations
        or _clinical_summary_items(
            handoff.safety_facts, {fact.field for fact in handoff.safety_facts}
        )
        or request.safety_information
    )
    rationale_title = (
        "Justification de la proposition"
        if proposal_is_reviewable
        else "Éléments ayant conduit à l'abstention"
    )
    if not proposal_is_reviewable:
        proposal_notice = (
            '<p class="warning"><strong>Aucune proposition transmissible à ce stade.</strong> '
            "Un échange direct avec le téléradiologue est requis.</p>"
        )
    else:
        proposal_notice = (
            '<section class="proposal"><span>Examen proposé au radiologue</span>'
            f"<strong>{escape(proposal_name)}</strong></section>"
        )
    unresolved = [question.question for question in handoff.unresolved_questions]
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta name="referrer" content="no-referrer"><title>Dossier de revue radiologique</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;color:#173042;background:#f5f8fa;margin:0}}
main{{max-width:1050px;margin:32px auto;background:white;padding:36px;border-radius:14px}}
h1,h2,h3{{color:#075b66}}h2{{margin-top:32px;border-bottom:1px solid #d9e4e8;padding-bottom:6px}}
.status{{display:inline-block;padding:7px 12px;border-radius:999px;background:#fff1dc;color:#8a4b00}}
.proposal{{display:flex;flex-direction:column;gap:4px;margin:20px 0;padding:18px 22px;border-radius:12px;background:#e9f7f7;border-left:5px solid #087f8c}}
.proposal span{{color:#405b66}}.proposal strong{{font-size:1.35rem;color:#075b66}}
.warning{{border-left:4px solid #ef7d32;padding:10px 14px;background:#fff8f1}}
.muted,small{{color:#5c6f78}}table{{width:100%;border-collapse:collapse}}
th,td{{text-align:left;vertical-align:top;padding:8px;border-bottom:1px solid #d9e4e8}}
details{{margin-top:32px;border:1px solid #d9e4e8;border-radius:10px;padding:14px}}
summary{{color:#405b66;font-weight:700;cursor:pointer}}details h3{{margin-top:24px}}
code{{font-size:.88em;overflow-wrap:anywhere}}@media print{{body{{background:white}}main{{margin:0;padding:0}}}}
</style></head><body><main>
<h1>Dossier de revue radiologique</h1><p class="status">{escape(status)}</p>
{proposal_notice}
<h2>Demande clinique</h2>
<p><strong>Patient :</strong> {escape(_clinical_patient_summary(handoff) or "Non renseigné")}</p>
<p><strong>Indication :</strong> {escape(_clinical_indication(handoff) or "Non renseignée")}</p>
<p><strong>Question clinique :</strong> {escape(request.clinical_question or proposal.clinical_question_for_radiologist or "Non renseignée")}</p>
<p><strong>{proposal_label} :</strong> {escape(proposal_name)}</p>
<p><strong>Protocole :</strong> {escape(request.protocol_requested or proposal.protocol or "Non renseigné")} —
<strong>Contraste :</strong> {escape(contrast)} —
<strong>Urgence :</strong> {escape(urgency)}</p>
<h2>Synthèse clinique transmise</h2>
<h3>Antécédents pertinents</h3>{_items(history)}
<h3>Traitements et allergies</h3>{_items(medications_and_allergies)}
<h3>Biologie pertinente</h3>{_items(labs)}
<h3>Imagerie antérieure</h3>{_items(prior_imaging)}
<h3>Informations de sécurité</h3>{_items(safety_information)}
<h2>{escape(rationale_title)}</h2>{_items(request.rationale_for_exam or proposal.rationale)}
<h2>Alternatives considérées</h2>{_items(proposal.alternatives)}
<h2>Clarifications du clinicien</h2>{_clarification_table(handoff.clarifications)}
<h2>Informations cliniques retenues et sources</h2>{_clinical_fact_table(handoff.supporting_facts)}
<h2>Sécurité</h2>{_clinical_fact_table(handoff.safety_facts)}
<h2>Informations encore nécessaires</h2>{_items(unresolved)}
<h2>Références documentaires</h2>{_citation_list(handoff.citations)}
<h2>Avertissements</h2>{"".join(f'<p class="warning">{escape(item)}</p>' for item in handoff.warnings)}
<details><summary>Afficher la traçabilité technique</summary>
<p class="muted">Ces données canoniques sont destinées à l'audit technique.</p>
<h3>Structured clinical facts</h3>{_technical_fact_table(handoff.supporting_facts)}
<h3>Reference scenarios</h3>{_technical_scenario_list(handoff.decision_trace)}
</details>
</main></body></html>"""
