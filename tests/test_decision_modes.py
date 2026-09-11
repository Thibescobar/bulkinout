import json
from pathlib import Path

import pytest

from bulkinout import cli
from bulkinout.core.models import (
    ClinicalCase,
    ClinicalField,
    FieldStatus,
    ImagingDecision,
    ImagingRecommendation,
    LLMExtraction,
    MissingQuestion,
    RadiologyCase,
)
from bulkinout.core.service import CoreResult
from bulkinout.output import write_request_outputs
from bulkinout.request.decision_comparison import compare_decisions
from bulkinout.request.decision_deterministic import DeterministicRequestDecision
from bulkinout.request.service import run_request_from_core


def _known(value):
    return ClinicalField(value=value, status=FieldStatus.observed, confidence=1.0)


def _case() -> ClinicalCase:
    return ClinicalCase(
        patient={"sex": _known("M")},
        current_problem={
            "indication": _known("custom condition"),
            "symptoms": _known("custom symptom"),
        },
    )


def _core_result() -> CoreResult:
    return CoreResult(RadiologyCase(clinical=_case()), LLMExtraction(), [])


def _scenario_context(*, candidates=None, questions=None, rules=None):
    return {
        "matched_scenarios": [
            {
                "id": "scenario_one",
                "title": "Scenario one",
                "match_score": 1.0,
                "version": "1",
                "status": "draft",
                "sources": [],
                "candidate_exams": candidates or [],
                "unresolved_material_questions": questions or [],
                "rules_triggered": rules or [],
            }
        ]
    }


def _candidate(candidate_id="ct_one", exam_name="TDM sans injection"):
    return {
        "id": candidate_id,
        "exam_name": exam_name,
        "modality": "CT",
        "contrast": "no",
        "appropriateness": "usually_appropriate",
    }


def _write_reference(path: Path, *, candidate_count: int = 1) -> Path:
    path.mkdir()
    candidates = "\n".join(
        f"  - id: ct_{index}\n"
        f"    exam_name: TDM {index}\n"
        "    modality: CT\n"
        "    contrast: no\n"
        "    appropriateness: usually_appropriate"
        for index in range(candidate_count)
    )
    (path / "custom.yaml").write_text(
        "id: custom\n"
        "version: 1\n"
        "title: Custom scenario\n"
        "entry:\n"
        "  any:\n"
        "    - {field: current_problem.indication, contains: custom}\n"
        "questions: []\n"
        f"candidates:\n{candidates}\n",
        encoding="utf-8",
    )
    return path


class CountingDecisionEngine:
    provider = "local"
    name = "counting_decision"
    model = "test"
    prompt_sha256 = "test"
    inference_parameters = {}

    def __init__(self):
        self.calls = 0

    def decide(self, case, missing_questions, reference_context=None):
        self.calls += 1
        return ImagingDecision(
            decision_status="selected",
            primary=ImagingRecommendation(
                exam_name="Décision LLM",
                modality="US",
                contrast="no",
            ),
            clinician_call_required=False,
        )


def test_deterministic_engine_selects_unique_applicable_candidate():
    decision = DeterministicRequestDecision().decide(
        _case(), [], _scenario_context(candidates=[_candidate()])
    )

    assert decision.decision_status == "selected"
    assert decision.primary.exam_name == "TDM sans injection"
    assert "référentiel clinique" in decision.primary.rationale[0]


def test_deterministic_engine_uses_explicit_preferred_candidate_rule():
    candidates = [_candidate(), _candidate("ct_two", "TDM avec injection")]
    decision = DeterministicRequestDecision().decide(
        _case(),
        [],
        _scenario_context(
            candidates=candidates,
            rules=[
                {
                    "rule_id": "PREFER_SECOND",
                    "result": {"preferred_candidate": "ct_two"},
                }
            ],
        ),
    )

    assert decision.decision_status == "selected"
    assert decision.primary.exam_name == "TDM avec injection"
    assert "référentiel clinique" in decision.primary.rationale[0]


def test_deterministic_engine_routes_ambiguous_candidates_to_radiologist():
    engine = DeterministicRequestDecision()

    ambiguous = engine.decide(
        _case(), [], _scenario_context(candidates=[_candidate(), _candidate("ct_two", "IRM")])
    )

    assert ambiguous.decision_status == "radiologist_selection_required"
    assert ambiguous.primary.recommended is False
    assert ambiguous.primary.exam_name == "TDM sans injection"
    assert [item.exam_name for item in ambiguous.secondary] == ["IRM"]
    assert ambiguous.clinician_call_required is False


