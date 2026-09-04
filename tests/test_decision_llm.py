import json
from types import SimpleNamespace

import pytest

from bulkinout.core.models import ClinicalCase, ImagingDecision, ImagingRecommendation
from bulkinout.errors import ConfigurationError
from bulkinout.request import decision_llm


def decision_json():
    return ImagingDecision(
        decision_status="selected",
        primary=ImagingRecommendation(modality="CT", exam_name="CT abdomen"),
        clinician_call_required=False,
        decision_ready_for_human_approval=True,
    ).model_dump_json()


def test_extract_json_supports_output_text_chunks_and_empty_output():
    assert (
        decision_llm._extract_json(SimpleNamespace(output_text=decision_json())) == decision_json()
    )
    response = SimpleNamespace(
        output_text="",
        output=[SimpleNamespace(content=[SimpleNamespace(text="a"), SimpleNamespace(text="b")])],
    )
    assert decision_llm._extract_json(response) == "ab"
    assert decision_llm._extract_json(SimpleNamespace()) == ""


def test_schema_format_is_strict():
    result = decision_llm._schema_format(ImagingDecision)

    assert result["name"] == "ImagingDecision"
    assert result["strict"] is True


def test_decision_engine_requires_model(monkeypatch):
    monkeypatch.delenv("BULKINOUT_DECISION_MODEL", raising=False)
    monkeypatch.delenv("BULKINOUT_MODEL", raising=False)
    monkeypatch.setattr(decision_llm, "OpenAI", lambda: SimpleNamespace())

    with pytest.raises(ConfigurationError, match="No decision model configured"):
        decision_llm.OpenAIRequestDecision()


def test_decision_engine_prefers_specific_model_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("BULKINOUT_DECISION_MODEL", "decision-model")
    monkeypatch.setenv("BULKINOUT_MODEL", "shared-model")
    monkeypatch.setattr(decision_llm, "OpenAI", lambda: SimpleNamespace())

    assert decision_llm.OpenAIRequestDecision().model == "decision-model"
    assert decision_llm.OpenAIRequestDecision(model="explicit-model").model == "explicit-model"

    monkeypatch.delenv("BULKINOUT_DECISION_MODEL")
    assert decision_llm.OpenAIRequestDecision().model == "shared-model"


def test_decide_sends_case_questions_and_reference_context(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(output_text=decision_json())

    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    monkeypatch.setattr(decision_llm, "OpenAI", lambda: client)
    engine = decision_llm.OpenAIRequestDecision(model="test-model")

    result = engine.decide(
        ClinicalCase(),
        [{"field": "patient.age"}],
        reference_context={"matched_scenarios": [{"id": "example"}]},
    )

    payload = json.loads(calls[0]["input"][1]["content"][0]["text"])
    assert result.primary.exam_name == "CT abdomen"
    assert calls[0]["model"] == "test-model"
    assert payload["unresolved_questions"] == [{"field": "patient.age"}]
    assert payload["reference_context"]["matched_scenarios"][0]["id"] == "example"


def test_decide_defaults_missing_reference_context_to_empty(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    calls = []
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=lambda **kwargs: (
                calls.append(kwargs) or SimpleNamespace(output_text=decision_json())
            )
        )
    )
    monkeypatch.setattr(decision_llm, "OpenAI", lambda: client)

    decision_llm.OpenAIRequestDecision(model="test-model").decide(ClinicalCase(), [])

    payload = json.loads(calls[0]["input"][1]["content"][0]["text"])
    assert payload["reference_context"] == {}


def test_decision_engine_requires_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY is missing"):
        decision_llm.OpenAIRequestDecision(model="test-model")
