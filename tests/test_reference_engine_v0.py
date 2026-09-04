from pathlib import Path
from bulkinout.core.models import ClinicalCase, ClinicalField, FieldStatus
from bulkinout.request.reference_engine import ReferenceEngine

ROOT = Path(__file__).parents[1]

def observed(value):
    return ClinicalField(value=value, status=FieldStatus.observed, confidence=1.0)

def test_candidate_when_filters_renal_colic_pregnancy():
    case = ClinicalCase()
    case.current_problem["location"] = observed("flanc droit")
    case.imaging_safety["pregnancy"] = observed(True)
    ctx = ReferenceEngine(ROOT / "reference" / "scenarios").build_context(case, max_scenarios=10)
    renal = next(x for x in ctx["matched_scenarios"] if x["id"] == "renal_colic")
    ids = {c["id"] for c in renal["candidate_exams"]}
    assert "renal_ultrasound" in ids
    assert "ct_noncontrast" not in ids


def test_candidate_when_filters_renal_colic_nonpregnant():
    case = ClinicalCase()
    case.current_problem["location"] = observed("flanc droit")
    case.imaging_safety["pregnancy"] = observed(False)
    ctx = ReferenceEngine(ROOT / "reference" / "scenarios").build_context(case, max_scenarios=10)
    renal = next(x for x in ctx["matched_scenarios"] if x["id"] == "renal_colic")
    ids = {c["id"] for c in renal["candidate_exams"]}
    assert "ct_noncontrast" in ids
    assert "renal_ultrasound" not in ids
