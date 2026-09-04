# End-to-End Tests

These synthetic records test the complete **documents → Core → Request** path with a real LLM call. They are not run by pytest; v0 uses them for manual, reproducible review.

## Included Cases

| Case | Test intent |
|---|---|
| `case_001_rlq_complete` | Complete record: an imaging proposal should be prepared without a clinician callback. |
| `case_002_right_sided_pain_ambiguous` | Ambiguous record: BULKINOUT should request discriminating information instead of forcing an exam. |
| `case_003_suspected_pe_conflicting_allergy` | Distributed data and contradictory evidence about a prior iodinated-contrast reaction. |

Patient source documents remain in French because they are clinical input fixtures. `expected.json` keys and developer-facing metadata use English; expected French presentation strings remain French.

## Run a Case

```bash
bulkinout request run --input tests/e2e/case_001_rlq_complete --output output_e2e/case_001
```

Compare `output_e2e/case_001/` with the case's `expected.json`, then record the review in `review/radiologist_review_template.csv`.

For case 002, `answers_after_call.example.json` demonstrates a second pass after clarification:

```bash
bulkinout request run --input tests/e2e/case_002_right_sided_pain_ambiguous --answers tests/e2e/case_002_right_sided_pain_ambiguous/answers_after_call.example.json --output output_e2e/case_002_after_answers
```
