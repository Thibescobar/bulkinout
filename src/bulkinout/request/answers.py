from __future__ import annotations

import json
from pathlib import Path

from ..core.models import (
    AnswerFile,
    AnswerItem,
    ClinicalCase,
    ClinicalField,
    FieldStatus,
    SourceRef,
    TemporalStatus,
    TimelineEvent,
)
from ..core.timeline import append_timeline_event

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


def _record_resolution(
    case: ClinicalCase,
    item: AnswerItem,
    filename: str,
    previous: ClinicalField | None,
) -> None:
    if previous is None or (
        previous.status != FieldStatus.conflicting and previous.value == item.value
    ):
        return
    reconciliation = case.metadata.get("reconciliation")
    if not isinstance(reconciliation, dict):
        reconciliation = {}
        case.metadata["reconciliation"] = reconciliation
    resolutions = reconciliation.get("resolutions")
    if not isinstance(resolutions, list):
        resolutions = []
        reconciliation["resolutions"] = resolutions
    resolutions.append(
        {
            "field": item.field,
            "method": "explicit_clinician_answer",
            "previous_value": previous.value,
            "selected_value": item.value,
            "answer_source": filename,
        }
    )


def _apply_answer(
    case: ClinicalCase,
    item: AnswerItem,
    filename: str,
    section_name: str,
    key: str,
) -> None:
    section = getattr(case, section_name)
    previous = section.get(key)
    answer_source = SourceRef(
        document_id=f"answers:{filename}",
        filename=filename,
        excerpt=item.note or item.question,
    )
    retained_sources = list(previous.sources) if previous is not None else []
    if answer_source not in retained_sources:
        retained_sources.append(answer_source)
    observed_at = item.answered_at.isoformat() if item.answered_at else None
    section[key] = ClinicalField(
        value=item.value,
        status=FieldStatus.observed,
        sources=retained_sources,
        confidence=1.0,
        validated=False,
        temporal_status=TemporalStatus.current,
        observed_at=observed_at,
    )
    append_timeline_event(
        case,
        TimelineEvent(
            field=item.field,
            value=item.value,
            status=FieldStatus.observed,
            temporal_status=TemporalStatus.current,
            observed_at=observed_at,
            sources=[answer_source],
            confidence=1.0,
        ),
    )
    _record_resolution(case, item, filename, previous)


def apply_answers(case: ClinicalCase, answer_file: AnswerFile, filename: str) -> ClinicalCase:
    for item in answer_file.answers:
        if item.value is None or (isinstance(item.value, str) and not item.value.strip()):
            continue
        if "." not in item.field:
            continue
        section_name, key = item.field.split(".", 1)
        if section_name not in SECTION_NAMES:
            continue
        _apply_answer(case, item, filename, section_name, key)
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
