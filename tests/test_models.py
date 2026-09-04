from bulkinout.core.models import ImagingDecision, ImagingRecommendation


def test_decision_model():
    d = ImagingDecision(
        decision_status="selected",
        primary=ImagingRecommendation(
            modality="CT",
            exam_name="TDM abdomino-pelvienne",
            contrast="conditional",
            urgency="urgent",
            confidence=0.8,
        ),
        clinician_call_required=False,
        decision_ready_for_human_approval=True,
    )
    assert d.primary.modality == "CT"
    assert d.primary.confidence == 0.8
