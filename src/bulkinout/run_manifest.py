"""Small, content-free fingerprints that make a Request run reproducible."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, Field

from .core.models import ImagingDecision, LLMExtraction
from .fingerprints import sha256_python_tree, sha256_text
from .request.types import DecisionEngineName, DecisionMode, ReferenceContext, ReferenceScenario
from .types import JsonObject

UNREPORTED = "unreported"


class InputFingerprint(BaseModel):
    filename: str
    sha256: str


class ComponentFingerprint(BaseModel):
    provider: str
    component: str
    model: str
    prompt_sha256: str
    schema_sha256: str
    inference_parameters: JsonObject = Field(default_factory=dict)


class ReferenceScenarioFingerprint(BaseModel):
    scenario_id: str
    version: str
    sha256: str


class ReferenceFingerprint(BaseModel):
    revision: str
    matched_scenarios: list[ReferenceScenarioFingerprint]


class TerminologyProviderFingerprint(BaseModel):
    name: str
    version: str
    content_sha256: str


class TerminologyFingerprint(BaseModel):
    providers: list[TerminologyProviderFingerprint]


class DecisionEngineFingerprint(BaseModel):
    engine: DecisionEngineName
    fingerprint: ComponentFingerprint


class RunManifest(BaseModel):
    schema_version: int = 5
    package_version: str
    code_sha256: str
    inputs: list[InputFingerprint]
    core: ComponentFingerprint
    request: ComponentFingerprint
    decision_mode: DecisionMode = "llm"
    active_decision_engine: DecisionEngineName = "llm"
    decision_engines: list[DecisionEngineFingerprint] = Field(default_factory=list)
    terminology: TerminologyFingerprint
    reference: ReferenceFingerprint


def _schema_sha256(model: type[BaseModel]) -> str:
    canonical = json.dumps(
        model.model_json_schema(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256_text(canonical)


def _reported(component: object, attribute: str, fallback: str | None = None) -> str:
    value = (
        component.get(attribute, fallback)
        if isinstance(component, Mapping)
        else getattr(component, attribute, fallback)
    )
    return value if isinstance(value, str) and value else UNREPORTED


def _reported_inference_parameters(component: object) -> JsonObject:
    value = (
        component.get("inference_parameters", {})
        if isinstance(component, Mapping)
        else getattr(component, "inference_parameters", {})
    )
    return value.copy() if isinstance(value, dict) else {}


def _component_fingerprint(
    component: object,
    schema: type[BaseModel],
    *,
    model_fallback: str | None = None,
) -> ComponentFingerprint:
    return ComponentFingerprint(
        provider=_reported(component, "provider"),
        component=_reported(component, "name"),
        model=_reported(component, "model", model_fallback),
        prompt_sha256=_reported(component, "prompt_sha256"),
        schema_sha256=_schema_sha256(schema),
        inference_parameters=_reported_inference_parameters(component),
    )


def _input_fingerprints(paths: list[Path]) -> list[InputFingerprint]:
    def file_sha256(path: Path) -> str:
        try:
            with path.open("rb") as stream:
                return hashlib.file_digest(stream, "sha256").hexdigest()
        except OSError:
            return UNREPORTED

    return sorted(
        (InputFingerprint(filename=path.name, sha256=file_sha256(path)) for path in paths),
        key=lambda item: (item.filename, item.sha256),
    )


def _reference_fingerprint(
    revision: str,
    scenarios: list[ReferenceScenario],
    context: ReferenceContext,
) -> ReferenceFingerprint:
    scenarios_by_id = {scenario["id"]: scenario for scenario in scenarios}
    matched: list[ReferenceScenarioFingerprint] = []
    for item in context["matched_scenarios"]:
        scenario = scenarios_by_id[item["id"]]
        matched.append(
            ReferenceScenarioFingerprint(
                scenario_id=scenario["id"],
                version=str(scenario.get("version") or UNREPORTED),
                sha256=scenario["_source_sha256"],
            )
        )
    return ReferenceFingerprint(
        revision=revision,
        matched_scenarios=sorted(matched, key=lambda item: item.scenario_id),
    )


def _terminology_fingerprint(providers: Sequence[object]) -> TerminologyFingerprint:
    return TerminologyFingerprint(
        providers=[
            TerminologyProviderFingerprint(
                name=_reported(provider, "name"),
                version=_reported(provider, "version"),
                content_sha256=_reported(provider, "content_sha256"),
            )
            for provider in providers
        ]
    )


def build_run_manifest(
    *,
    package_version: str,
    source_paths: list[Path],
    core_component: object,
    core_model: str | None,
    request_component: object,
    decision_mode: DecisionMode = "llm",
    request_components: Sequence[tuple[DecisionEngineName, object]] | None = None,
    terminology_providers: Sequence[object],
    reference_revision: str,
    reference_scenarios: list[ReferenceScenario],
    reference_context: ReferenceContext,
) -> RunManifest:
    """Build deterministic metadata for the exact inputs and components used."""

    active_engine: DecisionEngineName = (
        "deterministic" if decision_mode == "deterministic" else "llm"
    )
    components = request_components or [(active_engine, request_component)]
    return RunManifest(
        package_version=package_version,
        code_sha256=sha256_python_tree(Path(__file__).parent),
        inputs=_input_fingerprints(source_paths),
        core=_component_fingerprint(
            core_component,
            LLMExtraction,
            model_fallback=core_model,
        ),
        request=_component_fingerprint(request_component, ImagingDecision),
        decision_mode=decision_mode,
        active_decision_engine=active_engine,
        decision_engines=[
            DecisionEngineFingerprint(
                engine=engine,
                fingerprint=_component_fingerprint(component, ImagingDecision),
            )
            for engine, component in components
        ],
        terminology=_terminology_fingerprint(terminology_providers),
        reference=_reference_fingerprint(
            reference_revision,
            reference_scenarios,
            reference_context,
        ),
    )
