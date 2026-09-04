from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple

from ..errors import ConfigurationError, InputError
from .extraction import OpenAICoreExtractor, extraction_to_case
from .ingestion import collect_files
from .models import ArtifactRef, LLMExtraction, RadiologyCase, WorkflowState


class CoreResult(NamedTuple):
    """Typed Core output that remains tuple-unpackable for compatibility."""

    radiology_case: RadiologyCase
    extraction: LLMExtraction
    source_paths: list[Path]


def build_radiology_case(input_dir: Path, model: str | None = None) -> CoreResult:
    paths = collect_files(input_dir)
    if not paths:
        raise InputError(f"No supported document found in {input_dir}")
    if not os.getenv("OPENAI_API_KEY"):
        raise ConfigurationError("OPENAI_API_KEY is missing.")

    extractor = OpenAICoreExtractor(model=model)
    extraction = extractor.extract(paths)
    clinical = extraction_to_case(extraction)
    clinical.metadata["documents_processed"] = len(paths)
    clinical.metadata["model"] = extractor.model

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
        audit=[{"event": "core_structuring_completed", "model": extractor.model}],
    )
    return CoreResult(case, extraction, paths)
