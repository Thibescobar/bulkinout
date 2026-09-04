"""Typed representations of the YAML reference and its decision context."""

from __future__ import annotations

from typing import Required, TypedDict

from ..types import JsonObject, JsonValue

Predicate = TypedDict(
    "Predicate",
    {
        "field": Required[str],
        "equals": JsonValue,
        "not_equals": JsonValue,
        "contains": JsonValue,
        "contains_any": list[JsonValue],
        "contains_token": JsonValue,
        "contains_any_term": list[JsonValue],
        "in": list[JsonValue],
    },
    total=False,
)


class Condition(TypedDict, total=False):
    all: list[Predicate]
    any: list[Predicate]


class ReferenceQuestion(TypedDict, total=False):
    id: Required[str]
    field: Required[str]
    question: Required[str]
    priority: int
    material: bool
    required_to_choose: bool
    blocking: bool
    reason: str


class ReferenceCandidate(TypedDict, total=False):
    id: Required[str]
    exam_name: str
    modality: str
    contrast: str
    appropriateness: str
    when: Condition


ReferenceRule = TypedDict(
    "ReferenceRule",
    {"id": Required[str], "if": Condition, "result": JsonObject},
    total=False,
)


class ReferenceScenario(TypedDict, total=False):
    id: Required[str]
    title: Required[str]
    version: JsonValue
    status: JsonValue
    sources: list[JsonObject]
    entry: Condition
    questions: list[ReferenceQuestion]
    candidates: list[ReferenceCandidate]
    rules: list[ReferenceRule]
    notes: list[str]
    _source_file: str
    _source_sha256: str


class TriggeredRule(TypedDict):
    rule_id: str
    result: JsonObject


class MatchedScenarioContext(TypedDict):
    id: str
    title: str
    match_score: float
    version: JsonValue
    status: JsonValue
    sources: list[JsonObject]
    candidate_exams: list[ReferenceCandidate]
    unresolved_material_questions: list[ReferenceQuestion]
    rules_triggered: list[TriggeredRule]


class ReferenceContext(TypedDict):
    matched_scenarios: list[MatchedScenarioContext]


class CatalogEntry(TypedDict):
    id: JsonValue
    version: JsonValue
    title: JsonValue
    status: JsonValue
    source_file: str
    candidate_count: int
    question_count: int
    source_count: int
