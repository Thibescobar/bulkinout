"""Reconcile repeated extracted facts without discarding their evidence."""

from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from typing import cast

from ...types import JsonObject, JsonValue
from ..models import (
    ClinicalCase,
    ClinicalField,
    FieldStatus,
    LLMFact,
    SourceRef,
    TemporalStatus,
    TimelineEvent,
)
from ..timeline import sort_timeline

_SECTIONS = {
    "patient",
    "current_problem",
    "history",
    "medications",
    "allergies",
    "labs",
    "imaging_safety",
}

# A historical positive may remain relevant even after a later negative statement.
_PERSISTENT_SAFETY_FIELDS = {
    "allergies.iodinated_contrast_reaction",
    "allergies.gadolinium_reaction",
    "imaging_safety.pacemaker",
    "imaging_safety.implant_or_metal",
}


def _sources(fact: LLMFact) -> list[SourceRef]:
    return [
        SourceRef(
            document_id=f"llm:{source.filename}",
            filename=source.filename,
            page=source.page,
            excerpt=source.excerpt,
        )
        for source in fact.sources
    ]


def _event(fact: LLMFact) -> TimelineEvent:
    return TimelineEvent(
        field=fact.field,
        value=cast(JsonValue, fact.value),
        status=FieldStatus(fact.status),
        temporal_status=TemporalStatus(fact.temporal_status),
        observed_at=fact.observed_at,
        sources=_sources(fact),
        confidence=fact.confidence,
    )


def _text_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())


def _value_key(value: JsonValue) -> str:
    if isinstance(value, str):
        return f"text:{_text_key(value)}"
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _unique_values(events: list[TimelineEvent]) -> list[JsonValue]:
    values: list[JsonValue] = []
    seen: set[str] = set()
    for event in events:
        key = _value_key(event.value)
        if key not in seen:
            seen.add(key)
            values.append(event.value)
    return values


def _all_sources(events: list[TimelineEvent]) -> list[SourceRef]:
    sources: list[SourceRef] = []
    seen: set[tuple[str, str, int | None, str | None]] = set()
    for event in events:
        for source in event.sources:
            identity = (source.document_id, source.filename, source.page, source.excerpt)
            if identity not in seen:
                seen.add(identity)
                sources.append(source)
    return sources


def _evidence_status(events: list[TimelineEvent]) -> FieldStatus:
    statuses = {event.status for event in events}
    if FieldStatus.conflicting in statuses:
        return FieldStatus.conflicting
    if FieldStatus.observed in statuses:
        return FieldStatus.observed
    if FieldStatus.inferred in statuses:
        return FieldStatus.inferred
    return FieldStatus.unknown


def _aggregate_temporal_status(events: list[TimelineEvent]) -> TemporalStatus:
    statuses = {event.temporal_status for event in events}
    if len(statuses) == 1:
        return next(iter(statuses))
    if TemporalStatus.current in statuses:
        return TemporalStatus.current
    return TemporalStatus.unknown


def _aggregate_observed_at(events: list[TimelineEvent]) -> str | None:
    dates = {event.observed_at for event in events if event.observed_at}
    return next(iter(dates)) if len(dates) == 1 else None


def _merge_list_values(events: list[TimelineEvent]) -> list[JsonValue] | None:
    if not events or not all(isinstance(event.value, list) for event in events):
        return None
    merged: list[JsonValue] = []
    seen: set[str] = set()
    for event in events:
        assert isinstance(event.value, list)
        for item in event.value:
            key = _value_key(item)
            if key not in seen:
                seen.add(key)
                merged.append(item)
    return merged


def _conflict_record(field: str, events: list[TimelineEvent], reason: str) -> JsonObject:
    return {
        "field": field,
        "reason": reason,
        "values": _unique_values(events),
        "temporal_statuses": cast(
            list[JsonValue], sorted({event.temporal_status.value for event in events})
        ),
        "observed_at": cast(
            list[JsonValue],
            sorted({event.observed_at for event in events if event.observed_at is not None}),
        ),
        "sources": cast(
            list[JsonValue],
            sorted({source.filename for event in events for source in event.sources}),
        ),
    }


def _aggregate_field(
    field: str, events: list[TimelineEvent]
) -> tuple[ClinicalField, JsonObject | None, JsonObject | None]:
    known = [
        event
        for event in events
        if event.status != FieldStatus.unknown and event.value not in (None, "", [])
    ]
    sources = _all_sources(events)
    if not known:
        return ClinicalField(sources=sources), None, None

    values = _unique_values(known)
    current = [event for event in known if event.temporal_status == TemporalStatus.current]
    current_values = _unique_values(current)

    conflict_reason: str | None = None
    selected = known
    value: JsonValue
    if any(event.status == FieldStatus.conflicting for event in known):
        conflict_reason = "The extractor explicitly reported conflicting evidence."
        value = cast(JsonValue, values)
    elif len(values) == 1:
        value = values[0]
    elif field in _PERSISTENT_SAFETY_FIELDS:
        conflict_reason = "Historical safety evidence differs from another statement."
        value = cast(JsonValue, values)
    elif current and _merge_list_values(current) is not None:
        selected = current
        value = cast(JsonValue, _merge_list_values(current))
    elif len(current_values) == 1:
        selected = current
        value = current_values[0]
    elif not current and all(
        event.temporal_status in {TemporalStatus.historical, TemporalStatus.resolved}
        for event in known
    ):
        value = cast(JsonValue, _merge_list_values(known) or values)
    else:
        conflict_reason = "Multiple materially different values remain unresolved."
        value = cast(JsonValue, values)

    status = FieldStatus.conflicting if conflict_reason else _evidence_status(selected)
    temporal_status = (
        TemporalStatus.unknown if conflict_reason else _aggregate_temporal_status(selected)
    )
    observed_at = None if conflict_reason else _aggregate_observed_at(selected)
    field_value = ClinicalField(
        value=value,
        status=status,
        sources=sources,
        confidence=min(event.confidence for event in selected),
        validated=False,
        temporal_status=temporal_status,
        observed_at=observed_at,
    )
    conflict = _conflict_record(field, known, conflict_reason) if conflict_reason else None
    resolution = None
    if not conflict_reason and selected is not known and len(values) > 1:
        resolution = {
            "field": field,
            "method": "explicit_current_status",
            "selected_value": value,
            "retained_evidence_count": len(known),
        }
    return field_value, conflict, resolution


def reconcile_facts(facts: list[LLMFact]) -> ClinicalCase:
    """Build one decision view and a lossless event view from extracted facts."""

    case = ClinicalCase()
    grouped: dict[str, list[TimelineEvent]] = defaultdict(list)
    for fact in facts:
        section_name, separator, _key = fact.field.partition(".")
        if not separator or section_name not in _SECTIONS:
            continue
        grouped[fact.field].append(_event(fact))

    conflicts: list[JsonObject] = []
    resolutions: list[JsonObject] = []
    for field, events in grouped.items():
        section_name, key = field.split(".", 1)
        clinical_field, conflict, resolution = _aggregate_field(field, events)
        section = cast(dict[str, ClinicalField], getattr(case, section_name))
        section[key] = clinical_field
        if conflict is not None:
            conflicts.append(conflict)
        if resolution is not None:
            resolutions.append(resolution)

    case.timeline = sort_timeline([event for events in grouped.values() for event in events])
    case.metadata["reconciliation"] = cast(
        JsonValue,
        {
            "conflicts": conflicts,
            "resolutions": resolutions,
            "policy": "explicit_current_status_only",
        },
    )
    return case
