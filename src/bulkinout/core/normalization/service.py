"""Apply terminology annotations while preserving clinical facts and provenance."""

from __future__ import annotations

from typing import cast

from ...types import JsonObject, JsonValue
from ..models import ClinicalCase, ClinicalField, FieldStatus
from .interfaces import TerminologyProvider
from .providers import UCUMUnitProvider

_SECTIONS = (
    "patient",
    "current_problem",
    "history",
    "medications",
    "allergies",
    "labs",
    "imaging_safety",
)


class TerminologyNormalizer:
    """Annotate known facts using independent, deterministic providers."""

    def __init__(self, providers: list[TerminologyProvider] | None = None) -> None:
        self.providers = list(providers or [])

    def normalize_field(self, field_path: str, clinical_field: ClinicalField) -> None:
        if clinical_field.status in {FieldStatus.unknown, FieldStatus.conflicting}:
            return
        existing = {
            (concept.system, concept.code, concept.version, concept.original_text)
            for concept in clinical_field.coded_concepts
        }
        for provider in self.providers:
            for concept in provider.concepts_for(field_path, clinical_field.value):
                identity = (concept.system, concept.code, concept.version, concept.original_text)
                if identity not in existing:
                    clinical_field.coded_concepts.append(concept)
                    existing.add(identity)

    def normalize_case(self, case: ClinicalCase) -> ClinicalCase:
        for section_name in _SECTIONS:
            section = getattr(case, section_name)
            for key, clinical_field in section.items():
                self.normalize_field(f"{section_name}.{key}", clinical_field)
        for prior in case.prior_imaging:
            for key in ("modality", "region", "date", "result"):
                self.normalize_field(f"prior_imaging.{key}", getattr(prior, key))
        case.metadata["terminology"] = cast(
            JsonValue,
            {
                "providers": [
                    cast(
                        JsonObject,
                        {
                            "name": provider.name,
                            "version": provider.version,
                            "content_sha256": provider.content_sha256,
                        },
                    )
                    for provider in self.providers
                ]
            },
        )
        return case


def default_terminology_normalizer() -> TerminologyNormalizer:
    """Return the dependency-free default normalization pipeline."""

    return TerminologyNormalizer([UCUMUnitProvider()])
