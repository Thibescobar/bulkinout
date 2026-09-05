"""Shared selection rules for clinician clarification surfaces."""

from __future__ import annotations

from ..core.models import MissingQuestion

_IMPORTANCE_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def required_clarification_questions(
    questions: list[MissingQuestion],
) -> list[MissingQuestion]:
    """Return required or blocking questions in stable clinical priority order."""

    return sorted(
        (question for question in questions if question.required_to_choose or question.blocking),
        key=lambda question: (_IMPORTANCE_ORDER[question.importance], question.field),
    )
