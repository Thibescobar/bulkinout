from __future__ import annotations

from pathlib import Path

from .reference_engine import ReferenceEngine
from .types import CatalogEntry


def build_catalog(reference_dir: Path | None = None) -> list[CatalogEntry]:
    """Build lightweight catalog metadata from validated scenario mappings."""

    out: list[CatalogEntry] = []
    for data in ReferenceEngine(reference_dir).scenarios:
        out.append(
            {
                "id": data.get("id"),
                "version": data.get("version"),
                "title": data.get("title"),
                "status": data.get("status"),
                "source_file": data["_source_file"],
                "candidate_count": len(data.get("candidates", [])),
                "question_count": len(data.get("questions", [])),
                "source_count": len(data.get("sources", [])),
            }
        )
    return out
