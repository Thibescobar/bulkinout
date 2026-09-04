"""Offline assertions for manual end-to-end model runs."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from .core.models import (
    ClinicalCase,
    ClinicalField,
    FieldStatus,
    ImagingDecision,
    MissingQuestion,
    TeleradiologyRequest,
)
from .errors import ConfigurationError, InputError
from .types import JsonValue


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NumericTolerance(_StrictModel):
    target: float
    absolute_tolerance: float = Field(ge=0.0)


class RequiredFactExpectation(_StrictModel):
    field: str
    status_in: list[FieldStatus] | None = None
    numeric: NumericTolerance | None = None


class ForbiddenValueExpectation(_StrictModel):
    field: str
    values: list[JsonValue] = Field(min_length=1)


class CoreExpectations(_StrictModel):
    required_facts: list[RequiredFactExpectation] = Field(default_factory=list)
    forbidden_facts: list[str] = Field(default_factory=list)
    forbidden_values: list[ForbiddenValueExpectation] = Field(default_factory=list)


class PresentationTermGroup(_StrictModel):
    any_of: list[str] = Field(min_length=1)


class RequestExpectations(_StrictModel):
    matched_scenarios_all_of: list[str] = Field(default_factory=list)
    matched_scenarios_any_of: list[str] = Field(default_factory=list)
    decision_status_in: list[str] = Field(default_factory=list)
    primary_exam_name_in: list[str] = Field(default_factory=list)
    primary_recommended: bool | None = None
    clinician_call_required: bool | None = None
    required_question_fields: list[str] = Field(default_factory=list)
    forbidden_question_fields: list[str] = Field(default_factory=list)
    presentation_term_groups: list[PresentationTermGroup] = Field(default_factory=list)


class E2EExpectations(_StrictModel):
    schema_version: int = Field(ge=1, le=1)
    case_id: str
    purpose: str
    core: CoreExpectations
    request: RequestExpectations


class AssertionFailure(_StrictModel):
    assertion: str
    message: str


class StageEvaluation(_StrictModel):
    passed: bool
    checks: int
    failures: list[AssertionFailure]


class EvaluationReport(_StrictModel):
    schema_version: int = 1
    case_id: str
    core: StageEvaluation
    request: StageEvaluation
    passed: bool


def _load_json(path: Path, *, expectation: bool = False) -> object:
    if not path.is_file():
        raise InputError(f"Required evaluation file is missing: {path}")
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        error_type = ConfigurationError if expectation else InputError
        raise error_type(f"Invalid JSON in {path}: {error}") from error
    return raw


def _load_expectations(case_dir: Path) -> E2EExpectations:
    path = case_dir / "expected.json"
    try:
        return E2EExpectations.model_validate(_load_json(path, expectation=True))
    except ValidationError as error:
        raise ConfigurationError(f"Invalid E2E expectations in {path}: {error}") from error


def _load_model(path: Path, model: type[BaseModel]) -> BaseModel:
    try:
        return model.model_validate(_load_json(path))
    except ValidationError as error:
        raise InputError(f"Invalid evaluation artifact {path}: {error}") from error


def _load_questions(path: Path) -> list[MissingQuestion]:
    try:
        return TypeAdapter(list[MissingQuestion]).validate_python(_load_json(path))
    except ValidationError as error:
        raise InputError(f"Invalid evaluation artifact {path}: {error}") from error


def _clinical_field(case: ClinicalCase, path: str) -> ClinicalField | None:
    section_name, separator, field_name = path.partition(".")
    section = getattr(case, section_name, None)
    if not separator or not isinstance(section, dict):
        return None
    value = section.get(field_name)
    return value if isinstance(value, ClinicalField) else None


def _known(field: ClinicalField | None) -> bool:
    return field is not None and field.status != FieldStatus.unknown


def _number(value: JsonValue) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    try:
        return float(value.strip().replace(",", "."))
    except ValueError:
        return None


def _normalized_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(without_marks.split())


def _equal_scalar(actual: JsonValue, expected: JsonValue) -> bool:
    if isinstance(actual, str) and isinstance(expected, str):
        return _normalized_text(actual) == _normalized_text(expected)
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    return actual == expected


def _failure(assertion: str, message: str) -> AssertionFailure:
    return AssertionFailure(assertion=assertion, message=message)


def _required_fact_failure(
    case: ClinicalCase, expectation: RequiredFactExpectation
) -> AssertionFailure | None:
    field = _clinical_field(case, expectation.field)
    assertion = f"core.required_fact:{expectation.field}"
    if not _known(field):
        return _failure(assertion, "Expected a non-unknown clinical fact.")
    assert field is not None
    if expectation.status_in is not None and field.status not in expectation.status_in:
        allowed = ", ".join(status.value for status in expectation.status_in)
        return _failure(assertion, f"Status {field.status.value!r} is not in [{allowed}].")
    if expectation.numeric is None:
        return None
    actual = _number(field.value)
    if actual is None:
        return _failure(assertion, f"Value {field.value!r} is not numeric.")
    distance = abs(actual - expectation.numeric.target)
    if distance > expectation.numeric.absolute_tolerance:
        return _failure(
            assertion,
            f"Value {actual} is outside {expectation.numeric.target} "
            f"± {expectation.numeric.absolute_tolerance}.",
        )
    return None


def _evaluate_core(case: ClinicalCase, expected: CoreExpectations) -> StageEvaluation:
    checks = 0
    failures: list[AssertionFailure] = []
    for expectation in expected.required_facts:
        checks += 1
        failure = _required_fact_failure(case, expectation)
        if failure is not None:
            failures.append(failure)
    for path in expected.forbidden_facts:
        checks += 1
        if _known(_clinical_field(case, path)):
            failures.append(_failure(f"core.forbidden_fact:{path}", "Fact was present."))
    for forbidden_expectation in expected.forbidden_values:
        checks += 1
        field = _clinical_field(case, forbidden_expectation.field)
        if (
            field is not None
            and field.status in {FieldStatus.observed, FieldStatus.inferred}
            and any(
                _equal_scalar(field.value, forbidden) for forbidden in forbidden_expectation.values
            )
        ):
            failures.append(
                _failure(
                    f"core.forbidden_value:{forbidden_expectation.field}",
                    f"Forbidden value {field.value!r} was present.",
                )
            )
    return StageEvaluation(passed=not failures, checks=checks, failures=failures)


def _matched_scenario_ids(raw: object, path: Path) -> set[str]:
    if not isinstance(raw, dict) or not isinstance(raw.get("matched_scenarios"), list):
        raise InputError(f"Invalid evaluation artifact {path}: matched_scenarios must be a list")
    identifiers: set[str] = set()
    for item in raw["matched_scenarios"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise InputError(f"Invalid evaluation artifact {path}: every scenario requires an id")
        identifiers.add(item["id"])
    return identifiers


def _presentation_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [str(value)]
    if isinstance(value, list):
        return [text for item in value for text in _presentation_values(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _presentation_values(item)]
    return []


def _request_scalar_failures(
    expected: RequestExpectations, decision: ImagingDecision
) -> tuple[int, list[AssertionFailure]]:
    checks = 0
    failures: list[AssertionFailure] = []
    comparisons: list[tuple[str, object, object | None]] = [
        ("primary_recommended", decision.primary.recommended, expected.primary_recommended),
        (
            "clinician_call_required",
            decision.clinician_call_required,
            expected.clinician_call_required,
        ),
    ]
    for name, actual, wanted in comparisons:
        if wanted is None:
            continue
        checks += 1
        if actual != wanted:
            failures.append(_failure(f"request.{name}", f"Expected {wanted!r}, got {actual!r}."))
    return checks, failures


def _request_choice_failures(
    expected: RequestExpectations,
    scenario_ids: set[str],
    decision: ImagingDecision,
) -> tuple[int, list[AssertionFailure]]:
    checks = 0
    failures: list[AssertionFailure] = []
    for scenario_id in expected.matched_scenarios_all_of:
        checks += 1
        if scenario_id not in scenario_ids:
            failures.append(_failure(f"request.scenario:{scenario_id}", "Scenario did not match."))
    if expected.matched_scenarios_any_of:
        checks += 1
        if scenario_ids.isdisjoint(expected.matched_scenarios_any_of):
            failures.append(_failure("request.scenario_any_of", "No acceptable scenario matched."))
    if expected.decision_status_in:
        checks += 1
        if decision.decision_status not in expected.decision_status_in:
            failures.append(
                _failure("request.decision_status", f"Got {decision.decision_status!r}.")
            )
    if expected.primary_exam_name_in:
        checks += 1
        if decision.primary.exam_name not in expected.primary_exam_name_in:
            failures.append(
                _failure("request.primary_exam_name", f"Got {decision.primary.exam_name!r}.")
            )
    return checks, failures


def _request_question_failures(
    expected: RequestExpectations, questions: list[MissingQuestion]
) -> tuple[int, list[AssertionFailure]]:
    checks = 0
    failures: list[AssertionFailure] = []
    question_fields = {question.field for question in questions}
    for field in expected.required_question_fields:
        checks += 1
        if field not in question_fields:
            failures.append(_failure(f"request.required_question:{field}", "Question was absent."))
    for field in expected.forbidden_question_fields:
        checks += 1
        if field in question_fields:
            failures.append(
                _failure(f"request.forbidden_question:{field}", "Question was present.")
            )
    return checks, failures


def _request_presentation_failures(
    expected: RequestExpectations, request: TeleradiologyRequest
) -> tuple[int, list[AssertionFailure]]:
    checks = 0
    failures: list[AssertionFailure] = []
    presentation = _normalized_text(" ".join(_presentation_values(request.model_dump(mode="json"))))
    for index, group in enumerate(expected.presentation_term_groups):
        checks += 1
        if not any(_normalized_text(term) in presentation for term in group.any_of):
            failures.append(
                _failure(
                    f"request.presentation_term_group:{index}",
                    f"None of the expected terms were present: {group.any_of!r}.",
                )
            )
    return checks, failures


def _evaluate_request(
    expected: RequestExpectations,
    scenario_ids: set[str],
    decision: ImagingDecision,
    questions: list[MissingQuestion],
    request: TeleradiologyRequest,
) -> StageEvaluation:
    groups = [
        _request_scalar_failures(expected, decision),
        _request_choice_failures(expected, scenario_ids, decision),
        _request_question_failures(expected, questions),
        _request_presentation_failures(expected, request),
    ]
    checks = sum(group_checks for group_checks, _ in groups)
    failures = [failure for _, group_failures in groups for failure in group_failures]
    return StageEvaluation(passed=not failures, checks=checks, failures=failures)


def evaluate_e2e_case(case_dir: Path, run_dir: Path) -> EvaluationReport:
    """Evaluate saved Core and Request artifacts without invoking a model."""

    expected = _load_expectations(case_dir)
    case = _load_model(run_dir / "case.json", ClinicalCase)
    decision = _load_model(run_dir / "imaging_decision.json", ImagingDecision)
    request = _load_model(run_dir / "teleradiology_request.json", TeleradiologyRequest)
    questions = _load_questions(run_dir / "missing_questions.json")
    reference_path = run_dir / "reference_context.json"
    scenario_ids = _matched_scenario_ids(_load_json(reference_path), reference_path)

    assert isinstance(case, ClinicalCase)
    assert isinstance(decision, ImagingDecision)
    assert isinstance(request, TeleradiologyRequest)
    core_report = _evaluate_core(case, expected.core)
    request_report = _evaluate_request(expected.request, scenario_ids, decision, questions, request)
    return EvaluationReport(
        case_id=expected.case_id,
        core=core_report,
        request=request_report,
        passed=core_report.passed and request_report.passed,
    )
