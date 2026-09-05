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


def _items(values: list[str], empty: str = "Aucun élément") -> str:
    if not values:
        return f"<p class=muted>{escape(empty)}</p>"
    return "<ul>" + "".join(f"<li>{escape(value)}</li>" for value in values) + "</ul>"


def _fact_table(facts: list[HandoffFact]) -> str:
    if not facts:
        return "<p class=muted>Aucun fait structuré disponible.</p>"
    rows = []
    for fact in facts:
        sources = []
        for source in fact.sources:
            page = f", p. {source.page}" if source.page is not None else ""
            excerpt = f" — {source.excerpt}" if source.excerpt else ""
            sources.append(f"{source.filename}{page}{excerpt}")
        rows.append(
            "<tr>"
            f"<td><code>{escape(fact.field)}</code></td>"
            f"<td>{escape(_display_value(fact.value))}</td>"
            f"<td>{escape(fact.status.value)}</td>"
            f"<td>{escape('; '.join(sources) or 'source non renseignée')}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Information</th><th>Valeur</th><th>État</th>"
        "<th>Provenance</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def _clarification_table(entries: list[HandoffClarification]) -> str:
    if not entries:
        return "<p class=muted>Aucune clarification demandée.</p>"
    rows = []
    for entry in entries:
        state = "Répondu" if entry.state == "answered" else "Non renseigné"
        trace = " — ".join(
            value
            for value in [entry.answered_at, entry.response_method, entry.answer_source]
            if value
        )
        rows.append(
            "<tr>"
            f"<td>{escape(entry.question)}</td>"
            f"<td>{escape(entry.clinical_reason or 'Non renseigné')}</td>"
            f"<td>{escape(_display_value(entry.answer))}</td>"
            f"<td>{state}</td>"
            f"<td>{escape(entry.responder_role or 'non authentifié')}</td>"
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
            f"<br><small>Scénario {escape(citation.scenario_id)} ; "
            f"statut {escape(citation.reference_status or 'non renseigné')}</small></li>"
        )
    return "<ol>" + "".join(items) + "</ol>"


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
        proposal_notice = ""
    unresolved = [question.question for question in handoff.unresolved_questions]
    scenarios = [
        f"{item.title} ({item.scenario_id}, version {item.version}, statut {item.validation_status})"
        for item in handoff.decision_trace.matched_scenarios
    ]
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta name="referrer" content="no-referrer"><title>Dossier de revue radiologique</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;color:#173042;background:#f5f8fa;margin:0}}
main{{max-width:1050px;margin:32px auto;background:white;padding:36px;border-radius:14px}}
h1,h2,h3{{color:#075b66}}h2{{margin-top:32px;border-bottom:1px solid #d9e4e8;padding-bottom:6px}}
.status{{display:inline-block;padding:7px 12px;border-radius:999px;background:#fff1dc;color:#8a4b00}}
.warning{{border-left:4px solid #ef7d32;padding:10px 14px;background:#fff8f1}}
.muted,small{{color:#5c6f78}}table{{width:100%;border-collapse:collapse}}
th,td{{text-align:left;vertical-align:top;padding:8px;border-bottom:1px solid #d9e4e8}}
code{{font-size:.88em;overflow-wrap:anywhere}}@media print{{body{{background:white}}main{{margin:0;padding:0}}}}
</style></head><body><main>
<h1>Dossier de revue radiologique</h1><p class="status">{escape(status)}</p>
{proposal_notice}
<h2>Demande clinique</h2>
<p><strong>Patient :</strong> {escape(request.patient_summary or "Non renseigné")}</p>
<p><strong>Indication :</strong> {escape(request.indication or "Non renseignée")}</p>
<p><strong>Question clinique :</strong> {escape(request.clinical_question or proposal.clinical_question_for_radiologist or "Non renseignée")}</p>
<p><strong>{proposal_label} :</strong> {escape(proposal_name)}</p>
<p><strong>Protocole :</strong> {escape(request.protocol_requested or proposal.protocol or "Non renseigné")} —
<strong>Contraste :</strong> {escape(request.contrast or proposal.contrast)} —
<strong>Urgence :</strong> {escape(request.urgency or proposal.urgency)}</p>
<h2>Synthèse clinique transmise</h2>
<h3>Antécédents pertinents</h3>{_items(request.relevant_history)}
<h3>Traitements et allergies</h3>{_items(request.medications_and_allergies)}
<h3>Biologie pertinente</h3>{_items(request.relevant_labs)}
<h3>Imagerie antérieure</h3>{_items(request.relevant_prior_imaging)}
<h3>Informations de sécurité</h3>{_items(request.safety_information)}
<h2>{escape(rationale_title)}</h2>{_items(request.rationale_for_exam or proposal.rationale)}
<h2>Alternatives considérées</h2>{_items(proposal.alternatives)}
<h2>Clarifications du clinicien</h2>{_clarification_table(handoff.clarifications)}
<h2>Informations cliniques et provenance</h2>{_fact_table(handoff.supporting_facts)}
<h2>Sécurité</h2>{_fact_table(handoff.safety_facts)}
<h2>Informations encore nécessaires</h2>{_items(unresolved)}
<h2>Scénarios du référentiel</h2>{_items(scenarios)}
<h2>Références documentaires</h2>{_citation_list(handoff.citations)}
<h2>Avertissements</h2>{"".join(f'<p class="warning">{escape(item)}</p>' for item in handoff.warnings)}
</main></body></html>"""
