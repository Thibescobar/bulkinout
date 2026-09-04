from pathlib import Path

import pytest

from bulkinout.core.models import (
    ClinicalCase,
    ClinicalField,
    DiscriminatingQuestion,
    FieldStatus,
    ImagingDecision,
    ImagingRecommendation,
    LLMExtraction,
    MissingQuestion,
    RadiologyCase,
)
from bulkinout.core.service import CoreResult
from bulkinout.request import service


def observed(value):
    return ClinicalField(value=value, status=FieldStatus.observed, confidence=1.0)


def write_scenario(
    reference_dir: Path,
    *,
    required_to_choose: bool,
    blocking: bool = False,
    field: str = "current_problem.required_fact",
) -> None:
    reference_dir.mkdir()
    (reference_dir / "question_guard.yaml").write_text(
        f"""\
id: question_guard
title: Question guard
entry:
  any:
    - {{field: current_problem.indication, contains: guard}}
questions:
  - id: required_fact
    field: {field}
    question: "Quel est le fait requis ?"
    priority: 1
    material: true
    required_to_choose: {str(required_to_choose).lower()}
    blocking: {str(blocking).lower()}
    reason: "Changes the examination choice."
candidates: []
""",
        encoding="utf-8",
    )


def run_guarded_workflow(
    monkeypatch,
    tmp_path,
    llm_questions,
    *,
    required=True,
    blocking=False,
    field="current_problem.required_fact",
):
    case = ClinicalCase(
        current_problem={
            "indication": observed("guard scenario"),
            "symptoms": observed(["synthetic symptom"]),
        }
    )
    radiology_case = RadiologyCase(clinical=case)
    monkeypatch.setattr(
        service,
        "build_radiology_case",
        lambda input_dir, model, extractor: CoreResult(radiology_case, LLMExtraction(), []),
    )
    monkeypatch.setattr(service, "generic_missing_questions", lambda received_case: [])
    monkeypatch.setattr(
        service,
        "recommendation_specific_questions",
        lambda received_case, received_decision: [],
    )

    class DecisionEngine:
        def decide(self, received_case, missing_questions, reference_context=None):
            return ImagingDecision(
                decision_status="selected",
                discriminating_questions=llm_questions,
                primary=ImagingRecommendation(
                    recommended=True,
                    modality="US",
                    exam_name="Échographie ciblée",
                ),
                clinician_call_required=False,
                decision_ready_for_human_approval=True,
            )

    reference_dir = tmp_path / "reference"
    write_scenario(
        reference_dir,
        required_to_choose=required,
        blocking=blocking,
        field=field,
    )
    return service.run_request(
        tmp_path,
        reference_dir=reference_dir,
        decision_engine=DecisionEngine(),
    )


@pytest.mark.parametrize("llm_output", ["empty", "weakened_duplicate"])
def test_required_reference_question_cannot_be_omitted_or_weakened(
    monkeypatch, tmp_path, llm_output
):
    llm_questions = []
    if llm_output == "weakened_duplicate":
        llm_questions = [
            DiscriminatingQuestion(
                question_id="llm_optional",
                field="current_problem.required_fact",
                question="Question optionnelle inventée",
                why_it_matters="The model says this is optional.",
                priority=9,
                possible_decision_impact="None",
                required_to_choose=False,
            )
        ]

    result = run_guarded_workflow(monkeypatch, tmp_path, llm_questions)

    required = [
        question
        for question in result.missing_questions
        if question.field == "current_problem.required_fact"
    ]
    assert len(required) == 1
    assert required[0].question_id == "required_fact"
    assert required[0].required_to_choose is True
    assert result.imaging_decision.decision_status == "insufficient_information"
    assert result.imaging_decision.primary.recommended is False
    assert result.imaging_decision.decision_ready_for_human_approval is False


def test_material_reference_question_is_not_implicitly_required(monkeypatch, tmp_path):
    result = run_guarded_workflow(monkeypatch, tmp_path, [], required=False)

    assert result.missing_questions == []
    assert result.imaging_decision.decision_status == "selected"
    assert result.imaging_decision.primary.recommended is True
    assert result.imaging_decision.decision_ready_for_human_approval is True


def test_blocking_reference_question_preserves_strongest_duplicate_requirement(
    monkeypatch, tmp_path
):
    llm_question = DiscriminatingQuestion(
        question_id="llm_required",
        field="imaging_safety.pregnancy",
        question="Question du modèle",
        why_it_matters="The model also considers it required.",
        priority=1,
        possible_decision_impact="Changes the examination",
        required_to_choose=True,
    )

    result = run_guarded_workflow(
        monkeypatch,
        tmp_path,
        [llm_question],
        blocking=True,
        field="imaging_safety.pregnancy",
    )

    assert len(result.missing_questions) == 1
    question = result.missing_questions[0]
    assert question.blocking is True
    assert question.required_to_choose is True
    assert question.importance == "critical"
    assert result.imaging_decision.decision_status == "safety_blocked"
    assert result.imaging_decision.primary.recommended is False


def test_merge_questions_deduplicates_by_field_and_keeps_strongest_flags():
    optional = MissingQuestion(
        question_id="optional",
        field="imaging_safety.pregnancy",
        question="Question optionnelle",
        importance="medium",
        reason="Optional context",
        material=True,
    )
    blocking = MissingQuestion(
        question_id="blocking",
        field="imaging_safety.pregnancy",
        question="Une grossesse est-elle possible ou en cours ?",
        importance="critical",
        reason="Safety condition",
        blocking=True,
    )

    merged = service._merge_questions([optional], [blocking])

    assert len(merged) == 1
    assert merged[0].question_id == "blocking"
    assert merged[0].blocking is True
    assert merged[0].required_to_choose is True
    assert merged[0].importance == "critical"
