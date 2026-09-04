from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from ..errors import InputError
from .extraction import OpenAICoreExtractor, extraction_to_case
from .ingestion import collect_files
from .interfaces import CoreExtractor
from .models import ArtifactRef, LLMExtraction, RadiologyCase, WorkflowState


class CoreResult(NamedTuple):
    """Typed Core output that remains tuple-unpackable for compatibility."""

    radiology_case: RadiologyCase
    extraction: LLMExtraction
    source_paths: list[Path]


def build_radiology_case(
    input_dir: Path,
    model: str | None = None,
    *,
    extractor: CoreExtractor | None = None,
) -> CoreResult:
    """Build a radiology case with the default or an injected extractor."""

    paths = collect_files(input_dir)
    if not paths:
        raise InputError(f"No supported document found in {input_dir}")

    selected_extractor = extractor or OpenAICoreExtractor(model=model)
    extraction = selected_extractor.extract(paths)
    clinical = extraction_to_case(extraction)
    clinical.metadata["extractor"] = selected_extractor.name
    clinical.metadata["documents_processed"] = len(paths)
    clinical.metadata["model"] = selected_extractor.model

    case = RadiologyCase(
        workflow=WorkflowState(phase="pre_exam", status="active"),
        clinical=clinical,
        artifacts=[
            ArtifactRef(
                artifact_id=f"input:{p.name}",
                artifact_type=p.suffix.lower().lstrip(".") or "file",
                source=p.name,
            )
            for p in paths
        ],
        audit=[{"event": "core_structuring_completed", "model": selected_extractor.model}],
    )
    return CoreResult(case, extraction, paths)
