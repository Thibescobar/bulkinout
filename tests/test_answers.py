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
