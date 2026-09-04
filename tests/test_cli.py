import json
from types import SimpleNamespace

import pytest

from bulkinout import cli
from bulkinout.core.models import (
    ClinicalCase,
    ImagingDecision,
    ImagingRecommendation,
    LLMExtraction,
    MissingQuestion,
    RadiologyCase,
    TeleradiologyRequest,
)
from bulkinout.core.service import CoreResult
from bulkinout.errors import ConfigurationError
from bulkinout.request.service import RequestResult


def request_result() -> RequestResult:
    case = ClinicalCase()
    decision = ImagingDecision(
        decision_status="selected",
        primary=ImagingRecommendation(modality="CT", exam_name="CT abdomen"),
        clinician_call_required=False,
        decision_ready_for_human_approval=True,
    )
    return RequestResult(
        radiology_case=RadiologyCase(clinical=case),
        extraction=LLMExtraction(),
        clinical_case=case,
        reference_context={"matched_scenarios": []},
        missing_questions=[
            MissingQuestion(
                field="current_problem.indication",
                question="Quelle est l'indication ?",
                importance="critical",
                reason="Required",
            )
        ],
        imaging_decision=decision,
        teleradiology_request=TeleradiologyRequest(status="ready_for_human_approval"),
        source_paths=[],
    )


def test_core_structure_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    args = SimpleNamespace(input=str(tmp_path), output=str(tmp_path / "out"), model="model")

    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY is missing"):
        cli.cmd_core_structure(args)


def test_core_structure_writes_outputs(monkeypatch, tmp_path, capsys):
    from bulkinout.core import service as core_service

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    result = CoreResult(RadiologyCase(), LLMExtraction(), [])
    monkeypatch.setattr(core_service, "build_radiology_case", lambda input_dir, model: result)
    output = tmp_path / "out"

    cli.cmd_core_structure(SimpleNamespace(input=str(tmp_path), output=str(output), model="model"))

    assert (output / "radiology_case.json").exists()
    assert (output / "llm_extraction.json").exists()
    assert "Core structuring completed" in capsys.readouterr().out


def test_request_run_delegates_and_writes_all_outputs(monkeypatch, tmp_path, capsys):
    from bulkinout.request import service as request_service

    result = request_result()
    calls = []
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        request_service,
        "run_request",
        lambda input_dir, **kwargs: calls.append((input_dir, kwargs)) or result,
    )
    output = tmp_path / "out"
    answers = tmp_path / "answers.json"

    cli.cmd_request_run(
        SimpleNamespace(
            input=str(tmp_path),
            output=str(output),
            answers=str(answers),
            reference=str(tmp_path / "reference"),
            model="model",
            extraction_model="extraction-model",
            decision_model="decision-model",
        )
    )

    assert calls == [
        (
            tmp_path,
            {
                "reference_dir": tmp_path / "reference",
                "model": "model",
                "extraction_model": "extraction-model",
                "decision_model": "decision-model",
                "answers_path": answers,
            },
        )
    ]
    assert {
        "radiology_case.json",
        "llm_extraction.json",
        "case.json",
        "reference_context.json",
        "missing_questions.json",
        "imaging_decision.json",
        "teleradiology_request.json",
        "answers.template.json",
    } == {path.name for path in output.iterdir()}
    assert json.loads((output / "missing_questions.json").read_text())[0]["field"] == (
        "current_problem.indication"
    )
    assert "Decision: selected" in capsys.readouterr().out


def test_request_golden_handles_empty_success_and_failure(monkeypatch, tmp_path, capsys):
    args = SimpleNamespace(reference=str(tmp_path), cases=str(tmp_path))
    monkeypatch.setattr(cli, "discover_golden_cases", lambda path: [])
    with pytest.raises(ConfigurationError, match="No golden cases found"):
        cli.cmd_request_golden(args)

    paths = [tmp_path / "pass.yaml", tmp_path / "fail.yaml"]
    results = {
        paths[0]: SimpleNamespace(case_id="pass", passed=True, errors=[]),
        paths[1]: SimpleNamespace(case_id="fail", passed=False, errors=["bad result"]),
    }
    monkeypatch.setattr(cli, "discover_golden_cases", lambda path: paths)
    monkeypatch.setattr(cli, "run_golden_case", lambda path, reference: results[path])

    with pytest.raises(SystemExit) as error:
        cli.cmd_request_golden(args)

    assert error.value.code == 1
    output = capsys.readouterr().out
    assert "[PASS] pass" in output
    assert "[FAIL] fail" in output
    assert "bad result" in output


def test_request_catalog_prints_scenarios(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        cli,
        "build_catalog",
        lambda path: [
            {
                "id": "renal_colic",
                "version": 1,
                "candidate_count": 2,
                "question_count": 3,
                "status": "needs_local_validation",
            }
        ],
    )

    cli.cmd_request_catalog(SimpleNamespace(reference=str(tmp_path)))

    output = capsys.readouterr().out
    assert "1 scenario(s)" in output
    assert "renal_colic v1" in output


def test_request_catalog_uses_packaged_reference_by_default(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(cli, "build_catalog", lambda path: calls.append(path) or [])

    cli.main(["request", "catalog"])

    assert calls == [None]
    assert "0 scenario(s)" in capsys.readouterr().out


def test_request_evaluate_prints_stages_and_writes_report(monkeypatch, tmp_path, capsys):
    report = SimpleNamespace(
        core=SimpleNamespace(passed=True, checks=3, failures=[]),
        request=SimpleNamespace(passed=True, checks=4, failures=[]),
        passed=True,
        model_dump=lambda mode: {"passed": True},
    )
    monkeypatch.setattr(cli, "evaluate_e2e_case", lambda case, run: report)
    report_path = tmp_path / "evaluation.json"

    cli.main(
        [
            "request",
            "evaluate",
            "--case",
            "tests/e2e/example",
            "--run",
            "output/example",
            "--report",
            str(report_path),
        ]
    )

    output = capsys.readouterr().out
    assert "[PASS] Core (3 checks)" in output
    assert "[PASS] Request (4 checks)" in output
    assert json.loads(report_path.read_text(encoding="utf-8")) == {"passed": True}


def test_request_evaluate_exits_one_for_assertion_failures(monkeypatch, capsys):
    failure = SimpleNamespace(assertion="request.decision_status", message="Unexpected status.")
    report = SimpleNamespace(
        core=SimpleNamespace(passed=True, checks=1, failures=[]),
        request=SimpleNamespace(passed=False, checks=1, failures=[failure]),
        passed=False,
    )
    monkeypatch.setattr(cli, "evaluate_e2e_case", lambda case, run: report)

    with pytest.raises(SystemExit) as error:
        cli.main(
            [
                "request",
                "evaluate",
                "--case",
                "tests/e2e/example",
                "--run",
                "output/example",
            ]
        )

    assert error.value.code == 1
    assert "[FAIL] Request" in capsys.readouterr().out


def test_main_dispatches_report_and_renders_expected_errors(monkeypatch, capsys):
    cli.main(["report"])
    assert "Bulkinout Report is reserved" in capsys.readouterr().out

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit) as error:
        cli.main(["core", "structure"])

    assert error.value.code == 2
    assert "error: OPENAI_API_KEY is missing" in capsys.readouterr().err


def test_request_run_help_describes_its_arguments(capsys):
    with pytest.raises(SystemExit) as error:
        cli.main(["request", "run", "--help"])

    assert error.value.code == 0
    output = capsys.readouterr().out
    assert "Optional JSON file of clinician answers" in output
    assert "Directory containing scenario YAML files" in output
    assert "--extraction-model" in output
    assert "--decision-model" in output
