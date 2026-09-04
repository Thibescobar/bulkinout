from pathlib import Path

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
