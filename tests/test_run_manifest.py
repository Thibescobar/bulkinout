import hashlib
import json

from bulkinout import __version__
from bulkinout.core.extraction.llm import EXTRACTION_PROMPT, OpenAICoreExtractor
from bulkinout.core.models import (
    ImagingDecision,
    ImagingRecommendation,
    LLMExtraction,
    LLMFact,
    MissingQuestion,
)
from bulkinout.output import write_request_outputs
from bulkinout.request.decision_llm import DECISION_PROMPT, OpenAIRequestDecision
from bulkinout.request.service import run_request


class LocalExtractor:
    provider = "local"
    name = "test_extractor"
    model = "local-test-model"
    prompt_sha256 = "a" * 64

    def extract(self, paths):
        assert [path.name for path in paths] == ["a.txt", "b.txt"]
        return LLMExtraction(
            facts=[
                LLMFact(
                    field="current_problem.suspected_diagnosis",
                    value="custom condition",
                    status="observed",
                    confidence=1.0,
                )
            ]
        )


class LocalDecisionEngine:
    def decide(self, case, missing_questions, reference_context=None):
        return ImagingDecision(primary=ImagingRecommendation())


def _run_with_custom_components(
    tmp_path,
    *,
    answers_content=None,
    first_input="first synthetic input",
):
    input_dir = tmp_path / "input"
    input_dir.mkdir(parents=True)
    (input_dir / "b.txt").write_text("second synthetic input", encoding="utf-8")
    (input_dir / "a.txt").write_text(first_input, encoding="utf-8")
    reference_dir = tmp_path / "reference"
    reference_dir.mkdir()
    scenario = reference_dir / "custom.yaml"
    scenario.write_text(
        """id: custom_scenario
version: 2.0.0
title: Custom scenario
entry:
  any:
    - {field: current_problem.suspected_diagnosis, contains: custom}
questions:
  - id: detail
    field: current_problem.detail
    question: "Quel détail clinique manque ?"
    material: true
    required_to_choose: true
    reason: "Changes the proposal."
""",
        encoding="utf-8",
    )
    answers_path = None
    if answers_content is not None:
        answers_path = tmp_path / "answers.json"
        answers_path.write_text(answers_content, encoding="utf-8")
    result = run_request(
        input_dir,
        reference_dir=reference_dir,
        answers_path=answers_path,
        extractor=LocalExtractor(),
        decision_engine=LocalDecisionEngine(),
    )
    return result, scenario


def test_request_run_carries_reproducible_manifest(tmp_path):
    result, scenario = _run_with_custom_components(tmp_path)

    manifest = result.run_manifest
    assert manifest is not None
    assert manifest.schema_version == 1
    assert manifest.package_version == __version__
    assert [item.filename for item in manifest.inputs] == ["a.txt", "b.txt"]
    assert manifest.inputs[0].sha256 == hashlib.sha256(b"first synthetic input").hexdigest()
    assert manifest.core.provider == "local"
    assert manifest.core.component == "test_extractor"
    assert manifest.core.model == "local-test-model"
    assert manifest.core.prompt_sha256 == "a" * 64
    assert len(manifest.core.schema_sha256) == 64
    assert manifest.request.provider == "unreported"
    assert manifest.request.component == "unreported"
    assert manifest.request.model == "unreported"
    assert manifest.request.prompt_sha256 == "unreported"
    assert len(manifest.request.schema_sha256) == 64
    assert len(manifest.reference.revision) == 64
    assert manifest.reference.matched_scenarios[0].scenario_id == "custom_scenario"
    assert manifest.reference.matched_scenarios[0].version == "2.0.0"
    assert (
        manifest.reference.matched_scenarios[0].sha256
        == hashlib.sha256(scenario.read_bytes()).hexdigest()
    )


def test_manifest_is_stable_and_tracks_answer_and_input_changes(tmp_path):
    answers = '{"answers": []}\n'
    first, _ = _run_with_custom_components(tmp_path / "first", answers_content=answers)
    second, _ = _run_with_custom_components(tmp_path / "second", answers_content=answers)

    assert first.run_manifest == second.run_manifest
    assert first.run_manifest is not None
    assert [item.filename for item in first.run_manifest.inputs] == [
        "a.txt",
        "answers.json",
        "b.txt",
    ]
    assert first.run_manifest.inputs[1].sha256 == hashlib.sha256(answers.encode()).hexdigest()

    changed_answers, _ = _run_with_custom_components(
        tmp_path / "changed_answers",
        answers_content='{"answers": []}\n\n',
    )
    assert changed_answers.run_manifest is not None
    assert changed_answers.run_manifest != first.run_manifest

    changed, _ = _run_with_custom_components(
        tmp_path / "changed",
        answers_content=answers,
        first_input="changed synthetic input",
    )
    assert changed.run_manifest is not None
    assert changed.run_manifest != first.run_manifest


def test_builtin_prompt_hashes_track_exact_prompts():
    assert OpenAICoreExtractor.provider == "openai"
    assert (
        OpenAICoreExtractor.prompt_sha256
        == hashlib.sha256(EXTRACTION_PROMPT.encode("utf-8")).hexdigest()
    )
    assert OpenAIRequestDecision.provider == "openai"
    assert (
        OpenAIRequestDecision.prompt_sha256
        == hashlib.sha256(DECISION_PROMPT.encode("utf-8")).hexdigest()
    )


def test_request_outputs_include_manifest_and_all_required_answers(tmp_path):
    result, _ = _run_with_custom_components(tmp_path)
    result.missing_questions.append(
        MissingQuestion(
            field="imaging_safety.custom_device",
            question="Le dispositif est-il compatible ?",
            importance="critical",
            reason="Safety requirement.",
            blocking=True,
        )
    )
    output_dir = tmp_path / "output"

    write_request_outputs(result, output_dir)

    manifest_payload = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest_payload == result.run_manifest.model_dump(mode="json")
    assert "first synthetic input" not in json.dumps(manifest_payload)
    answer_payload = json.loads((output_dir / "answers.template.json").read_text(encoding="utf-8"))
    answers_by_field = {answer["field"]: answer for answer in answer_payload["answers"]}
    assert answers_by_field["current_problem.detail"]["question_id"] == "detail"
    assert answers_by_field["imaging_safety.custom_device"]["question_id"] == (
        "imaging_safety.custom_device"
    )
