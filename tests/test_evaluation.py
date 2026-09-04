import json
from pathlib import Path

import pytest

from bulkinout.core.models import (
    ClinicalCase,
    ClinicalField,
    FieldStatus,
    ImagingDecision,
    ImagingRecommendation,
    MissingQuestion,
    TeleradiologyRequest,
)
from bulkinout.errors import ConfigurationError, InputError
from bulkinout.evaluation import E2EExpectations, evaluate_e2e_case


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _expectations():
    return {
        "schema_version": 1,
        "case_id": "synthetic_case",
        "purpose": "Exercise the offline evaluator.",
        "core": {
            "required_facts": [
                {"field": "current_problem.location"},
                {
                    "field": "labs.egfr_ml_min_1_73m2",
                    "status_in": ["observed"],
                    "numeric": {"target": 105, "absolute_tolerance": 1},
                },
            ],
            "forbidden_facts": ["history.oncology"],
            "forbidden_values": [
                {
                    "field": "allergies.iodinated_contrast_reaction",
                    "values": [False, "no"],
                }
            ],
        },
        "request": {
            "matched_scenarios_all_of": ["rlq_appendicitis"],
            "matched_scenarios_any_of": ["rlq_appendicitis", "renal_colic"],
            "decision_status_in": ["selected"],
            "primary_exam_name_in": ["TDM abdomino-pelvienne avec injection IV"],
            "primary_recommended": True,
            "clinician_call_required": False,
            "required_question_fields": ["current_problem.onset"],
            "forbidden_question_fields": ["imaging_safety.pregnancy"],
            "presentation_term_groups": [
                {"any_of": ["fonction rénale", "DFG/eGFR"]},
                {"any_of": ["105"]},
            ],
        },
    }


def _write_run(run_dir, *, case=None, decision=None, questions=None, request=None, scenarios=None):
    if case is None:
        case = ClinicalCase(
            current_problem={
                "location": ClinicalField(value="right_lower_quadrant", status=FieldStatus.observed)
            },
            allergies={
                "iodinated_contrast_reaction": ClinicalField(
                    value="YES", status=FieldStatus.observed
                )
            },
            labs={"egfr_ml_min_1_73m2": ClinicalField(value="104,5", status=FieldStatus.observed)},
        )
    if decision is None:
        decision = ImagingDecision(
            decision_status="selected",
            primary=ImagingRecommendation(
                recommended=True,
                modality="CT",
                exam_name="TDM abdomino-pelvienne avec injection IV",
            ),
            clinician_call_required=False,
        )
    if questions is None:
        questions = [
            MissingQuestion(
                field="current_problem.onset",
                question="Depuis quand ?",
                importance="high",
                reason="Changes urgency.",
            )
        ]
    if request is None:
        request = TeleradiologyRequest(relevant_labs=["DFG/eGFR : 105"])
    if scenarios is None:
        scenarios = [{"id": "rlq_appendicitis"}]
    _write_json(run_dir / "case.json", case.model_dump(mode="json"))
    _write_json(run_dir / "imaging_decision.json", decision.model_dump(mode="json"))
    _write_json(
        run_dir / "missing_questions.json",
        [question.model_dump(mode="json") for question in questions],
    )
    _write_json(run_dir / "teleradiology_request.json", request.model_dump(mode="json"))
    _write_json(run_dir / "reference_context.json", {"matched_scenarios": scenarios})


def test_evaluate_e2e_case_passes_typed_clinical_assertions(tmp_path):
    case_dir = tmp_path / "fixture"
    run_dir = tmp_path / "run"
    _write_json(case_dir / "expected.json", _expectations())
    _write_run(run_dir)

    report = evaluate_e2e_case(case_dir, run_dir)

    assert report.passed is True
    assert report.core.passed is True
    assert report.request.passed is True
    assert report.core.checks == 4
    assert report.request.checks == 10
    assert report.core.failures == []
    assert report.request.failures == []


