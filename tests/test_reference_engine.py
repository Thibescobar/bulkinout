from pathlib import Path

import pytest

from bulkinout.core.models import (
    CodedConcept,
    ClinicalCase,
    ClinicalField,
    FieldStatus,
    TemporalStatus,
)
from bulkinout.request.reference_engine import ReferenceEngine


def observed(v):
    return ClinicalField(
        value=v,
        status=FieldStatus.observed,
        confidence=1.0,
        temporal_status=TemporalStatus.current,
    )


def reference_dir():
    return Path(__file__).parents[1] / "reference" / "scenarios"


def test_matches_renal_colic():
    case = ClinicalCase()
    case.current_problem["location"] = observed("douleur du flanc droit")
    engine = ReferenceEngine(reference_dir())
    matches = engine.match(case)
    assert matches
    assert matches[0].scenario_id == "renal_colic"


@pytest.mark.parametrize(
    "diagnosis",
    ["Suspicion d'EP aiguë", "Suspected EP"],
)
def test_pulmonary_embolism_acronym_matches_as_a_token(diagnosis):
    case = ClinicalCase()
    case.current_problem["suspected_diagnosis"] = observed(diagnosis)

    matches = ReferenceEngine(reference_dir()).match(case)

    assert "suspected_pulmonary_embolism" in {match.scenario_id for match in matches}


@pytest.mark.parametrize(
    "diagnosis",
    ["Sepsis d'origine pulmonaire", "Sepsis with shock"],
)
def test_pulmonary_embolism_acronym_does_not_match_inside_a_word(diagnosis):
    case = ClinicalCase()
    case.current_problem["suspected_diagnosis"] = observed(diagnosis)

    matches = ReferenceEngine(reference_dir()).match(case)

    assert "suspected_pulmonary_embolism" not in {match.scenario_id for match in matches}


@pytest.mark.parametrize(
    ("field_name", "value", "expected_scenario"),
    [
        ("current_problem.suspected_diagnosis", "AVC aigu", "acute_stroke"),
        ("current_problem.location", "pain in RLQ", "rlq_appendicitis"),
        ("current_problem.location", "pain in LLQ", "llq_diverticulitis"),
        ("current_problem.location", "pain in RUQ", "right_upper_quadrant_pain"),
    ],
)
def test_other_clinical_acronyms_match_as_tokens(field_name, value, expected_scenario):
    case = ClinicalCase()
    section_name, key = field_name.split(".", 1)
    getattr(case, section_name)[key] = observed(value)

    matches = ReferenceEngine(reference_dir()).match(case)

    assert expected_scenario in {match.scenario_id for match in matches}


@pytest.mark.parametrize(
    ("field_name", "term", "expanded_term", "scenario_id"),
    [
        ("current_problem.suspected_diagnosis", "AVC", "stroke", "acute_stroke"),
        ("current_problem.location", "RLQ", "right lower quadrant", "rlq_appendicitis"),
        ("current_problem.location", "LLQ", "left lower quadrant", "llq_diverticulitis"),
        (
            "current_problem.location",
            "RUQ",
            "right upper quadrant",
            "right_upper_quadrant_pain",
        ),
    ],
)
def test_acronym_and_expanded_term_keep_the_same_scenario_score(
    field_name, term, expanded_term, scenario_id
):
    def score_for(value):
        case = ClinicalCase()
        section_name, key = field_name.split(".", 1)
        getattr(case, section_name)[key] = observed(value)
        return next(
            match.score
            for match in ReferenceEngine(reference_dir()).match(case)
            if match.scenario_id == scenario_id
        )

    assert score_for(term) == score_for(expanded_term)


def test_pregnancy_question_is_material_when_unknown():
    case = ClinicalCase()
    case.current_problem["location"] = observed("flanc gauche")
    engine = ReferenceEngine(reference_dir())
    match = engine.match(case)[0]
    qs = engine.unresolved_material_questions(case, match.scenario)
    assert any(q["field"] == "imaging_safety.pregnancy" for q in qs)


def test_reference_pregnancy_question_is_skipped_when_not_relevant():
    case = ClinicalCase()
    case.patient["sex"] = observed("male")
    case.current_problem["location"] = observed("right lower quadrant")
    engine = ReferenceEngine(reference_dir())
    scenario = next(
        match.scenario for match in engine.match(case) if match.scenario_id == "rlq_appendicitis"
    )

    questions = engine.unresolved_material_questions(case, scenario)

    assert all(q["field"] != "imaging_safety.pregnancy" for q in questions)


