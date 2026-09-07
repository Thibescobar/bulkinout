from bulkinout.core.models import (
    FieldStatus,
    LLMFact,
    LLMSource,
    TemporalStatus,
)
from bulkinout.core.reconciliation import reconcile_facts


def fact(
    field: str,
    value: object,
    *,
    filename: str,
    temporal_status: str = "current",
    observed_at: str | None = None,
    status: str = "observed",
) -> LLMFact:
    return LLMFact(
        field=field,
        value=value,
        status=status,
        confidence=0.9,
        temporal_status=temporal_status,
        observed_at=observed_at,
        sources=[LLMSource(filename=filename, excerpt=str(value))],
    )


def test_compatible_fr_en_evidence_is_grouped_without_losing_sources():
    case = reconcile_facts(
        [
            fact(
                "current_problem.suspected_diagnosis",
                "pulmonary_embolism",
                filename="urgences_fr.txt",
            ),
            fact(
                "current_problem.suspected_diagnosis",
                "  PULMONARY_EMBOLISM ",
                filename="referral_en.txt",
            ),
        ]
    )

    field = case.current_problem["suspected_diagnosis"]
    assert field.value == "pulmonary_embolism"
    assert field.status == FieldStatus.observed
    assert field.temporal_status == TemporalStatus.current
    assert [source.filename for source in field.sources] == [
        "urgences_fr.txt",
        "referral_en.txt",
    ]
    assert len(case.timeline) == 2


def test_explicit_current_renal_value_supersedes_old_value_and_retains_evidence():
    case = reconcile_facts(
        [
            fact(
                "labs.egfr_ml_min_1_73m2",
                42,
                filename="old_labs.txt",
                temporal_status="historical",
                observed_at="2024-02-03",
            ),
            fact(
                "labs.egfr_ml_min_1_73m2",
                78,
                filename="current_labs.txt",
                observed_at="2026-09-07",
            ),
        ]
    )

    field = case.labs["egfr_ml_min_1_73m2"]
    assert field.value == 78
    assert field.status == FieldStatus.observed
    assert field.temporal_status == TemporalStatus.current
    assert field.observed_at == "2026-09-07"
    assert len(field.sources) == 2
    assert case.metadata["reconciliation"]["resolutions"][0]["method"] == (
        "explicit_current_status"
    )


def test_different_current_renal_values_are_conflicting():
    case = reconcile_facts(
        [
            fact("labs.egfr_ml_min_1_73m2", 42, filename="lab_a.txt"),
            fact("labs.egfr_ml_min_1_73m2", 78, filename="lab_b.txt"),
        ]
    )

    field = case.labs["egfr_ml_min_1_73m2"]
    assert field.value == [42, 78]
    assert field.status == FieldStatus.conflicting
    assert field.temporal_status == TemporalStatus.unknown
    assert len(field.sources) == 2
    assert case.metadata["reconciliation"]["conflicts"][0]["field"] == ("labs.egfr_ml_min_1_73m2")


def test_old_resolved_contrast_reaction_is_not_erased_by_current_negative_statement():
    case = reconcile_facts(
        [
            fact(
                "allergies.iodinated_contrast_reaction",
                "diffuse_urticaria",
                filename="old_ct.txt",
                temporal_status="resolved",
                observed_at="2024-11-10",
            ),
            fact(
                "allergies.iodinated_contrast_reaction",
                False,
                filename="current_note.txt",
            ),
        ]
    )

    field = case.allergies["iodinated_contrast_reaction"]
    assert field.status == FieldStatus.conflicting
    assert field.value == ["diffuse_urticaria", False]
    assert len(case.timeline) == 2


def test_current_pregnancy_statements_remain_explicitly_conflicting():
    case = reconcile_facts(
        [
            fact("imaging_safety.pregnancy", True, filename="triage.txt"),
            fact("imaging_safety.pregnancy", False, filename="lab.txt"),
        ]
    )

    assert case.imaging_safety["pregnancy"].status == FieldStatus.conflicting


def test_current_anticoagulation_answer_can_resolve_historical_treatment():
    case = reconcile_facts(
        [
            fact(
                "medications.anticoagulation",
                "apixaban",
                filename="old_letter.txt",
                temporal_status="historical",
            ),
            fact("medications.anticoagulation", False, filename="current_medication.txt"),
        ]
    )

    field = case.medications["anticoagulation"]
    assert field.value is False
    assert field.temporal_status == TemporalStatus.current
    assert len(field.sources) == 2


def test_historical_device_and_unknown_date_remain_visible_without_becoming_current():
    case = reconcile_facts(
        [
            fact(
                "imaging_safety.pacemaker",
                True,
                filename="history.txt",
                temporal_status="historical",
            )
        ]
    )

    field = case.imaging_safety["pacemaker"]
    assert field.value is True
    assert field.temporal_status == TemporalStatus.historical
    assert field.observed_at is None
    assert case.timeline[0].observed_at is None


def test_historical_list_observations_are_combined_as_longitudinal_evidence():
    case = reconcile_facts(
        [
            fact(
                "history.relevant_conditions",
                ["hypertension"],
                filename="letter_fr.txt",
                temporal_status="historical",
            ),
            fact(
                "history.relevant_conditions",
                ["hypertension", "dyslipidemia"],
                filename="summary_en.txt",
                temporal_status="historical",
            ),
        ]
    )

    field = case.history["relevant_conditions"]
    assert field.value == ["hypertension", "dyslipidemia"]
    assert field.status == FieldStatus.observed
    assert field.temporal_status == TemporalStatus.historical
