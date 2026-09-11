"""Closed-world Request decisions derived only from the reference context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from ..core.models import ClinicalCase, ImagingDecision, ImagingRecommendation
from ..types import JsonObject
from .types import ReferenceCandidate, ReferenceContext


@dataclass(frozen=True, slots=True)
class _CandidateSelection:
    scenario_id: str
    candidate: ReferenceCandidate
    rule_id: str | None = None


class DeterministicRequestDecision:
    """Select explicit results and route unresolved candidate choices to review."""

    provider = "bulkinout"
    name = "bulkinout_request_deterministic_decision_v1"
    model = "not_applicable"
    prompt_sha256 = "not_applicable"
    inference_parameters: JsonObject = {"llm_calls": 0, "world": "closed"}

    def decide(
        self,
        case: ClinicalCase,
        missing_questions: list[JsonObject],
        reference_context: ReferenceContext | None = None,
    ) -> ImagingDecision:
        del case, missing_questions
        context = reference_context or {"matched_scenarios": []}
        if self._has_unresolved_required_question(context):
            return self._abstain("Le référentiel exige une information clinique supplémentaire.")

        preferred, no_imaging_rules = self._rule_results(context)
        if no_imaging_rules and not preferred:
            rule_ids = ", ".join(no_imaging_rules)
            return ImagingDecision(
                decision_status="no_imaging_recommended",
                primary=ImagingRecommendation(recommended=False),
                no_imaging_reason=(
                    "Le référentiel indique explicitement l'absence d'imagerie initiale "
                    f"via la ou les règles : {rule_ids}."
                ),
                clinician_call_required=False,
            )
        if len(preferred) == 1 and not no_imaging_rules:
            return self._select(preferred[0])
        if preferred or no_imaging_rules:
            return self._abstain("Plusieurs résultats de règles explicites restent incompatibles.")

        candidates = self._applicable_candidates(context)
        if not candidates:
            return self._abstain("Aucun candidat applicable n'est encodé dans le référentiel.")
        if (
            len(candidates) == 1
            and candidates[0].candidate.get("appropriateness") == "usually_appropriate"
        ):
            return self._select(candidates[0])
        return self._route_to_radiologist(candidates)

    @staticmethod
    def _has_unresolved_required_question(context: ReferenceContext) -> bool:
        return any(
            question.get("required_to_choose", False) or question.get("blocking", False)
            for scenario in context["matched_scenarios"]
            for question in scenario["unresolved_material_questions"]
        )

    @staticmethod
    def _applicable_candidates(context: ReferenceContext) -> list[_CandidateSelection]:
        return [
            _CandidateSelection(scenario["id"], candidate)
            for scenario in context["matched_scenarios"]
            for candidate in scenario["candidate_exams"]
        ]

    @staticmethod
    def _rule_results(
        context: ReferenceContext,
    ) -> tuple[list[_CandidateSelection], list[str]]:
        preferred: list[_CandidateSelection] = []
        no_imaging: list[str] = []
        for scenario in context["matched_scenarios"]:
            candidates = {candidate["id"]: candidate for candidate in scenario["candidate_exams"]}
            for triggered in scenario["rules_triggered"]:
                result = triggered["result"]
                candidate_id = result.get("preferred_candidate")
                if isinstance(candidate_id, str) and candidate_id in candidates:
                    preferred.append(
                        _CandidateSelection(
                            scenario["id"], candidates[candidate_id], triggered["rule_id"]
                        )
                    )
                if result.get("no_imaging_recommended") is True:
                    no_imaging.append(triggered["rule_id"])
        return preferred, no_imaging

    @staticmethod
    def _recommendation(
        selection: _CandidateSelection, *, recommended: bool
    ) -> ImagingRecommendation:
        candidate = selection.candidate
        raw_contrast = cast(dict[str, object], candidate).get("contrast", "unknown")
        contrast = (
            "yes" if raw_contrast is True else "no" if raw_contrast is False else raw_contrast
        )
        if contrast not in {"yes", "no", "conditional", "unknown"}:
            contrast = "unknown"
        contrast_value = cast(Literal["yes", "no", "conditional", "unknown"], contrast)
        rationale = candidate.get("rationale") or [
            "Option issue du référentiel clinique et soumise à la validation du radiologue."
        ]
        urgency = candidate.get("urgency", "unknown")
        if urgency not in {"emergent", "urgent", "routine", "unknown"}:
            urgency = "unknown"
        return ImagingRecommendation(
            recommended=recommended,
            modality=candidate.get("modality"),
            exam_name=candidate.get("exam_name"),
            protocol=candidate.get("protocol"),
            contrast=contrast_value,
            urgency=urgency,
            rationale=rationale,
            safety_considerations=candidate.get("safety_considerations", []),
        )

    @classmethod
    def _select(cls, selection: _CandidateSelection) -> ImagingDecision:
        return ImagingDecision(
            decision_status="selected",
            primary=cls._recommendation(selection, recommended=True),
            clinician_call_required=False,
        )

    @classmethod
    def _route_to_radiologist(cls, selections: list[_CandidateSelection]) -> ImagingDecision:
        recommendations = [
            cls._recommendation(selection, recommended=False) for selection in selections
        ]
        return ImagingDecision(
            decision_status="radiologist_selection_required",
            primary=recommendations[0],
            secondary=recommendations[1:],
            clinician_call_required=False,
            decision_ready_for_human_approval=True,
        )

    @staticmethod
    def _abstain(reason: str) -> ImagingDecision:
        return ImagingDecision(
            decision_status="insufficient_information",
            primary=ImagingRecommendation(recommended=False, missing_information=[reason]),
            clinician_call_required=True,
            clinician_call_reasons=[reason],
        )