def test_renal_colic_pregnancy_candidate_rule():
    case = ClinicalCase()
    case.current_problem["location"] = observed("flanc droit")
    case.imaging_safety["pregnancy"] = observed(True)
    engine = ReferenceEngine(reference_dir())
    ctx = engine.build_context(case)
    assert ctx["matched_scenarios"][0]["id"] == "renal_colic"
    candidates = ctx["matched_scenarios"][0]["candidate_exams"]
    assert any(c["id"] == "renal_ultrasound" for c in candidates)


@pytest.mark.parametrize(
    ("facts", "expected_scenario"),
    [
        ({"current_problem.indication": "acute abdominal pain"}, "acute_abdominal_pain"),
        (
            {"current_problem.suspected_diagnosis": "acute aortic syndrome"},
            "acute_aortic_syndrome",
        ),
        (
            {"current_problem.location": "hip", "history.trauma": "recent trauma"},
            "acute_hip_trauma",
        ),
        ({"current_problem.suspected_diagnosis": "acute pancreatitis"}, "acute_pancreatitis"),
        ({"current_problem.suspected_diagnosis": "acute stroke"}, "acute_stroke"),
        ({"current_problem.location": "neck pain"}, "cervical_spine_trauma"),
        ({"current_problem.indication": "mild head trauma"}, "head_trauma"),
        ({"current_problem.symptoms": ["jaundice"]}, "jaundice"),
        ({"current_problem.location": "left lower quadrant"}, "llq_diverticulitis"),
        ({"current_problem.indication": "acute low back pain"}, "low_back_pain"),
        ({"current_problem.indication": "first seizure"}, "new_onset_seizure"),
        ({"current_problem.location": "right flank"}, "renal_colic"),
        ({"current_problem.location": "right upper quadrant"}, "right_upper_quadrant_pain"),
        ({"current_problem.location": "right lower quadrant"}, "rlq_appendicitis"),
        (
            {"current_problem.suspected_diagnosis": "small bowel obstruction"},
            "small_bowel_obstruction",
        ),
        (
            {"current_problem.suspected_diagnosis": "pulmonary embolism"},
            "suspected_pulmonary_embolism",
        ),
        (
            {"current_problem.suspected_diagnosis": "spinal infection"},
            "suspected_spine_infection",
        ),
        ({"current_problem.symptoms": ["thunderclap headache"]}, "thunderclap_headache"),
    ],
)
def test_reference_matches_english_clinical_terms(facts, expected_scenario):
    case = ClinicalCase()
    for field_name, value in facts.items():
        section_name, key = field_name.split(".", 1)
        getattr(case, section_name)[key] = observed(value)

    matches = ReferenceEngine(reference_dir()).match(case)

    assert expected_scenario in {match.scenario_id for match in matches}


def test_reference_can_match_concepts_and_filter_candidates_by_concept(tmp_path):
    (tmp_path / "coded.yaml").write_text(
        """
id: coded_scenario
title: Coded scenario
entry:
  any:
    - field: current_problem.suspected_diagnosis
      concept_is:
        system: urn:bulkinout:test
        code: finding-a
candidates:
  - id: coded_candidate
    exam_name: Coded candidate
    when:
      any:
        - field: current_problem.suspected_diagnosis
          concept_in:
            - system: urn:bulkinout:test
              code: finding-a
""",
        encoding="utf-8",
    )
    case = ClinicalCase()
    case.current_problem["suspected_diagnosis"] = ClinicalField(
        value="Unmapped wording remains available",
        status=FieldStatus.observed,
        coded_concepts=[
            CodedConcept(
                system="urn:bulkinout:test",
                code="finding-a",
                display="Finding A",
                original_text="source wording",
            )
        ],
        temporal_status=TemporalStatus.current,
    )

    context = ReferenceEngine(tmp_path).build_context(case)

    assert context["matched_scenarios"][0]["id"] == "coded_scenario"
    assert context["matched_scenarios"][0]["candidate_exams"][0]["id"] == "coded_candidate"


def test_resolved_current_problem_does_not_enter_an_active_scenario():
    case = ClinicalCase(
        current_problem={
            "suspected_diagnosis": ClinicalField(
                value="pulmonary embolism",
                status=FieldStatus.observed,
                temporal_status=TemporalStatus.resolved,
                observed_at="2024-03-10",
            )
        }
    )

    matches = ReferenceEngine(reference_dir()).match(case)

    assert "suspected_pulmonary_embolism" not in {match.scenario_id for match in matches}
