from bulkinout.core.models import (
    ClinicalCase,
    ImagingDecision,
    ImagingRecommendation,
    LLMExtraction,
    MissingQuestion,
    RadiologyCase,
)
from bulkinout.core.service import CoreResult
from bulkinout.request import service


def question(field, text, *, blocking=False, importance="high"):
    return MissingQuestion(
        field=field,
        question=text,
        importance=importance,
        reason="Required for the test",
        blocking=blocking,
    )


def configure_workflow(monkeypatch, case, decision, initial, specific):
    radiology_case = RadiologyCase(clinical=case)
    extraction = LLMExtraction()

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
            assert reference_context == {"matched_scenarios": []}
            return decision

    monkeypatch.setattr(
        service,
        "build_radiology_case",
        lambda input_dir, model: CoreResult(radiology_case, extraction, []),
    )
    monkeypatch.setattr(service, "ReferenceEngine", FakeReferenceEngine)
    monkeypatch.setattr(service, "OpenAIRequestDecision", FakeDecisionEngine)
    monkeypatch.setattr(service, "generic_missing_questions", lambda received_case: initial)
    monkeypatch.setattr(
        service,
        "recommendation_specific_questions",
        lambda received_case, received_decision: specific,
    )
    return radiology_case


def test_run_request_applies_safety_guards_and_builds_result(monkeypatch, tmp_path):
    case = ClinicalCase()
    decision = ImagingDecision(
        decision_status="selected",
        primary=ImagingRecommendation(modality="MRI", exam_name="MRI brain"),
        clinician_call_required=False,
        decision_ready_for_human_approval=True,
    )
    initial = question(
        "current_problem.indication",
        "Clinical indication?",
        blocking=True,
        importance="critical",
    )
    safety = question("imaging_safety.pacemaker", "Pacemaker?", blocking=True)
    nonblocking = question("imaging_safety.implant_or_metal", "Implant?")
    radiology_case = configure_workflow(
        monkeypatch, case, decision, [initial], [safety, nonblocking]
    )

    result = service.run_request(tmp_path, reference_dir=tmp_path, model="model")

    assert result.imaging_decision.decision_status == "safety_blocked"
    assert result.imaging_decision.clinician_call_required is True
    assert set(result.imaging_decision.clinician_call_reasons) == {
        "Clinical indication?",
        "Pacemaker?",
        "Implant?",
    }
    assert result.teleradiology_request.status == "blocked"
    assert radiology_case.referral["reference_context"] == {"matched_scenarios": []}
    assert radiology_case.audit[-1]["event"] == "request_workflow_completed"


def test_run_request_applies_answers_and_nonblocking_material_guard(monkeypatch, tmp_path):
    case = ClinicalCase()
    decision = ImagingDecision(
        decision_status="selected",
        primary=ImagingRecommendation(modality="CT", exam_name="CT abdomen"),
        clinician_call_required=False,
        decision_ready_for_human_approval=True,
    )
    configure_workflow(
        monkeypatch,
        case,
        decision,
        [],
        [question("labs.egfr_ml_min_1_73m2", "eGFR?")],
    )
    applied = []
    monkeypatch.setattr(service, "load_answers", lambda path: "loaded")
    monkeypatch.setattr(
        service,
        "apply_answers",
        lambda received_case, answers, filename: (
            applied.append((answers, filename)) or received_case
        ),
    )

    result = service.run_request(
        tmp_path,
        reference_dir=tmp_path,
        model="model",
        answers_path=tmp_path / "answers.json",
    )

    assert applied == [("loaded", "answers.json")]
    assert result.imaging_decision.decision_status == "insufficient_information"


def test_question_guards_leave_decision_unchanged_without_material_questions():
    decision = ImagingDecision(
        decision_status="selected",
        primary=ImagingRecommendation(modality="US"),
        clinician_call_required=False,
        decision_ready_for_human_approval=True,
    )

    service._apply_question_guards(decision, [], [])

    assert decision.decision_status == "selected"
    assert decision.decision_ready_for_human_approval is True
