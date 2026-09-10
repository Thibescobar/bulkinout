from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast

import yaml

from ..core.models import ClinicalCase, ClinicalField, FieldStatus
from ..types import JsonObject, JsonValue
from .reference_engine import ReferenceEngine
from .types import MatchedScenarioContext


class GoldenExpected(TypedDict, total=False):
    scenario: str
    must_not_match: list[str]
    must_trigger_rules: list[str]
    must_not_trigger_rules: list[str]
    must_ask_fields: list[str]
    must_not_ask_fields: list[str]
    preferred_candidate: str
    no_imaging_recommended: bool


class GoldenSpec(TypedDict, total=False):
    id: str
    facts: JsonObject
    expected: GoldenExpected


def _observed(value: JsonValue) -> ClinicalField:
    return ClinicalField(value=value, status=FieldStatus.observed, confidence=1.0, validated=False)


def case_from_facts(facts: JsonObject) -> ClinicalCase:
    case = ClinicalCase()
    for field, value in facts.items():
        if "." not in field:
            continue
        section_name, key = field.split(".", 1)
        section = getattr(case, section_name, None)
        if isinstance(section, dict):
            section[key] = _observed(value)
    return case


@dataclass(frozen=True, slots=True)
class GoldenResult:
    case_id: str
    passed: bool
    errors: list[str]
    matched_scenarios: list[str]
    triggered_rules: list[str]
    unresolved_material_questions: list[str]


def _missing_errors(required: list[str], actual: list[str], message: str) -> list[str]:
    return [message.format(value=value) for value in required if value not in actual]


def _unexpected_errors(forbidden: list[str], actual: list[str], message: str) -> list[str]:
    return [message.format(value=value) for value in forbidden if value in actual]


def _has_rule_result(
    matches: list[MatchedScenarioContext], key: str, expected_value: JsonValue
) -> bool:
    return any(
        rule.get("result", {}).get(key) == expected_value
        for match in matches
        for rule in match.get("rules_triggered", [])
    )


def _expectation_errors(
    expected: GoldenExpected,
    matches: list[MatchedScenarioContext],
    matched_ids: list[str],
    triggered: list[str],
    unresolved: list[str],
) -> list[str]:
    errors: list[str] = []
    if "scenario" in expected and expected["scenario"] not in matched_ids:
        errors.append(f"Expected scenario {expected['scenario']!r}, got {matched_ids!r}")
    errors.extend(
        _unexpected_errors(
            expected.get("must_not_match", []), matched_ids, "Scenario {value!r} should not match"
        )
    )
    errors.extend(
        _missing_errors(
            expected.get("must_trigger_rules", []),
            triggered,
            "Expected rule {value!r} to trigger",
        )
    )
    errors.extend(
        _unexpected_errors(
            expected.get("must_not_trigger_rules", []),
            triggered,
            "Rule {value!r} should not trigger",
        )
    )
    errors.extend(
        _missing_errors(
            expected.get("must_ask_fields", []),
            unresolved,
            "Expected material question for {value!r}",
        )
    )
    errors.extend(
        _unexpected_errors(
            expected.get("must_not_ask_fields", []),
            unresolved,
            "Did not expect material question for {value!r}",
        )
    )

    preferred = expected.get("preferred_candidate")
    if preferred is not None and not _has_rule_result(matches, "preferred_candidate", preferred):
        errors.append(f"Expected preferred_candidate {preferred!r}")
    if expected.get("no_imaging_recommended") is True:
        if not _has_rule_result(matches, "no_imaging_recommended", True):
            errors.append("Expected no_imaging_recommended=true")
    return errors


def run_golden_case(path: Path, reference_dir: Path | None = None) -> GoldenResult:
    spec = cast(GoldenSpec, yaml.safe_load(path.read_text(encoding="utf-8")))
    case = case_from_facts(spec.get("facts", {}))
    expected = spec.get("expected", {})
    engine = ReferenceEngine(reference_dir)
    ctx = engine.build_context(case, max_scenarios=10)
    matches = ctx["matched_scenarios"]
    matched_ids = [m["id"] for m in matches]
    triggered = [r["rule_id"] for m in matches for r in m.get("rules_triggered", [])]
    unresolved = [q["field"] for m in matches for q in m.get("unresolved_material_questions", [])]
    errors = _expectation_errors(expected, matches, matched_ids, triggered, unresolved)

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
