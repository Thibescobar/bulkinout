"""Interfaces for terminology providers."""

from __future__ import annotations

from typing import Protocol

from ...types import JsonValue
from ..models import CodedConcept


class TerminologyProvider(Protocol):
    """Resolve selected clinical values without owning the source value."""

    name: str
    version: str
    content_sha256: str

    def concepts_for(self, field_path: str, value: JsonValue) -> list[CodedConcept]:
        """Return reliable annotations, or an empty list when no mapping is safe."""