def test_deterministic_engine_routes_context_dependent_candidate_to_radiologist():
    candidate = _candidate()
    candidate["appropriateness"] = "context_dependent"

    decision = DeterministicRequestDecision().decide(
        _case(), [], _scenario_context(candidates=[candidate])
    )

    assert decision.decision_status == "radiologist_selection_required"
    assert decision.primary.recommended is False
    assert decision.clinician_call_required is False


def test_deterministic_engine_abstains_when_no_candidate_is_available():
    absent = DeterministicRequestDecision().decide(_case(), [], _scenario_context())

    assert absent.decision_status == "insufficient_information"
    assert absent.primary.recommended is False


def test_deterministic_engine_only_uses_explicit_no_imaging_rule():
    explicit = DeterministicRequestDecision().decide(
        _case(),
        [],
        _scenario_context(
            candidates=[_candidate()],
            rules=[
                {
                    "rule_id": "NO_IMAGING",
                    "result": {"no_imaging_recommended": True},
                }
            ],
        ),
    )

    assert explicit.decision_status == "no_imaging_recommended"
    assert explicit.primary.recommended is False
    assert "NO_IMAGING" in (explicit.no_imaging_reason or "")


def test_deterministic_engine_abstains_for_unresolved_required_question():
    decision = DeterministicRequestDecision().decide(
        _case(),
        [],
        _scenario_context(
            candidates=[_candidate()],
            questions=[
                {
                    "id": "needed",
                    "field": "current_problem.needed",
                    "question": "Information nécessaire ?",
                    "required_to_choose": True,
                }
            ],
        ),
    )

    assert decision.decision_status == "insufficient_information"


def test_deterministic_mode_never_constructs_llm_decision(monkeypatch, tmp_path):
    reference = _write_reference(tmp_path / "reference")

    def fail_if_constructed(*args, **kwargs):
        raise AssertionError("The LLM decision engine must not be constructed")

    monkeypatch.setattr(
        "bulkinout.request.service.OpenAIRequestDecision",
        fail_if_constructed,
    )

    result = run_request_from_core(
        _core_result(),
        reference_dir=reference,
        decision_model="ignored-model",
        decision_mode="deterministic",
    )

    assert result.imaging_decision.primary.exam_name == "TDM 0"
    assert result.run_manifest is not None
    assert result.run_manifest.decision_mode == "deterministic"
    assert result.run_manifest.active_decision_engine == "deterministic"
    assert [item.engine for item in result.run_manifest.decision_engines] == ["deterministic"]
    assert result.run_manifest.decision_engines[0].fingerprint.inference_parameters == {
        "llm_calls": 0,
        "world": "closed",
    }


def test_deterministic_mode_applies_existing_safety_questions(tmp_path):
    reference = tmp_path / "reference"
    reference.mkdir()
    (reference / "custom.yaml").write_text(
        "id: custom\n"
        "title: Custom scenario\n"
        "entry:\n"
        "  any:\n"
        "    - {field: current_problem.indication, contains: custom}\n"
        "questions: []\n"
        "candidates:\n"
        "  - id: ct_contrast\n"
        "    exam_name: TDM avec injection\n"
        "    modality: CT\n"
        "    contrast: yes\n"
        "    appropriateness: usually_appropriate\n",
        encoding="utf-8",
    )

    result = run_request_from_core(
        _core_result(), reference_dir=reference, decision_mode="deterministic"
    )

    assert result.imaging_decision.decision_status == "insufficient_information"
    assert result.imaging_decision.primary.recommended is False
    assert {question.field for question in result.missing_questions} >= {
        "allergies.iodinated_contrast_reaction",
        "labs.egfr_ml_min_1_73m2",
    }


def test_deterministic_pe_routes_equivalent_options_to_radiologist():
    case = ClinicalCase(
        patient={"age": _known(67), "sex": _known("female")},
        current_problem={
            "indication": _known("Suspicion d'embolie pulmonaire"),
            "symptoms": _known(["dyspnée brutale"]),
            "suspected_diagnosis": _known("pulmonary embolism"),
            "pe_pretest_probability": _known("high"),
        },
        allergies={"iodinated_contrast_reaction": _known("urticaire diffuse")},
        labs={"d_dimer": _known("positive"), "egfr_ml_min_1_73m2": _known(51)},
    )
    core = CoreResult(RadiologyCase(clinical=case), LLMExtraction(), [])

    result = run_request_from_core(core, decision_mode="deterministic")

    assert result.imaging_decision.decision_status == "radiologist_selection_required"
    assert result.imaging_decision.clinician_call_required is False
    assert result.imaging_decision.primary.exam_name == "Angioscanner des artères pulmonaires"
    assert [item.exam_name for item in result.imaging_decision.secondary] == [
        "Scintigraphie pulmonaire ventilation/perfusion (V/Q)"
    ]
    assert result.teleradiology_request.status == "ready_for_human_approval"
    assert result.teleradiology_request.requested_exam is None
    assert result.radiology_handoff is not None
    assert result.radiology_handoff.status == "ready_for_radiologist_review"
    assert result.radiology_handoff.radiologist_selection_required is True


