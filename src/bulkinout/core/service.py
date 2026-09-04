from __future__ import annotations

from pathlib import Path

from .ingestion import collect_files
from .extraction import OpenAICoreExtractor, extraction_to_case
from .models import RadiologyCase, WorkflowState, ArtifactRef

def build_radiology_case(input_dir: Path, model: str | None = None):
    paths = collect_files(input_dir)
    if not paths:
        raise ValueError(f"Aucun document supporté trouvé dans {input_dir}")

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
    return case, extraction, paths
