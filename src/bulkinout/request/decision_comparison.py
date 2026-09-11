"""Small pure comparison helper for shadow Request decisions."""

from __future__ import annotations

from ..core.models import ImagingDecision, MissingQuestion
from .types import DecisionComparison, DecisionComparisonItem


def compare_decisions(
    llm: ImagingDecision,
    llm_questions: list[MissingQuestion],
    deterministic: ImagingDecision,
    deterministic_questions: list[MissingQuestion],
) -> DecisionComparison:
    """Compare guarded decisions without choosing or merging their content."""

    def summary(
        decision: ImagingDecision, questions: list[MissingQuestion]
    ) -> DecisionComparisonItem:
        return DecisionComparisonItem(
            decision_status=decision.decision_status,
            primary_exam=decision.primary.exam_name,
            protocol=decision.primary.protocol,
            required_question_fields=sorted(
                {
                    question.field
                    for question in questions
                    if question.required_to_choose or question.blocking
                }
            ),
        )

    llm_summary = summary(llm, llm_questions)
    deterministic_summary = summary(deterministic, deterministic_questions)
    return DecisionComparison(
        active_engine="llm",
        llm=llm_summary,
        deterministic=deterministic_summary,
        same_status=llm_summary.decision_status == deterministic_summary.decision_status,
        same_primary_exam=llm_summary.primary_exam == deterministic_summary.primary_exam,
        same_protocol=llm_summary.protocol == deterministic_summary.protocol,
    )