def test_radiologist_option_set_does_not_apply_first_option_checks_globally(tmp_path):
    reference = tmp_path / "reference"
    reference.mkdir()
    (reference / "custom.yaml").write_text(
        "id: custom\n"
        "title: Custom scenario\n"
        "entry:\n"
        "  any:\n"
        "    - {field: current_problem.indication, contains: custom}\n"
        "questions: []\n"
        "candidates:\n"
        "  - {id: ct_iv, exam_name: TDM injectée, modality: CT, contrast: yes}\n"
        "  - {id: us, exam_name: Échographie, modality: US, contrast: no}\n",
        encoding="utf-8",
    )

    result = run_request_from_core(
        _core_result(), reference_dir=reference, decision_mode="deterministic"
    )

    assert result.imaging_decision.decision_status == "radiologist_selection_required"
    assert result.imaging_decision.clinician_call_required is False
    assert result.missing_questions == []


def test_shadow_runs_each_engine_once_and_keeps_llm_active(tmp_path):
    reference = _write_reference(tmp_path / "reference")
    llm = CountingDecisionEngine()

    result = run_request_from_core(
        _core_result(),
        reference_dir=reference,
        decision_engine=llm,
        decision_mode="shadow",
    )

    assert llm.calls == 1
    assert result.imaging_decision is result.llm_decision
    assert result.imaging_decision.primary.exam_name == "Décision LLM"
    assert result.deterministic_decision is not None
    assert result.deterministic_decision.primary.exam_name == "TDM 0"
    assert result.teleradiology_request.requested_exam == "Décision LLM"
    assert result.radiology_handoff is not None
    assert result.radiology_handoff.proposal.exam_name == "Décision LLM"
    assert result.run_manifest is not None
    assert result.run_manifest.decision_mode == "shadow"
    assert result.run_manifest.active_decision_engine == "llm"
    assert [item.engine for item in result.run_manifest.decision_engines] == [
        "llm",
        "deterministic",
    ]


def test_shadow_outputs_add_only_comparison_artifacts(tmp_path):
    reference = _write_reference(tmp_path / "reference")
    result = run_request_from_core(
        _core_result(),
        reference_dir=reference,
        decision_engine=CountingDecisionEngine(),
        decision_mode="shadow",
    )
    output = tmp_path / "output"

    write_request_outputs(result, output)

    assert {
        "imaging_decision_llm.json",
        "imaging_decision_deterministic.json",
        "decision_comparison.json",
    } <= {path.name for path in output.iterdir()}
    active = json.loads((output / "imaging_decision.json").read_text(encoding="utf-8"))
    llm = json.loads((output / "imaging_decision_llm.json").read_text(encoding="utf-8"))
    assert active == llm


def test_decision_comparison_reports_agreement_and_required_question_differences():
    first = ImagingDecision(
        decision_status="selected",
        primary=ImagingRecommendation(exam_name="TDM", protocol="portal"),
    )
    second = first.model_copy(deep=True)
    question = MissingQuestion(
        field="labs.egfr_ml_min_1_73m2",
        question="DFG ?",
        importance="high",
        reason="Safety",
        required_to_choose=True,
    )

    agreement = compare_decisions(first, [question], second, [])
    second.primary.protocol = "sans injection"
    disagreement = compare_decisions(first, [], second, [])

    assert agreement.same_status is True
    assert agreement.same_primary_exam is True
    assert agreement.same_protocol is True
    assert agreement.llm.required_question_fields == ["labs.egfr_ml_min_1_73m2"]
    assert disagreement.same_protocol is False


@pytest.mark.parametrize("mode", ["llm", "deterministic", "shadow"])
def test_cli_accepts_supported_decision_modes(mode):
    args = cli.build_parser().parse_args(["request", "run", "--decision-mode", mode])
    assert args.decision_mode == mode


def test_cli_rejects_unknown_decision_mode():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["request", "run", "--decision-mode", "hybrid"])
