"""Provider-neutral contracts used by the Request application service."""

from __future__ import annotations

from typing import Protocol

from ..core.models import ClinicalCase, ImagingDecision
from ..types import JsonObject
from .types import ReferenceContext


class RequestDecisionEngine(Protocol):
    """Produce a validated imaging proposal from a structured case."""

    def decide(
        self,
        case: ClinicalCase,
        missing_questions: list[JsonObject],
        reference_context: ReferenceContext | None = None,
    ) -> ImagingDecision:
        """Compare candidate examinations and return a typed proposal."""
        ...
