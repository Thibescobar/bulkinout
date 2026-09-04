from pathlib import Path

import pytest

from bulkinout.core.models import ClinicalCase, ClinicalField, FieldStatus
from bulkinout.request.reference_engine import ReferenceEngine


def observed(v):
    return ClinicalField(value=v, status=FieldStatus.observed, confidence=1.0)


def reference_dir():
    return Path(__file__).parents[1] / "reference" / "scenarios"


def test_matches_renal_colic():
    case = ClinicalCase()
    case.current_problem["location"] = observed("douleur du flanc droit")
    engine = ReferenceEngine(reference_dir())
    matches = engine.match(case)
    assert matches
    assert matches[0].scenario_id == "renal_colic"


def test_pregnancy_question_is_material_when_unknown():
    case = ClinicalCase()
    case.current_problem["location"] = observed("flanc gauche")
    engine = ReferenceEngine(reference_dir())
    match = engine.match(case)[0]
    qs = engine.unresolved_material_questions(case, match.scenario)
    assert any(q["field"] == "imaging_safety.pregnancy" for q in qs)


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
