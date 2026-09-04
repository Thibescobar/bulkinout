from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import yaml

from ..core.models import ClinicalCase, FieldStatus


@dataclass
class ScenarioMatch:
    scenario_id: str
    title: str
    score: float
    source_file: str
    scenario: dict


def _raw(case: ClinicalCase, field: str):
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


def _predicate(case: ClinicalCase, pred: dict) -> bool:
    value, known = _raw(case, pred["field"])
    if not known:
        return False
    if "equals" in pred:
        return value == pred["equals"]
    if "not_equals" in pred:
        return value != pred["not_equals"]
    if "contains" in pred:
        needle = str(pred["contains"]).lower()
        if isinstance(value, list):
            hay = " ".join(map(str, value)).lower()
        else:
            hay = str(value).lower()
        return needle.lower() in hay
    if "in" in pred:
        return value in pred["in"]
    return False


def _condition(case: ClinicalCase, node: dict) -> bool:
    if "all" in node:
        return all(_predicate(case, p) for p in node["all"])
    if "any" in node:
        return any(_predicate(case, p) for p in node["any"])
    return False


def _candidate_applicable(case: ClinicalCase, candidate: dict) -> bool:
    condition = candidate.get("when")
    if not condition:
        return True
    return _condition(case, condition)


class ReferenceEngine:
    def __init__(self, reference_dir: Path):
        self.reference_dir = reference_dir
        self.scenarios = []
        for p in sorted(reference_dir.glob("*.yaml")):
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            data["_source_file"] = p.name
            self.scenarios.append(data)

    def match(self, case: ClinicalCase) -> list[ScenarioMatch]:
        matches = []
        for s in self.scenarios:
            entry = s.get("entry", {})
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
                matches.append(ScenarioMatch(
                    scenario_id=s["id"],
                    title=s["title"],
                    score=score,
                    source_file=s["_source_file"],
                    scenario=s,
                ))
        return sorted(matches, key=lambda x: x.score, reverse=True)

    def unresolved_material_questions(self, case: ClinicalCase, scenario: dict) -> list[dict]:
        out = []
        for q in scenario.get("questions", []):
            _, known = _raw(case, q["field"])
            if not known and q.get("material", False):
                out.append(q)
        return sorted(out, key=lambda q: q.get("priority", 99))

    def evaluate_rules(self, case: ClinicalCase, scenario: dict) -> list[dict]:
        results = []
        for rule in scenario.get("rules", []):
            if _condition(case, rule.get("if", {})):
                results.append({
                    "rule_id": rule["id"],
                    "result": rule["result"],
                })
        return results

    def build_context(self, case: ClinicalCase, max_scenarios: int = 3) -> dict:
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
                        c for c in m.scenario.get("candidates", [])
                        if _candidate_applicable(case, c)
                    ],
                    "unresolved_material_questions": self.unresolved_material_questions(case, m.scenario),
                    "rules_triggered": self.evaluate_rules(case, m.scenario),
                }
                for m in matches
            ]
        }
