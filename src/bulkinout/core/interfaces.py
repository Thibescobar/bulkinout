"""Provider-neutral contracts used by the Core application service."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import LLMExtraction


class CoreExtractor(Protocol):
    """Extract a validated clinical structure from source documents."""

    name: str
    model: str

    def extract(self, paths: list[Path]) -> LLMExtraction:
        """Return structured facts for the supplied document paths."""
        ...
