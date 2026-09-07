import pytest

from bulkinout.openai_compat import ColdModeWarning, resolve_openai_inference_settings


@pytest.mark.parametrize("model", ["gpt-4.1", "gpt-4.1-mini-2025-04-14", "gpt-4o-mini"])
def test_cold_mode_applies_to_supported_non_reasoning_models(model):
    settings = resolve_openai_inference_settings(model, cold=True, component="Core")

    assert settings.request_parameters() == {"temperature": 0.0}
    assert settings.manifest_parameters() == {
        "reasoning_effort": None,
        "temperature_requested": 0.0,
        "temperature_applied": 0.0,
        "temperature_status": "applied",
    }


def test_reasoning_model_keeps_medium_effort_when_cold_is_not_requested():
    settings = resolve_openai_inference_settings("gpt-5.6-terra", cold=False, component="Request")

    assert settings.request_parameters() == {"reasoning": {"effort": "medium"}}
    assert settings.temperature_status == "not_requested"


def test_incompatible_cold_mode_warns_and_does_not_weaken_reasoning():
    with pytest.warns(ColdModeWarning, match="--cold ignored for Request model 'gpt-5.6-terra'"):
        settings = resolve_openai_inference_settings(
            "gpt-5.6-terra", cold=True, component="Request"
        )

    assert settings.request_parameters() == {"reasoning": {"effort": "medium"}}
    assert settings.manifest_parameters() == {
        "reasoning_effort": "medium",
        "temperature_requested": 0.0,
        "temperature_applied": None,
        "temperature_status": "unsupported_by_model_configuration",
    }
