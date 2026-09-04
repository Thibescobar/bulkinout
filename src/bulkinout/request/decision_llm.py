from __future__ import annotations

import json
import os
from typing import Any, TypeVar, cast

from openai import OpenAI
from pydantic import BaseModel

from ..core.models import ClinicalCase, ImagingDecision
from ..errors import ConfigurationError
from ..types import JsonObject, JsonValue
from .types import ReferenceContext

T = TypeVar("T", bound=BaseModel)

DECISION_PROMPT = """
You are Bulkinout Request, a radiology clinical decision-support component.
Given a structured clinical case, unresolved questions and a reference context,
reason across plausible imaging candidates.

This is decision support, not autonomous prescribing.
Clinical input may originate in any language. Do not assume that source documents are French.
Use canonical English identifiers and language-independent canonical structured values.
Write internal reasoning and metadata in English. Write only clinician- and radiologist-facing
presentation text in French for the current product, including clinical questions, examination
and protocol labels, the radiologist's clinical question, and request-facing rationale.

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


def _schema_format(model: type[T]) -> JsonObject:
    return {
        "type": "json_schema",
        "name": model.__name__,
        "strict": True,
        "schema": model.model_json_schema(),
    }


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


class OpenAIRequestDecision:
    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("BULKINOUT_DECISION_MODEL") or os.getenv("BULKINOUT_MODEL")
        if not self.model:
            raise ConfigurationError(
                "No decision model configured. Use --decision-model, "
                "BULKINOUT_DECISION_MODEL, --model, or BULKINOUT_MODEL."
            )
        if not os.getenv("OPENAI_API_KEY"):
            raise ConfigurationError("OPENAI_API_KEY is missing.")
        self.client = OpenAI()

    def decide(
        self,
        case: ClinicalCase,
        missing_questions: list[JsonObject],
        reference_context: ReferenceContext | None = None,
    ) -> ImagingDecision:
        payload: JsonObject = {
            "clinical_case": cast(JsonObject, case.model_dump(mode="json")),
            "unresolved_questions": cast(list[JsonValue], missing_questions),
            "reference_context": cast(JsonObject, reference_context or {}),
        }
        responses = cast(Any, self.client.responses)
        response = responses.create(
            model=self.model,
            reasoning={"effort": "medium"},
            input=[
                {"role": "developer", "content": [{"type": "input_text", "text": DECISION_PROMPT}]},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": json.dumps(payload, ensure_ascii=False)}
                    ],
                },
            ],
            text={"format": _schema_format(ImagingDecision)},
        )
        return ImagingDecision.model_validate_json(_extract_json(response))
