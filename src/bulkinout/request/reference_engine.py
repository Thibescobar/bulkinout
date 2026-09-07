from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from ..core.models import ClinicalCase, ClinicalField, FieldStatus, TemporalStatus
from ..errors import ReferenceDataError
from ..types import JsonValue
from .reference_resources import load_reference_documents
from .rules import pregnancy_is_relevant
from .types import (
    Condition,
    ConceptSelector,
    Predicate,
    ReferenceCandidate,
    ReferenceContext,
    ReferenceQuestion,
    ReferenceScenario,
    TriggeredRule,
)

_CURRENT_FACT_SECTIONS = {"current_problem", "labs", "medications", "imaging_safety"}


@dataclass(frozen=True, slots=True)
class ScenarioMatch:
    scenario_id: str
    title: str
    score: float
    source_file: str
    scenario: ReferenceScenario


def _clinical_field(case: ClinicalCase, field: str) -> ClinicalField | None:
    if "." not in field:
        return None
    section_name, key = field.split(".", 1)
    section = getattr(case, section_name, None)
    if not isinstance(section, dict):
        return None
    cf = section.get(key)
    if not isinstance(cf, ClinicalField) or cf.status in {
        FieldStatus.unknown,
        FieldStatus.conflicting,
    }:
        return None
    if section_name in _CURRENT_FACT_SECTIONS and cf.temporal_status != TemporalStatus.current:
        return None
    return cf


def _raw(case: ClinicalCase, field: str) -> tuple[JsonValue, bool]:
    clinical_field = _clinical_field(case, field)
    if clinical_field is None:
        return None, False
    return clinical_field.value, True


def _searchable_text(value: JsonValue) -> str:
    if isinstance(value, list):
        return " ".join(map(str, value)).lower()
    return str(value).lower()


def _contains_term(haystack: str, needle: JsonValue) -> bool:
    term = re.escape(str(needle).lower())
    return re.search(rf"(?<!\w){term}(?!\w)", haystack) is not None


def _has_concept(clinical_field: ClinicalField, selector: ConceptSelector) -> bool:
    return any(
        concept.system == selector["system"] and concept.code == selector["code"]
        for concept in clinical_field.coded_concepts
    )


def _concept_predicate(clinical_field: ClinicalField, pred: Predicate) -> bool | None:
    selector = pred.get("concept_is")
    if selector is not None:
        return _has_concept(clinical_field, selector)
    selectors = pred.get("concept_in")
    if selectors is not None:
        return any(_has_concept(clinical_field, item) for item in selectors)
    return None


def _predicate(case: ClinicalCase, pred: Predicate) -> bool:
    clinical_field = _clinical_field(case, pred["field"])
    if clinical_field is None:
        return False
    value = clinical_field.value
    concept_result = _concept_predicate(clinical_field, pred)
    if concept_result is not None:
        return concept_result
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
        documents = load_reference_documents(reference_dir)
        revision = hashlib.sha256()
        for source_name, document in documents:
            revision.update(source_name.encode("utf-8"))
            revision.update(b"\0")
            revision.update(document.encode("utf-8"))
            revision.update(b"\0")
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
            data["_source_sha256"] = hashlib.sha256(document.encode("utf-8")).hexdigest()
            self.scenarios.append(data)
        self.reference_revision = revision.hexdigest()

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
            if q["field"] == "imaging_safety.pregnancy" and not pregnancy_is_relevant(case):
                continue
            clinical_field = _clinical_field(case, q["field"])
            known = clinical_field is not None
            if known and not q["field"].startswith(("patient.", "history.")):
                assert clinical_field is not None
                known = clinical_field.temporal_status == TemporalStatus.current
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
