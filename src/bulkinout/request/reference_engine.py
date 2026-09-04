from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from ..core.models import ClinicalCase, FieldStatus
from ..errors import ReferenceDataError
from ..types import JsonValue
from .reference_resources import load_reference_documents
from .types import (
    Condition,
    Predicate,
    ReferenceCandidate,
    ReferenceContext,
    ReferenceQuestion,
    ReferenceScenario,
    TriggeredRule,
)


@dataclass(frozen=True, slots=True)
class ScenarioMatch:
    scenario_id: str
    title: str
    score: float
    source_file: str
    scenario: ReferenceScenario


def _raw(case: ClinicalCase, field: str) -> tuple[JsonValue, bool]:
    if "." not in field:
        return None, False
    section_name, key = field.split(".", 1)
    section = getattr(case, section_name, None)
    if not isinstance(section, dict):
        return None, False
    cf = section.get(key)
    if not cf or cf.status in {FieldStatus.unknown, FieldStatus.conflicting}:
        return None, False
    return cf.value, True


def _searchable_text(value: JsonValue) -> str:
    if isinstance(value, list):
        return " ".join(map(str, value)).lower()
    return str(value).lower()


def _contains_term(haystack: str, needle: JsonValue) -> bool:
    term = re.escape(str(needle).lower())
    return re.search(rf"(?<!\w){term}(?!\w)", haystack) is not None


def _predicate(case: ClinicalCase, pred: Predicate) -> bool:
    value, known = _raw(case, pred["field"])
    if not known:
        return False
    if "equals" in pred:
        return value == pred["equals"]
    if "not_equals" in pred:
        return value != pred["not_equals"]
    haystack = _searchable_text(value)
    if "contains" in pred:
        return str(pred["contains"]).lower() in haystack
    if "contains_any" in pred:
        return any(str(needle).lower() in haystack for needle in pred["contains_any"])
    if "contains_token" in pred:
        return _contains_term(haystack, pred["contains_token"])
    if "contains_any_term" in pred:
        return any(_contains_term(haystack, needle) for needle in pred["contains_any_term"])
    if "in" in pred:
        return value in pred["in"]
    return False


def _condition(case: ClinicalCase, node: Condition) -> bool:
    if "all" in node:
        return all(_predicate(case, p) for p in node["all"])
    if "any" in node:
        return any(_predicate(case, p) for p in node["any"])
    return False


def _candidate_applicable(case: ClinicalCase, candidate: ReferenceCandidate) -> bool:
    condition = candidate.get("when")
    if not condition:
        return True
    return _condition(case, condition)


class ReferenceEngine:
    def __init__(self, reference_dir: Path | None = None):
        self.reference_dir = reference_dir
        self.scenarios: list[ReferenceScenario] = []
        for source_name, document in load_reference_documents(reference_dir):
            try:
                raw = yaml.safe_load(document)
            except yaml.YAMLError as error:
                raise ReferenceDataError(
                    f"Reference file contains invalid YAML: {source_name}: {error}"
                ) from error
            if not isinstance(raw, dict):
                raise ReferenceDataError(f"Reference file must contain a mapping: {source_name}")
            if not isinstance(raw.get("id"), str) or not isinstance(raw.get("title"), str):
                raise ReferenceDataError(
                    f"Reference file requires string id and title: {source_name}"
                )
            data = cast(ReferenceScenario, raw)
            data["_source_file"] = source_name
            self.scenarios.append(data)

    def match(self, case: ClinicalCase) -> list[ScenarioMatch]:
        matches: list[ScenarioMatch] = []
        for scenario in self.scenarios:
            entry = scenario.get("entry", {})
            if "all" in entry:
                predicates = entry["all"]
                hits = sum(_predicate(case, p) for p in predicates)
                score = hits / max(1, len(predicates))
                qualifies = hits == len(predicates)
            else:
                predicates = entry.get("any", [])
                hits = sum(_predicate(case, p) for p in predicates)
                score = hits / max(1, len(predicates))
                qualifies = hits > 0
            if qualifies:
                matches.append(
                    ScenarioMatch(
                        scenario_id=scenario["id"],
                        title=scenario["title"],
                        score=score,
                        source_file=scenario["_source_file"],
                        scenario=scenario,
                    )
                )
        return sorted(matches, key=lambda x: x.score, reverse=True)

    def unresolved_material_questions(
        self, case: ClinicalCase, scenario: ReferenceScenario
    ) -> list[ReferenceQuestion]:
        out: list[ReferenceQuestion] = []
        for q in scenario.get("questions", []):
            _, known = _raw(case, q["field"])
            is_relevant = (
                q.get("material", False)
                or q.get("required_to_choose", False)
                or q.get("blocking", False)
            )
            if not known and is_relevant:
                out.append(q)
        return sorted(out, key=lambda q: q.get("priority", 99))

    def evaluate_rules(
        self, case: ClinicalCase, scenario: ReferenceScenario
    ) -> list[TriggeredRule]:
        results: list[TriggeredRule] = []
        for rule in scenario.get("rules", []):
            if _condition(case, rule.get("if", {})):
                results.append(
                    {
                        "rule_id": rule["id"],
                        "result": rule["result"],
                    }
                )
        return results

    def build_context(self, case: ClinicalCase, max_scenarios: int = 3) -> ReferenceContext:
        matches = self.match(case)[:max_scenarios]
        return {
            "matched_scenarios": [
                {
                    "id": m.scenario_id,
                    "title": m.title,
                    "match_score": m.score,
                    "version": m.scenario.get("version"),
                    "status": m.scenario.get("status"),
                    "sources": m.scenario.get("sources", []),
                    "candidate_exams": [
                        c
                        for c in m.scenario.get("candidates", [])
                        if _candidate_applicable(case, c)
                    ],
                    "unresolved_material_questions": self.unresolved_material_questions(
                        case, m.scenario
                    ),
                    "rules_triggered": self.evaluate_rules(case, m.scenario),
                }
                for m in matches
            ]
        }
