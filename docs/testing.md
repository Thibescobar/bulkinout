# Tests

## Pytest

```bash
pytest -q
```

The suite covers models, ingestion, extraction with simulated clients, rules, the decision guard, reference engine, catalog, CLI, and golden cases. `pytest-cov` measures `bulkinout` automatically and enforces at least 95% coverage.

Run lint before every contribution:

```bash
ruff check src tests
```

## Golden Cases

`tests/golden/*.yaml` tests the reference without an LLM. `case_from_facts()` converts `section.field → value` mappings into a `ClinicalCase`; `run_golden_case()` compares matched scenarios, triggered rules, questions, and expected results. These tests are fast and deterministic.

```bash
bulkinout request golden --cases tests/golden --reference reference/scenarios
```

Golden clinical facts may be French, English, or another supported input language. Keep existing French cases and add English equivalents when validating multilingual matching.

## End-to-End

`tests/e2e/` contains synthetic multidocument records. They call the Core/LLM and Request workflows and are excluded from default pytest runs. Each case has an `expected.json` for manual comparison. Record findings in `review/radiologist_review_template.csv`.

## Turn Errors into Tests

For a reference error, add or update a golden case before changing a rule. For an extraction error, retain the E2E case and `expected.json` so later Core versions remain measurable.
