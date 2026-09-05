import json

from bulkinout.core.models import AnswerFile, AnswerItem, ClinicalCase, FieldStatus
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
