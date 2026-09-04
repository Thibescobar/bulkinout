from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class FieldStatus(str, Enum):
    observed = "observed"
    inferred = "inferred"
    unknown = "unknown"
    conflicting = "conflicting"


class SourceRef(BaseModel):
    document_id: str
    filename: str
    page: int | None = None
    excerpt: str | None = None


class ClinicalField(BaseModel):
    value: Any = None
    status: FieldStatus = FieldStatus.unknown
    sources: list[SourceRef] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    validated: bool = False


class PriorImaging(BaseModel):
    modality: ClinicalField = Field(default_factory=ClinicalField)
    region: ClinicalField = Field(default_factory=ClinicalField)
    date: ClinicalField = Field(default_factory=ClinicalField)
    result: ClinicalField = Field(default_factory=ClinicalField)
    source_document: str | None = None


class ClinicalCase(BaseModel):
    patient: dict[str, ClinicalField] = Field(default_factory=dict)
    current_problem: dict[str, ClinicalField] = Field(default_factory=dict)
    history: dict[str, ClinicalField] = Field(default_factory=dict)
    medications: dict[str, ClinicalField] = Field(default_factory=dict)
    allergies: dict[str, ClinicalField] = Field(default_factory=dict)
    labs: dict[str, ClinicalField] = Field(default_factory=dict)
    imaging_safety: dict[str, ClinicalField] = Field(default_factory=dict)
    prior_imaging: list[PriorImaging] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactRef(BaseModel):
    artifact_id: str
    artifact_type: str
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowState(BaseModel):
    phase: Literal["pre_exam", "acquisition", "post_exam", "finalized"] = "pre_exam"
    status: str = "active"


class RadiologyCase(BaseModel):
    """
    Longitudinal container shared by all BULKINOUT radiology workflows.
    Pre-exam Request is implemented now; post-exam Report is reserved for later.
    """
    case_id: str | None = None
    workflow: WorkflowState = Field(default_factory=WorkflowState)
    clinical: ClinicalCase = Field(default_factory=ClinicalCase)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    referral: dict[str, Any] = Field(default_factory=dict)
    acquisition: dict[str, Any] = Field(default_factory=dict)
    ai_results: list[dict[str, Any]] = Field(default_factory=list)
    radiologist_observations: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    impression: dict[str, Any] = Field(default_factory=dict)
    final_report: dict[str, Any] = Field(default_factory=dict)
    audit: list[dict[str, Any]] = Field(default_factory=list)


class MissingQuestion(BaseModel):
    field: str
    question: str
    importance: Literal["critical", "high", "medium", "low"]
    reason: str
    blocking: bool = False
    answerable_from_existing_docs: bool = False


class CandidateExam(BaseModel):
    candidate_id: str
    exam_name: str
    modality: str
    body_region: str
    contrast: Literal["yes", "no", "conditional", "unknown"] = "unknown"
    protocol: str | None = None
    fit_score: float = Field(ge=0.0, le=1.0)
    arguments_for: list[str] = Field(default_factory=list)
    arguments_against: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class DiscriminatingQuestion(BaseModel):
    question_id: str
    field: str
    question: str
    why_it_matters: str
    priority: int = Field(ge=1)
    candidate_ids_affected: list[str] = Field(default_factory=list)
    possible_decision_impact: str
    required_to_choose: bool = True


class ImagingRecommendation(BaseModel):
    recommended: bool = True
    modality: str | None = None
    body_region: str | None = None
    exam_name: str | None = None
    protocol: str | None = None
    contrast: Literal["yes", "no", "conditional", "unknown"] = "unknown"
    contrast_phase_or_sequence: str | None = None
    urgency: Literal["emergent", "urgent", "routine", "unknown"] = "unknown"
    clinical_question_for_radiologist: str | None = None
    rationale: list[str] = Field(default_factory=list)
    expected_diagnostic_value: str | None = None
    alternatives: list[str] = Field(default_factory=list)
    relevant_prior_imaging: list[str] = Field(default_factory=list)
    safety_considerations: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ImagingDecision(BaseModel):
    decision_status: Literal[
        "selected",
        "insufficient_information",
        "no_imaging_recommended",
        "safety_blocked"
    ] = "insufficient_information"
    candidates: list[CandidateExam] = Field(default_factory=list)
    discriminating_questions: list[DiscriminatingQuestion] = Field(default_factory=list)
    primary: ImagingRecommendation
    secondary: list[ImagingRecommendation] = Field(default_factory=list)
    no_imaging_reason: str | None = None
    clinician_call_required: bool = True
    clinician_call_reasons: list[str] = Field(default_factory=list)
    decision_ready_for_human_approval: bool = False
    validation_warning: str = (
        "Aide à la décision. Une validation clinique humaine est requise avant prescription/transmission."
    )


class TeleradiologyRequest(BaseModel):
    status: Literal["draft", "ready_for_human_approval", "blocked"] = "draft"
    patient_summary: str | None = None
    indication: str | None = None
    requested_exam: str | None = None
    protocol_requested: str | None = None
    contrast: str | None = None
    urgency: str | None = None
    clinical_question: str | None = None
    relevant_history: list[str] = Field(default_factory=list)
    medications_and_allergies: list[str] = Field(default_factory=list)
    relevant_labs: list[str] = Field(default_factory=list)
    relevant_prior_imaging: list[str] = Field(default_factory=list)
    safety_information: list[str] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    rationale_for_exam: list[str] = Field(default_factory=list)
    validated_by_clinician: bool = False
    warning: str = "Brouillon généré automatiquement. Ne pas transmettre sans validation clinique."


class LLMSource(BaseModel):
    filename: str
    page: int | None = None
    excerpt: str | None = None


class LLMFact(BaseModel):
    field: str
    value: Any
    status: Literal["observed", "inferred", "unknown", "conflicting"]
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[LLMSource] = Field(default_factory=list)


class LLMExtraction(BaseModel):
    facts: list[LLMFact] = Field(default_factory=list)
    prior_imaging: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    document_notes: list[str] = Field(default_factory=list)


class AnswerItem(BaseModel):
    question_id: str | None = None
    field: str
    value: Any
    note: str | None = None


class AnswerFile(BaseModel):
    answers: list[AnswerItem] = Field(default_factory=list)
