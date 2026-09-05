"""JSON output writers shared by the CLI and Python integrations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, cast

from .core.models import MissingQuestion
from .request.clarification import required_clarification_questions
from .types import JsonObject, JsonValue

if TYPE_CHECKING:
    from .core.service import CoreResult
    from .request.service import RequestResult


def write_json(path: Path, payload: JsonValue) -> None:
    """Write one human-readable UTF-8 JSON document."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _answer_template(questions: list[MissingQuestion]) -> JsonObject:
    required = required_clarification_questions(questions)
    return {
        "answers": [
            {
                "question_id": question.question_id or question.field,
                "field": question.field,
                "value": None,
                "note": question.question,
            }
            for question in required
        ]
    }


def write_core_outputs(result: CoreResult, output_dir: Path) -> None:
    """Persist the two Core output snapshots."""

    write_json(
        output_dir / "radiology_case.json",
        cast(JsonObject, result.radiology_case.model_dump(mode="json")),
    )
    write_json(
        output_dir / "llm_extraction.json",
        cast(JsonObject, result.extraction.model_dump(mode="json")),
    )


def write_request_outputs(result: RequestResult, output_dir: Path) -> None:
    """Persist the complete set of Request workflow snapshots."""

    payloads: dict[str, JsonValue] = {
        "radiology_case.json": cast(JsonObject, result.radiology_case.model_dump(mode="json")),
        "llm_extraction.json": cast(JsonObject, result.extraction.model_dump(mode="json")),
        "case.json": cast(JsonObject, result.clinical_case.model_dump(mode="json")),
        "reference_context.json": cast(JsonObject, result.reference_context),
        "missing_questions.json": [
            cast(JsonObject, question.model_dump(mode="json"))
            for question in result.missing_questions
        ],
        "imaging_decision.json": cast(JsonObject, result.imaging_decision.model_dump(mode="json")),
        "teleradiology_request.json": cast(
            JsonObject, result.teleradiology_request.model_dump(mode="json")
        ),
        "answers.template.json": _answer_template(result.missing_questions),
    }
    if result.run_manifest is not None:
        payloads["run_manifest.json"] = cast(
            JsonObject, result.run_manifest.model_dump(mode="json")
        )
    if result.radiology_handoff is not None:
        payloads["radiology_handoff.json"] = cast(
            JsonObject, result.radiology_handoff.model_dump(mode="json")
        )
    for filename, payload in payloads.items():
        write_json(output_dir / filename, payload)
    if result.radiology_handoff is not None:
        from .request.handoff import render_radiology_handoff_html

        html = render_radiology_handoff_html(result.radiology_handoff)
        (output_dir / "radiology_handoff.html").write_text(html, encoding="utf-8")
