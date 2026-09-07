from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Any, TypeVar, cast

from openai import OpenAI
from pydantic import BaseModel

from ...errors import ConfigurationError
from ...fingerprints import sha256_text
from ...openai_compat import resolve_openai_inference_settings
from ...types import JsonObject, JsonValue
from ..models import (
    ClinicalCase,
    ClinicalField,
    FieldStatus,
    LLMExtraction,
    PriorImaging,
    SourceRef,
    TemporalStatus,
    TimelineEvent,
)
from ..reconciliation import reconcile_facts
from ..timeline import append_timeline_event

T = TypeVar("T", bound=BaseModel)

EXTRACTION_PROMPT = """
You are the Bulkinout Core clinical information extraction component.
Extract ONLY information present in supplied documents. Do not invent absent facts.

Critical rules:
- Source documents may be written in any language. Never assume French or any other language.
- Missing information stays unknown.
- Absence of mention is NOT a negative finding.
- Distinguish observed vs inferred.
- Provide provenance for every non-unknown fact.
- Preserve dates and units.
- Emit separate fact entries when sources give different values or temporal states for the same
  field. Do not reconcile them or select one as true.
- Set temporal_status to current only when the source supports that the fact applies to the current
  encounter; use historical for past facts, resolved only when resolution is explicit, and unknown
  when the temporal relationship is unclear.
- Set observed_at to an ISO 8601 date or datetime only when the source supports one. Never infer a
  date from document order or file metadata.
- Detect contradictions, including materially different current values.
- Preserve explicit negation: encode a negative finding only when a source states it, and retain
  its exact evidence excerpt. Never turn absence of mention into false or no.
- Keep numeric values and their units together when the canonical field does not define a unit;
  do not convert units unless the source gives the converted value.
- Extract information useful across the radiology workflow, not only pre-exam referral.
- Never infer device MRI compatibility.
- Never convert missing renal function into normal renal function.
- Use canonical English identifiers and language-independent canonical values.
- Preserve source wording in provenance excerpts; do not translate quoted evidence.
- Write developer-facing contradictions and document notes in English.

Use canonical fields when applicable:
patient.age
patient.sex
current_problem.indication
current_problem.symptoms
current_problem.onset
current_problem.location
current_problem.laterality
current_problem.severity
current_problem.red_flags
current_problem.suspected_diagnosis
current_problem.known_diagnosis
history.oncology
history.surgery
history.trauma
history.relevant_conditions
medications.anticoagulation
medications.metformin
allergies.iodinated_contrast_reaction
allergies.gadolinium_reaction
labs.egfr_ml_min_1_73m2
labs.creatinine
labs.pregnancy_test
imaging_safety.pregnancy
imaging_safety.pacemaker
imaging_safety.implant_or_metal
imaging_safety.mri_compatibility
imaging_safety.claustrophobia
"""


