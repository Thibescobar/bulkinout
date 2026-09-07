from typing import Any

from openai.lib._pydantic import to_strict_json_schema

from bulkinout.core.models import ImagingDecision, LLMExtraction


def _assert_all_objects_are_strict(value: Any) -> None:
    if isinstance(value, dict):
        if value.get("type") == "object":
            assert value.get("additionalProperties") is False
            properties = value.get("properties", {})
            assert set(value.get("required", [])) == set(properties)
        for child in value.values():
            _assert_all_objects_are_strict(child)
    elif isinstance(value, list):
        for child in value:
            _assert_all_objects_are_strict(child)


def test_openai_extraction_schema_contains_only_closed_required_objects():
    schema = to_strict_json_schema(LLMExtraction)

    _assert_all_objects_are_strict(schema)
    fact_properties = schema["$defs"]["LLMFact"]["properties"]
    assert "temporal_status" in fact_properties
    assert "observed_at" in fact_properties


def test_openai_decision_schema_contains_only_closed_required_objects():
    _assert_all_objects_are_strict(to_strict_json_schema(ImagingDecision))
