import json
from datetime import UTC, datetime

from bulkinout.core.models import (
    AnswerFile,
    AnswerItem,
    ClinicalCase,
    ClinicalField,
    FieldStatus,
    SourceRef,
    TemporalStatus,
    TimelineEvent,
)
from bulkinout.request.answers import apply_answers, load_answers


def test_load_answers_accepts_mapping_form(tmp_path):
    path = tmp_path / "answers.json"
    path.write_text(
        json.dumps({"answers": {"patient.age": 42, "patient.sex": "F"}}),
        encoding="utf-8",
    )

    answers = load_answers(path)

    assert [(item.field, item.value) for item in answers.answers] == [
        ("patient.age", 42),
        ("patient.sex", "F"),
    ]


def test_load_answers_accepts_full_list_form(tmp_path):
    path = tmp_path / "answers.json"
    path.write_text(
        json.dumps(
            {
                "answers": [
                    {
                        "question_id": "age",
                        "field": "patient.age",
                        "value": 42,
                        "note": "Confirmed by clinician",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_answers(path).answers[0].question_id == "age"


def test_apply_answers_updates_valid_fields_and_tracks_provenance():
    case = ClinicalCase(metadata={"answer_files": ["earlier.json"]})
    answers = AnswerFile(
        answers=[
            AnswerItem(field="patient.age", value=42, note="Telephone confirmation"),
            AnswerItem(field="invalid", value="ignored"),
            AnswerItem(field="unsupported.value", value="ignored"),
        ]
    )

    result = apply_answers(case, answers, "answers.json")

    age = result.patient["age"]
    assert age.value == 42
    assert age.status == FieldStatus.observed
    assert age.confidence == 1.0
    assert age.sources[0].document_id == "answers:answers.json"
    assert age.sources[0].excerpt == "Telephone confirmation"
    assert result.metadata["answer_files"] == ["earlier.json", "answers.json"]


def test_apply_answers_keeps_empty_values_unresolved_but_records_the_attempt():
    case = ClinicalCase()
    answers = AnswerFile(
        answers=[
            AnswerItem(field="imaging_safety.pregnancy", value=None, question="Grossesse ?"),
            AnswerItem(field="current_problem.onset", value="   ", question="Début ?"),
        ]
    )

    result = apply_answers(case, answers, "interactive.json")

    assert "pregnancy" not in result.imaging_safety
    assert "onset" not in result.current_problem
    assert [item["state"] for item in result.metadata["clarifications"]] == [
        "unanswered",
        "unanswered",
    ]


def test_apply_answers_preserves_false_and_zero_as_typed_observations():
    case = ClinicalCase()
    answers = AnswerFile(
        answers=[
            AnswerItem(field="imaging_safety.pregnancy", value=False),
            AnswerItem(field="current_problem.gcs", value=0),
        ]
    )

    result = apply_answers(case, answers, "interactive.json")

    assert result.imaging_safety["pregnancy"].value is False
    assert result.current_problem["gcs"].value == 0
    assert [item["state"] for item in result.metadata["clarifications"]] == [
        "answered",
        "answered",
    ]


def test_clinician_answer_resolves_conflict_without_discarding_evidence():
    previous_source = SourceRef(document_id="llm:lab.txt", filename="lab.txt")
    case = ClinicalCase(
        labs={
            "egfr_ml_min_1_73m2": ClinicalField(
                value=[42, 78],
                status=FieldStatus.conflicting,
                sources=[previous_source],
            )
        },
        timeline=[
            TimelineEvent(
                field="labs.egfr_ml_min_1_73m2",
                value=42,
                status=FieldStatus.observed,
                temporal_status=TemporalStatus.current,
                sources=[previous_source],
            )
        ],
    )
    answered_at = datetime(2026, 9, 7, 9, 30, tzinfo=UTC)
    answers = AnswerFile(
        answers=[
            AnswerItem(
                field="labs.egfr_ml_min_1_73m2",
                value=42,
                answered_at=answered_at,
                response_method="interactive_browser",
            )
        ]
    )

    result = apply_answers(case, answers, "answers.interactive.1.json")

    field = result.labs["egfr_ml_min_1_73m2"]
    assert field.value == 42
    assert field.status == FieldStatus.observed
    assert field.temporal_status == TemporalStatus.current
    assert field.observed_at == answered_at.isoformat()
    assert [source.filename for source in field.sources] == [
        "lab.txt",
        "answers.interactive.1.json",
    ]
    assert len(result.timeline) == 2
    assert result.metadata["reconciliation"]["resolutions"][0]["method"] == (
        "explicit_clinician_answer"
    )
