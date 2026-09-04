# CLI

The entry point is declared as `bulkinout = "bulkinout.cli:main"` in `pyproject.toml`. CLI help, progress output, and technical errors are in English; clinical questions and generated clinical request content remain in French.

## `bulkinout core structure`

Arguments: `--input`, `--output`, and `--model`. Requires `OPENAI_API_KEY` and a model supplied through `--model` or `BULKINOUT_MODEL`. Writes `radiology_case.json` and `llm_extraction.json`.

## `bulkinout request run`

Arguments: `--input`, `--output`, `--answers`, `--reference`, and `--model`. Requires the same LLM configuration. Writes `radiology_case.json`, `llm_extraction.json`, `case.json`, `reference_context.json`, `missing_questions.json`, `imaging_decision.json`, `teleradiology_request.json`, and `answers.template.json`.

## `bulkinout request catalog`

Lists YAML scenarios, versions, candidate and question counts, and validation status. It makes no LLM call.

## `bulkinout request golden`

Runs YAML golden cases without an LLM and exits nonzero on failure.

## `bulkinout report`

Reports that the post-exam workflow is reserved for a later phase. v0 performs no post-exam processing.
