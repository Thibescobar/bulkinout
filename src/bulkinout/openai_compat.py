"""Model-aware inference settings for the built-in OpenAI adapters."""

from __future__ import annotations

import warnings
from dataclasses import dataclass

from .types import JsonObject

_TEMPERATURE_MODEL_FAMILIES = ("gpt-4.1", "gpt-4o")


class ColdModeWarning(UserWarning):
    """Report that cold mode could not be applied to one model stage."""


@dataclass(frozen=True, slots=True)
class OpenAIInferenceSettings:
    """Resolved API parameters and auditable sampling metadata."""

    reasoning_effort: str | None
    temperature_requested: float | None
    temperature_applied: float | None
    temperature_status: str

    def request_parameters(self) -> dict[str, object]:
        parameters: dict[str, object] = {}
        if self.reasoning_effort is not None:
            parameters["reasoning"] = {"effort": self.reasoning_effort}
        if self.temperature_applied is not None:
            parameters["temperature"] = self.temperature_applied
        return parameters

    def manifest_parameters(self) -> JsonObject:
        return {
            "reasoning_effort": self.reasoning_effort,
            "temperature_requested": self.temperature_requested,
            "temperature_applied": self.temperature_applied,
            "temperature_status": self.temperature_status,
        }


def _supports_temperature(model: str) -> bool:
    return any(
        model == family or model.startswith(f"{family}-") for family in _TEMPERATURE_MODEL_FAMILIES
    )


def resolve_openai_inference_settings(
    model: str,
    *,
    cold: bool,
    component: str,
) -> OpenAIInferenceSettings:
    """Resolve compatible parameters without weakening reasoning implicitly."""

    temperature_requested = 0.0 if cold else None
    if _supports_temperature(model):
        return OpenAIInferenceSettings(
            reasoning_effort=None,
            temperature_requested=temperature_requested,
            temperature_applied=temperature_requested,
            temperature_status="applied" if cold else "not_requested",
        )

    if cold:
        warnings.warn(
            f"--cold ignored for {component} model '{model}': temperature is not compatible "
            "with this model configuration; provider-controlled sampling will be used.",
            ColdModeWarning,
            stacklevel=2,
        )
    return OpenAIInferenceSettings(
        reasoning_effort="medium",
        temperature_requested=temperature_requested,
        temperature_applied=None,
        temperature_status="unsupported_by_model_configuration" if cold else "not_requested",
    )
