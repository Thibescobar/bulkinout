# End-to-end tests

These synthetic records test the complete **documents → Core → Request** path with a real LLM call. They are not run by pytest. Each `expected.json` uses executable assertion schema version 1 so that a completed run can be evaluated consistently while still supporting manual clinical review.

## Included cases

| Case | Test intent |
|---|---|
| `case_001_rlq_complete` | Complete record: an imaging proposal should be prepared without a clinician callback. |
| `case_002_right_sided_pain_ambiguous` | Ambiguous record: Bulkinout should request discriminating information instead of forcing an exam. |
| `case_003_suspected_pe_conflicting_allergy` | Distributed data and contradictory evidence about a prior iodinated-contrast reaction. |
| `renal_colic_001` | Minimal renal-colic record: undocumented pregnancy status must remain unknown and block selection. |
| `case_004_stroke_missing_onset_mixed` | Bilingual stroke record with no usable onset time: Request must ask for it. |
| `case_005_low_back_no_red_flags_en` | Complete English low-back-pain record: no initial imaging should be recommended. |
| `case_006_aortic_extent_missing_fr` | Suspected aortic syndrome with insufficient anatomical coverage information. |
| `case_007_head_trauma_positive_rule_fr` | Explicit positive head-CT rule with the decision inputs already documented. |
| `case_008_spine_infection_bilingual` | French and English evidence combined into one lumbar spinal-infection case. |
| `case_009_sepsis_negative_control_en` | Negative control: `sepsis` must not match the pulmonary-embolism scenario. |
| `case_010_conflicting_renal_function_fr` | Same-day contradictory eGFR results that must prevent contrast approval. |
| `case_011_image_only_renal_colic_fr` | Mildly degraded image-only French referral exercising multimodal extraction. |

Clinical source documents intentionally include French, English, and mixed-language records. `expected.json` keys and developer-facing metadata use English; expected French presentation strings remain French. Every record is synthetic and explicitly labelled; never substitute real patient material.

## Suggested manual suites

Run cases one at a time so model calls and failures remain visible. A Request run normally makes one extraction call and one decision call, in addition to any provider-side file upload. An answered `--interactive` round reuses Core and adds only one decision call.

The **quick smoke suite** covers one successful selection, ambiguity, a safety block, mixed-language extraction, negative matching, and image input:

1. `case_001_rlq_complete`
2. `case_002_right_sided_pain_ambiguous`
3. `renal_colic_001`
4. `case_004_stroke_missing_onset_mixed`
5. `case_009_sepsis_negative_control_en`
6. `case_011_image_only_renal_colic_fr`

The **extended suite** comprises all 12 cases. Run it before accepting a model, prompt, extraction-schema, or clinical-matching change. The deterministic golden suite remains the authoritative fast check for all reference rules; manual E2E cases sample cross-cutting model behavior rather than duplicating every scenario.

## Run a case

```bash
bulkinout request run --input tests/e2e/case_001_rlq_complete --output output_e2e/case_001
```

Exercise the clinician-question loop with a case that must remain blocked until onset is known:

```bash
bulkinout request run \
  --input tests/e2e/case_004_stroke_missing_onset_mixed \
  --output output_e2e/case_004_interactive \
  --interactive
```

After submission, confirm that `answers.interactive.1.json` retains the typed response and that `run_manifest.json` fingerprints it. Open `radiology_handoff.html` and verify that the final status, clinical question, clarification, source evidence, rationale or abstention, safety information, and scenario references support remote review without implying approval.

Evaluate the generated artifacts against the case assertions:

```bash
bulkinout request evaluate \
  --case tests/e2e/case_001_rlq_complete \
  --run output_e2e/case_001
```

Write the machine-readable evaluation report when it must be retained for review:

```bash
bulkinout request evaluate \
  --case tests/e2e/case_001_rlq_complete \
  --run output_e2e/case_001 \
  --report output_e2e/case_001/evaluation.json
```

The evaluator checks deterministic artifacts, but it does not replace radiologist review. Record the clinical review separately in `review/radiologist_review_template.csv`, including whether the handoff supports review and describes citations conservatively.

For case 002, `answers_after_call.example.json` demonstrates a second pass after clarification:

```bash
bulkinout request run --input tests/e2e/case_002_right_sided_pain_ambiguous --answers tests/e2e/case_002_right_sided_pain_ambiguous/answers_after_call.example.json --output output_e2e/case_002_after_answers
```

## Assertion schema version 1

Every `expected.json` has the required top-level keys `schema_version`, `case_id`, `purpose`, `core`, and `request`. Unknown keys and unsupported schema versions are errors. Assertion lists may be omitted when a case does not need that check.

```json
{
  "schema_version": 1,
  "case_id": "example_case",
  "purpose": "Developer-facing test intent in English.",
  "core": {
    "required_facts": [
      {
        "field": "labs.egfr_ml_min_1_73m2",
        "status_in": ["observed", "inferred"],
        "numeric": {
          "target": 51,
          "absolute_tolerance": 2
        }
      }
    ],
    "forbidden_facts": ["imaging_safety.pregnancy"],
    "forbidden_values": [
      {
        "field": "allergies.iodinated_contrast_reaction",
        "values": [false, "no"]
      }
    ]
  },
  "request": {
    "matched_scenarios_all_of": ["suspected_pulmonary_embolism"],
    "matched_scenarios_any_of": [],
    "forbidden_scenarios": [],
    "decision_status_in": ["selected", "safety_blocked"],
    "primary_exam_name_in": ["Angioscanner des artères pulmonaires"],
    "primary_recommended": false,
    "clinician_call_required": true,
    "required_question_fields": ["imaging_safety.pregnancy"],
    "forbidden_question_fields": [],
    "presentation_term_groups": [
      {
        "any_of": ["réaction iodée", "réaction au contraste iodé"]
      }
    ]
  }
}
```

`core.required_facts` asserts that a canonical field is present and known. `status_in` optionally restricts its evidence status. `numeric` optionally checks the extracted numeric value within an absolute tolerance. `forbidden_facts` rejects invented known facts, while `forbidden_values` rejects specific unsafe values without forbidding a supported alternative or a conflict status.

For Request assertions, `matched_scenarios_all_of` requires every listed scenario, `matched_scenarios_any_of` requires at least one listed scenario, and `forbidden_scenarios` rejects every listed scenario. The remaining scalar and list assertions constrain decision status, primary examination, recommendation and call flags, and canonical missing-question fields. Each `presentation_term_groups` entry passes when at least one of its `any_of` clinical terms appears in the teleradiology request.