def test_evaluate_e2e_case_attributes_core_and_request_failures_separately(tmp_path):
    expected = _expectations()
    case_dir = tmp_path / "fixture"
    run_dir = tmp_path / "run"
    _write_json(case_dir / "expected.json", expected)
    case = ClinicalCase(
        current_problem={"location": ClinicalField()},
        history={"oncology": ClinicalField(value=True, status=FieldStatus.inferred)},
        allergies={
            "iodinated_contrast_reaction": ClinicalField(value="NO", status=FieldStatus.observed)
        },
        labs={"egfr_ml_min_1_73m2": ClinicalField(value=110, status=FieldStatus.observed)},
    )
    decision = ImagingDecision(
        decision_status="insufficient_information",
        primary=ImagingRecommendation(recommended=False, exam_name="Échographie"),
        clinician_call_required=True,
    )
    _write_run(
        run_dir,
        case=case,
        decision=decision,
        questions=[],
        request=TeleradiologyRequest(patient_summary="Aucun terme attendu"),
        scenarios=[{"id": "unrelated"}],
    )

    report = evaluate_e2e_case(case_dir, run_dir)

    assert report.passed is False
    assert {failure.assertion for failure in report.core.failures} == {
        "core.required_fact:current_problem.location",
        "core.required_fact:labs.egfr_ml_min_1_73m2",
        "core.forbidden_fact:history.oncology",
        "core.forbidden_value:allergies.iodinated_contrast_reaction",
    }
    assert report.request.passed is False
    assert "request.scenario:rlq_appendicitis" in {
        failure.assertion for failure in report.request.failures
    }
    assert "request.decision_status" in {failure.assertion for failure in report.request.failures}
    assert "request.required_question:current_problem.onset" in {
        failure.assertion for failure in report.request.failures
    }


def test_required_fact_rejects_unknown_even_when_status_list_includes_it(tmp_path):
    expected = _expectations()
    expected["core"] = {
        "required_facts": [{"field": "current_problem.location", "status_in": ["unknown"]}]
    }
    expected["request"] = {}
    case_dir = tmp_path / "fixture"
    run_dir = tmp_path / "run"
    _write_json(case_dir / "expected.json", expected)
    _write_run(
        run_dir,
        case=ClinicalCase(current_problem={"location": ClinicalField()}),
    )

    report = evaluate_e2e_case(case_dir, run_dir)

    assert report.core.passed is False
    assert report.request.passed is True


def test_forbidden_value_allows_an_explicit_conflict(tmp_path):
    expected = _expectations()
    expected["core"] = {
        "forbidden_values": [
            {
                "field": "allergies.iodinated_contrast_reaction",
                "values": [False, "no"],
            }
        ]
    }
    expected["request"] = {}
    case_dir = tmp_path / "fixture"
    run_dir = tmp_path / "run"
    _write_json(case_dir / "expected.json", expected)
    _write_run(
        run_dir,
        case=ClinicalCase(
            allergies={
                "iodinated_contrast_reaction": ClinicalField(
                    value=False,
                    status=FieldStatus.conflicting,
                )
            }
        ),
    )

    report = evaluate_e2e_case(case_dir, run_dir)

    assert report.core.passed is True


def test_evaluate_e2e_case_rejects_malformed_expectations(tmp_path):
    case_dir = tmp_path / "fixture"
    run_dir = tmp_path / "run"
    malformed = _expectations()
    malformed["unexpected"] = True
    _write_json(case_dir / "expected.json", malformed)
    _write_run(run_dir)

    with pytest.raises(ConfigurationError, match="Invalid E2E expectations"):
        evaluate_e2e_case(case_dir, run_dir)


def test_evaluate_e2e_case_reports_missing_or_invalid_artifacts(tmp_path):
    case_dir = tmp_path / "fixture"
    run_dir = tmp_path / "run"
    _write_json(case_dir / "expected.json", _expectations())

    with pytest.raises(InputError, match="case.json"):
        evaluate_e2e_case(case_dir, run_dir)

    _write_run(run_dir)
    (run_dir / "reference_context.json").write_text("[]", encoding="utf-8")
    with pytest.raises(InputError, match="matched_scenarios must be a list"):
        evaluate_e2e_case(case_dir, run_dir)


def test_repository_e2e_expectations_use_supported_schema():
    expected_files = sorted(Path("tests/e2e").glob("*/expected.json"))

    assert len(expected_files) == 4
    for path in expected_files:
        E2EExpectations.model_validate_json(path.read_text(encoding="utf-8"))