def _extract_json(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text:
        return output_text
    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for c in getattr(item, "content", []) or []:
            text = getattr(c, "text", None)
            if isinstance(text, str):
                chunks.append(text)
    return "".join(chunks)


class OpenAICoreExtractor:
    provider = "openai"
    name = "bulkinout_core_openai_multimodal_v1"
    prompt_sha256 = sha256_text(EXTRACTION_PROMPT)

    def __init__(self, model: str | None = None, *, cold: bool = False):
        self.model = (
            model or os.getenv("BULKINOUT_EXTRACTION_MODEL") or os.getenv("BULKINOUT_MODEL")
        )
        if not self.model:
            raise ConfigurationError(
                "No extraction model configured. Use --extraction-model, "
                "BULKINOUT_EXTRACTION_MODEL, --model, or BULKINOUT_MODEL."
            )
        if not os.getenv("OPENAI_API_KEY"):
            raise ConfigurationError("OPENAI_API_KEY is missing.")
        settings = resolve_openai_inference_settings(
            self.model,
            cold=cold,
            component="Core",
        )
        self._request_parameters = settings.request_parameters()
        self.inference_parameters = settings.manifest_parameters()
        self.client = OpenAI()

    def _call_structured(self, prompt: str, content: list[JsonObject], model_cls: type[T]) -> T:
        responses = cast(Any, self.client.responses)
        request_parameters: dict[str, object] = {
            "model": self.model,
            "input": [
                {"role": "developer", "content": [{"type": "input_text", "text": prompt}]},
                {"role": "user", "content": content},
            ],
            "text_format": model_cls,
            **self._request_parameters,
        }
        response = responses.parse(**request_parameters)
        parsed = getattr(response, "output_parsed", None)
        if parsed is not None:
            return model_cls.model_validate(parsed)
        return model_cls.model_validate_json(_extract_json(response))

    def _upload_or_inline(self, path: Path) -> JsonObject:
        suffix = path.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            return {
                "type": "input_image",
                "image_url": f"data:{mime};base64,{data}",
                "detail": "high",
            }
        uploaded = self.client.files.create(file=path.open("rb"), purpose="user_data")
        return {"type": "input_file", "file_id": uploaded.id}

    def extract(self, paths: list[Path]) -> LLMExtraction:
        content: list[JsonObject] = [
            {
                "type": "input_text",
                "text": "Extract clinical observations across all supplied documents.",
            }
        ]
        for path in paths:
            if path.suffix.lower() in {".txt", ".md"}:
                text = path.read_text(encoding="utf-8", errors="replace")
                content.append({"type": "input_text", "text": f"--- FILE: {path.name} ---\n{text}"})
            else:
                content.append({"type": "input_text", "text": f"Next file: {path.name}"})
                content.append(self._upload_or_inline(path))
        return self._call_structured(EXTRACTION_PROMPT, content, LLMExtraction)


def extraction_to_case(extraction: LLMExtraction) -> ClinicalCase:
    case = reconcile_facts(extraction.facts)

    def clinical_field(value: JsonValue, source_document: str | None) -> ClinicalField:
        if value in (None, "", []):
            return ClinicalField()
        sources = (
            [
                SourceRef(
                    document_id=f"llm:{source_document}",
                    filename=source_document,
                )
            ]
            if source_document
            else []
        )
        return ClinicalField(
            value=value,
            status=FieldStatus.observed,
            sources=sources,
            confidence=0.75,
            temporal_status=TemporalStatus.historical,
        )

    for prior in extraction.prior_imaging:
        source_refs = (
            [
                SourceRef(
                    document_id=f"llm:{prior.source_document}",
                    filename=prior.source_document,
                )
            ]
            if prior.source_document
            else []
        )
        case.prior_imaging.append(
            PriorImaging(
                modality=clinical_field(prior.modality, prior.source_document),
                region=clinical_field(prior.region, prior.source_document),
                date=clinical_field(prior.date, prior.source_document).model_copy(
                    update={"observed_at": prior.date}
                ),
                result=clinical_field(prior.result, prior.source_document),
                source_document=prior.source_document,
            )
        )
        prior_value = {
            key: value
            for key, value in {
                "modality": prior.modality,
                "region": prior.region,
                "result": prior.result,
            }.items()
            if value is not None
        }
        if prior_value:
            append_timeline_event(
                case,
                TimelineEvent(
                    field="prior_imaging",
                    value=cast(JsonObject, prior_value),
                    status=FieldStatus.observed,
                    temporal_status=TemporalStatus.historical,
                    observed_at=prior.date,
                    sources=source_refs,
                    confidence=0.75,
                ),
            )

    reconciliation = case.metadata.get("reconciliation", {})
    conflict_value = reconciliation.get("conflicts", []) if isinstance(reconciliation, dict) else []
    deterministic_conflicts = conflict_value if isinstance(conflict_value, list) else []
    case.metadata["contradictions"] = cast(
        list[JsonValue], [*extraction.contradictions, *deterministic_conflicts]
    )
    case.metadata["document_notes"] = cast(list[JsonValue], extraction.document_notes)
    return case
