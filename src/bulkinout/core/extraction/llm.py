from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from ..models import (
    ClinicalCase,
    ClinicalField,
    FieldStatus,
    LLMExtraction,
    PriorImaging,
    SourceRef,
)

T = TypeVar("T", bound=BaseModel)

EXTRACTION_PROMPT = """
You are the BULKINOUT Core clinical information extraction component.
Extract ONLY information present in supplied documents. Do not invent absent facts.

Critical rules:
- Source documents may be written in any language. Never assume French or any other language.
- Missing information stays unknown.
- Absence of mention is NOT a negative finding.
- Distinguish observed vs inferred.
- Provide provenance for every non-unknown fact.
- Preserve dates and units.
- Detect contradictions.
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

def _schema_format(model: type[T]) -> dict:
    return {
        "type": "json_schema",
        "name": model.__name__,
        "strict": True,
        "schema": model.model_json_schema(),
    }

def _extract_json(response) -> str:
    if getattr(response, "output_text", None):
        return response.output_text
    chunks = []
    for item in getattr(response, "output", []) or []:
        for c in getattr(item, "content", []) or []:
            if getattr(c, "text", None):
                chunks.append(c.text)
    return "".join(chunks)

class OpenAICoreExtractor:
    def __init__(self, model: str | None = None):
        self.client = OpenAI()
        self.model = model or os.getenv("BULKINOUT_MODEL")
        if not self.model:
            raise ValueError("No model configured. Use --model or BULKINOUT_MODEL.")

    def _call_structured(self, prompt: str, content: list[dict], model_cls: type[T]) -> T:
        response = self.client.responses.create(
            model=self.model,
            reasoning={"effort": "medium"},
            input=[
                {"role": "developer", "content": [{"type": "input_text", "text": prompt}]},
                {"role": "user", "content": content},
            ],
            text={"format": _schema_format(model_cls)},
        )
        return model_cls.model_validate_json(_extract_json(response))

    def _upload_or_inline(self, path: Path) -> dict:
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
        content = [{
            "type": "input_text",
            "text": "Extract and reconcile clinical facts across all supplied documents."
        }]
        for path in paths:
            if path.suffix.lower() in {".txt", ".md"}:
                text = path.read_text(encoding="utf-8", errors="replace")
                content.append({"type": "input_text", "text": f"--- FILE: {path.name} ---\n{text}"})
            else:
                content.append({"type": "input_text", "text": f"Next file: {path.name}"})
                content.append(self._upload_or_inline(path))
        return self._call_structured(EXTRACTION_PROMPT, content, LLMExtraction)

def extraction_to_case(extraction: LLMExtraction) -> ClinicalCase:
    case = ClinicalCase()
    sections = {
        "patient": case.patient,
        "current_problem": case.current_problem,
        "history": case.history,
        "medications": case.medications,
        "allergies": case.allergies,
        "labs": case.labs,
        "imaging_safety": case.imaging_safety,
    }

    for fact in extraction.facts:
        if "." not in fact.field:
            continue
        section_name, key = fact.field.split(".", 1)
        section = sections.get(section_name)
        if section is None:
            continue
        refs = [
            SourceRef(
                document_id=f"llm:{s.filename}",
                filename=s.filename,
                page=s.page,
                excerpt=s.excerpt,
            )
            for s in fact.sources
        ]
        section[key] = ClinicalField(
            value=fact.value,
            status=FieldStatus(fact.status),
            sources=refs,
            confidence=fact.confidence,
            validated=False,
        )

    for pi in extraction.prior_imaging:
        def cf(v):
            if v in (None, "", []):
                return ClinicalField()
            return ClinicalField(value=v, status=FieldStatus.observed, confidence=0.75)
        case.prior_imaging.append(PriorImaging(
            modality=cf(pi.get("modality")),
            region=cf(pi.get("region")),
            date=cf(pi.get("date")),
            result=cf(pi.get("result") or pi.get("summary")),
            source_document=pi.get("source_document") or pi.get("filename"),
        ))

    case.metadata["extractor"] = "bulkinout_core_openai_multimodal_v1"
    case.metadata["contradictions"] = extraction.contradictions
    case.metadata["document_notes"] = extraction.document_notes
    return case
