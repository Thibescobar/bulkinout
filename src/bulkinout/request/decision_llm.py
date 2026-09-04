from __future__ import annotations

import json
import os
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from ..core.models import ClinicalCase, ImagingDecision

T = TypeVar("T", bound=BaseModel)

DECISION_PROMPT = """
You are BULKINOUT Request, a radiology clinical decision-support component.
Given a structured clinical case, unresolved questions and a reference context,
reason across plausible imaging candidates.

This is decision support, not autonomous prescribing.

Process:
1. Use reference_context as the normative local decision-support context when supplied.
2. Generate/compare plausible candidates.
3. Identify missing facts that can materially change exam, protocol, contrast, urgency or safety.
4. Convert only material unknowns into discriminating questions.
5. Ask the minimum number of questions needed.
6. If a required discriminating question is unanswered, decision_status must be
   insufficient_information or safety_blocked, primary.recommended=false,
   clinician_call_required=true, decision_ready_for_human_approval=false.
7. Select one primary exam only when justified.
8. If imaging is not warranted, use no_imaging_recommended.

Do not fabricate contraindications, lab values, allergies, pregnancy status or device compatibility.
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

class OpenAIRequestDecision:
    def __init__(self, model: str | None = None):
        self.client = OpenAI()
        self.model = model or os.getenv("BULKINOUT_MODEL")
        if not self.model:
            raise ValueError("Aucun modèle configuré. Utilisez --model ou BULKINOUT_MODEL.")

    def decide(self, case: ClinicalCase, missing_questions: list[dict], reference_context: dict | None = None) -> ImagingDecision:
        payload = {
            "clinical_case": case.model_dump(mode="json"),
            "unresolved_questions": missing_questions,
            "reference_context": reference_context or {},
        }
        response = self.client.responses.create(
            model=self.model,
            reasoning={"effort": "medium"},
            input=[
                {"role": "developer", "content": [{"type": "input_text", "text": DECISION_PROMPT}]},
                {"role": "user", "content": [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False)}]},
            ],
            text={"format": _schema_format(ImagingDecision)},
        )
        return ImagingDecision.model_validate_json(_extract_json(response))
