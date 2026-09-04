from bulkinout.core.models import RadiologyCase


def test_radiology_case_defaults_to_pre_exam():
    case = RadiologyCase()
    assert case.workflow.phase == "pre_exam"
    assert case.ai_results == []
    assert case.final_report == {}
