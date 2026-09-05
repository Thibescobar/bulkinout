from __future__ import annotations

import json
from pathlib import Path

from ..core.models import AnswerFile, ClinicalCase, ClinicalField, FieldStatus, SourceRef

SECTION_NAMES = {
    "patient",
    "current_problem",
    "history",
    "medications",
    "allergies",
    "labs",
    "imaging_safety",
}


def load_answers(path: Path) -> AnswerFile:
    raw = json.loads(path.read_text(encoding="utf-8"))
    # Accept ergonomic {"answers": {"field": value}} as well as full list form.
    if isinstance(raw.get("answers"), dict):
        raw["answers"] = [
            {"field": field, "value": value} for field, value in raw["answers"].items()
        ]
    return AnswerFile.model_validate(raw)


def apply_answers(case: ClinicalCase, answer_file: AnswerFile, filename: str) -> ClinicalCase:
    for item in answer_file.answers:
        if item.value is None or (isinstance(item.value, str) and not item.value.strip()):
            continue
        if "." not in item.field:
            continue
        section_name, key = item.field.split(".", 1)
        if section_name not in SECTION_NAMES:
            continue
        section = getattr(case, section_name)
        section[key] = ClinicalField(
            value=item.value,
            status=FieldStatus.observed,
            sources=[
                SourceRef(
                    document_id=f"answers:{filename}",
                    filename=filename,
                    excerpt=item.note or item.question,
                )
            ],
            confidence=1.0,
            validated=False,
        )
    clarification_records = case.metadata.get("clarifications")
    if not isinstance(clarification_records, list):
        clarification_records = []
        case.metadata["clarifications"] = clarification_records
    clarification_records.extend(
        {
            **item.model_dump(mode="json"),
            "answer_source": filename,
            "state": (
                "unanswered"
                if item.value is None or (isinstance(item.value, str) and not item.value.strip())
                else "answered"
            ),
        }
        for item in answer_file.answers
    )
    answer_files = case.metadata.get("answer_files")
    if not isinstance(answer_files, list):
        answer_files = []
        case.metadata["answer_files"] = answer_files
    answer_files.append(filename)
    return case
