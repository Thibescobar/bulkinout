from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..core.models import ClinicalCase, ClinicalField, FieldStatus
from .reference_engine import ReferenceEngine


def _observed(value):
    return ClinicalField(value=value, status=FieldStatus.observed, confidence=1.0, validated=False)

def case_from_facts(facts: dict[str, Any]) -> ClinicalCase:
    case = ClinicalCase()
    for field, value in facts.items():
        if "." not in field:
            continue
        section_name, key = field.split(".", 1)
        section = getattr(case, section_name, None)
        if isinstance(section, dict):
            section[key] = _observed(value)
    return case

@dataclass
class GoldenResult:
    case_id: str
    passed: bool
    errors: list[str]
    matched_scenarios: list[str]
    triggered_rules: list[str]
    unresolved_material_questions: list[str]

def run_golden_case(path: Path, reference_dir: Path) -> GoldenResult:
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    case = case_from_facts(spec.get("facts", {}))
    expected = spec.get("expected", {})
    engine = ReferenceEngine(reference_dir)
    ctx = engine.build_context(case, max_scenarios=10)
    matches = ctx["matched_scenarios"]
    matched_ids = [m["id"] for m in matches]
    triggered = [r["rule_id"] for m in matches for r in m.get("rules_triggered", [])]
    unresolved = [q["field"] for m in matches for q in m.get("unresolved_material_questions", [])]
    errors = []

    if "scenario" in expected and expected["scenario"] not in matched_ids:
        errors.append(f"Expected scenario {expected['scenario']!r}, got {matched_ids!r}")
    for scenario in expected.get("must_not_match", []):
        if scenario in matched_ids:
            errors.append(f"Scenario {scenario!r} should not match")
    for rule in expected.get("must_trigger_rules", []):
        if rule not in triggered:
            errors.append(f"Expected rule {rule!r} to trigger")
    for rule in expected.get("must_not_trigger_rules", []):
        if rule in triggered:
            errors.append(f"Rule {rule!r} should not trigger")
    for field in expected.get("must_ask_fields", []):
        if field not in unresolved:
            errors.append(f"Expected material question for {field!r}")
    for field in expected.get("must_not_ask_fields", []):
        if field in unresolved:
            errors.append(f"Did not expect material question for {field!r}")

    if "preferred_candidate" in expected:
        preferred = expected["preferred_candidate"]
        found = any(
            r.get("result", {}).get("preferred_candidate") == preferred
            for m in matches for r in m.get("rules_triggered", [])
        )
        if not found:
            errors.append(f"Expected preferred_candidate {preferred!r}")

    if expected.get("no_imaging_recommended") is True:
        found = any(
            r.get("result", {}).get("no_imaging_recommended") is True
            for m in matches for r in m.get("rules_triggered", [])
        )
        if not found:
            errors.append("Expected no_imaging_recommended=true")

    return GoldenResult(
        case_id=spec.get("id", path.stem),
        passed=not errors,
        errors=errors,
        matched_scenarios=matched_ids,
        triggered_rules=triggered,
        unresolved_material_questions=sorted(set(unresolved)),
    )

def discover_golden_cases(case_dir: Path) -> list[Path]:
    return sorted(case_dir.rglob("*.yaml"))
