import json
import sys
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
)


def question(field, text, *, blocking=False, importance="high"):
    return MissingQuestion(
        field=field,
        question=text,
        importance=importance,
        reason="Required for the test",
        blocking=blocking,
    )


def test_dump_and_answer_template_write_json(tmp_path):
    cli._dump(tmp_path / "nested" / "payload.json", {"name": "Unicode ✓"})
    decision = ImagingDecision(
        primary=ImagingRecommendation(),
        discriminating_questions=[
            {
                "question_id": "optional",
                "field": "patient.sex",
                "question": "Sex?",
                "why_it_matters": "Protocol",
                "priority": 2,
                "possible_decision_impact": "None",
                "required_to_choose": False,
            },
            {
                "question_id": "required",
                "field": "patient.age",
                "question": "Age?",
                "why_it_matters": "Protocol",
                "priority": 1,
                "possible_decision_impact": "Changes protocol",
                "required_to_choose": True,
            },
        ],
    )

    cli._write_answer_template(tmp_path, decision)

    assert json.loads((tmp_path / "nested" / "payload.json").read_text())["name"] == "Unicode ✓"
    payload = json.loads((tmp_path / "answers.template.json").read_text())
    assert payload["answers"] == [
        {
            "question_id": "required",
            "field": "patient.age",
            "value": None,
            "note": "Age?",
        }
    ]


def test_core_structure_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    args = SimpleNamespace(input=str(tmp_path), output=str(tmp_path / "out"), model="model")

    with pytest.raises(SystemExit, match="OPENAI_API_KEY is missing"):
        cli.cmd_core_structure(args)


def test_core_structure_writes_outputs(monkeypatch, tmp_path, capsys):
    from bulkinout.core import service

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        service,
        "build_radiology_case",
        lambda input_dir, model: (RadiologyCase(), LLMExtraction(), []),
    )
    output = tmp_path / "out"
    args = SimpleNamespace(input=str(tmp_path), output=str(output), model="model")

    cli.cmd_core_structure(args)

    assert (output / "radiology_case.json").exists()
    assert (output / "llm_extraction.json").exists()
    assert "Core structuring completed" in capsys.readouterr().out


def test_request_run_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    args = SimpleNamespace(
        input=str(tmp_path),
        output=str(tmp_path / "out"),
        answers=None,
        reference=str(tmp_path),
        model="model",
    )

    with pytest.raises(SystemExit, match="OPENAI_API_KEY is missing"):
        cli.cmd_request_run(args)


def test_request_run_applies_guards_and_writes_all_outputs(monkeypatch, tmp_path, capsys):
    from bulkinout.core import service
    from bulkinout.request import decision_llm

    case = ClinicalCase()
    radiology_case = RadiologyCase(clinical=case)
    extraction = LLMExtraction()
    decision = ImagingDecision(
        decision_status="selected",
        primary=ImagingRecommendation(
            modality="MRI",
            exam_name="MRI brain",
            contrast="no",
            confidence=0.8,
        ),
        clinician_call_required=False,
        decision_ready_for_human_approval=True,
    )

    class FakeReferenceEngine:
        def __init__(self, path):
            self.path = path

        def build_context(self, received_case):
            assert received_case is case
            return {"matched_scenarios": []}

    class FakeDecisionEngine:
        def __init__(self, model=None):
            self.model = model

        def decide(self, received_case, missing_questions, reference_context=None):
            assert received_case is case
            assert missing_questions[0]["field"] == "current_problem.indication"
            assert reference_context == {"matched_scenarios": []}
            return decision

    initial = question(
        "current_problem.indication",
        "Clinical indication?",
        blocking=True,
        importance="critical",
    )
    safety = question("imaging_safety.pacemaker", "Pacemaker?", blocking=True)
    nonblocking = question("imaging_safety.implant_or_metal", "Implant?")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        service,
        "build_radiology_case",
        lambda input_dir, model: (radiology_case, extraction, []),
    )
    monkeypatch.setattr(decision_llm, "OpenAIRequestDecision", FakeDecisionEngine)
    monkeypatch.setattr(cli, "ReferenceEngine", FakeReferenceEngine)
    monkeypatch.setattr(cli, "generic_missing_questions", lambda received_case: [initial])
    monkeypatch.setattr(
        cli,
        "recommendation_specific_questions",
        lambda received_case, received_decision: [safety, nonblocking],
    )
    output = tmp_path / "out"
    args = SimpleNamespace(
        input=str(tmp_path),
        output=str(output),
        answers=None,
        reference=str(tmp_path),
        model="model",
    )

    cli.cmd_request_run(args)

    assert decision.decision_status == "safety_blocked"
    assert decision.clinician_call_required is True
    assert set(decision.clinician_call_reasons) == {
        "Clinical indication?",
        "Pacemaker?",
        "Implant?",
    }
    assert radiology_case.audit[-1]["event"] == "request_workflow_completed"
    assert {
        "radiology_case.json",
        "llm_extraction.json",
        "case.json",
        "reference_context.json",
        "missing_questions.json",
        "imaging_decision.json",
        "teleradiology_request.json",
        "answers.template.json",
    } <= {path.name for path in output.iterdir()}
    assert "Decision: safety_blocked" in capsys.readouterr().out


def test_request_run_applies_answer_file_and_nonblocking_material_guard(monkeypatch, tmp_path):
    from bulkinout.core import service
    from bulkinout.request import decision_llm

    case = ClinicalCase()
    radiology_case = RadiologyCase(clinical=case)
    decision = ImagingDecision(
        decision_status="selected",
        primary=ImagingRecommendation(modality="CT", exam_name="CT abdomen"),
        clinician_call_required=False,
        decision_ready_for_human_approval=True,
    )
    applied = []

    class FakeDecisionEngine:
        def __init__(self, model=None):
            pass

        def decide(self, case, questions, reference_context=None):
            return decision

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        service,
        "build_radiology_case",
        lambda input_dir, model: (radiology_case, LLMExtraction(), []),
    )
    monkeypatch.setattr(decision_llm, "OpenAIRequestDecision", FakeDecisionEngine)
    monkeypatch.setattr(cli, "load_answers", lambda path: "loaded")
    monkeypatch.setattr(
        cli,
        "apply_answers",
        lambda received_case, answers, filename: applied.append((answers, filename)) or received_case,
    )
    monkeypatch.setattr(cli, "generic_missing_questions", lambda received_case: [])
    monkeypatch.setattr(
        cli,
        "recommendation_specific_questions",
        lambda received_case, received_decision: [question("labs.egfr", "eGFR?")],
    )
    monkeypatch.setattr(cli.ReferenceEngine, "build_context", lambda self, received_case: {})
    args = SimpleNamespace(
        input=str(tmp_path),
        output=str(tmp_path / "out"),
        answers=str(tmp_path / "answers.json"),
        reference=str(tmp_path),
        model="model",
    )

    cli.cmd_request_run(args)

    assert applied == [("loaded", "answers.json")]
    assert decision.decision_status == "insufficient_information"


def test_request_golden_handles_empty_success_and_failure(monkeypatch, tmp_path, capsys):
    args = SimpleNamespace(reference=str(tmp_path), cases=str(tmp_path))
    monkeypatch.setattr(cli, "discover_golden_cases", lambda path: [])
    with pytest.raises(SystemExit, match="No golden cases found"):
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


def test_main_dispatches_report_command(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["bulkinout", "report"])

    cli.main()

    assert "BULKINOUT Report is reserved" in capsys.readouterr().out
