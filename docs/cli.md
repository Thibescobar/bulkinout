# Command-line interface

The console entry point is declared in `pyproject.toml`:

```toml
[project.scripts]
bulkinout = "bulkinout.cli:main"
```

Install the package in editable mode before using the command:

```bash
pip install -e ".[dev]"
bulkinout --help
```

Technical help, progress, and error text are in English. Questions and generated request content intended for current clinical users remain in French.

## Command tree

```text
bulkinout
├── core
│   └── structure
├── request
│   ├── run
│   ├── catalog
│   ├── golden
│   └── evaluate
└── report
```

## Configuration precedence

Both LLM-backed CLI commands currently use the built-in OpenAI adapters and need:

- `OPENAI_API_KEY` in the process environment;
- an extraction model and, for Request, a decision model.

For `request run`, each stage resolves its model in this order:

1. `--extraction-model` or `--decision-model`;
2. the shared `--model` compatibility fallback;
3. `BULKINOUT_EXTRACTION_MODEL` or `BULKINOUT_DECISION_MODEL`;
4. the shared `BULKINOUT_MODEL` compatibility fallback.

`core structure --model` configures extraction only, then falls back to `BULKINOUT_EXTRACTION_MODEL` and `BULKINOUT_MODEL`. `.env.example` documents variable names, but Bulkinout does not load `.env` files itself.

```bash
export OPENAI_API_KEY="..."
export BULKINOUT_MODEL="<compatible-model>"
```

## `bulkinout core structure`

Run ingestion and extraction without the Request workflow:

```bash
bulkinout core structure \
  --input input \
  --output output_core \
  --model "$BULKINOUT_MODEL"
```

| Option | Default | Meaning |
|---|---|---|
| `--input` | `input` | Directory recursively scanned for PDF, TXT, Markdown, JPEG, PNG, and WebP files. |
| `--output` | `output` | Destination directory. Parent directories are created when outputs are written. |
| `--model` | `BULKINOUT_EXTRACTION_MODEL`, then `BULKINOUT_MODEL` | Model used by `OpenAICoreExtractor`. |

Outputs:

- `radiology_case.json` — aggregate record with artifacts and Core audit state;
- `llm_extraction.json` — direct validated structured model response.

The command rejects a missing API key before file discovery. It then rejects an empty supported input set or an unspecified model.

## `bulkinout request run`

Run Core and the complete pre-exam Request workflow:

```bash
bulkinout request run \
  --input input \
  --output output
```

| Option | Default | Meaning |
|---|---|---|
| `--input` | `input` | Clinical document directory processed by Core. |
| `--output` | `output` | Destination for aggregate and intermediate JSON artifacts. |
| `--answers` | none | Optional answer JSON from a previous clarification pass. |
| `--reference` | packaged reference | Optional scenario-directory override. |
| `--extraction-model` | `BULKINOUT_EXTRACTION_MODEL` | Model used for Core extraction. |
| `--decision-model` | `BULKINOUT_DECISION_MODEL` | Model used for Request decision support. |
| `--model` | `BULKINOUT_MODEL` | Optional shared fallback for both stages. |

The command reports the combined service run before processing:

```text
Running the Core and Request workflow...
```

It then writes all outputs and finishes with the guarded decision status, whether a clinician call is required, and the request status. Detailed step order belongs to the shared Request service and is identical for CLI and Python callers.

### Clarification pass

The first run may write `answers.template.json`:

```json
{
  "answers": [
    {
      "question_id": "pregnancy",
      "field": "imaging_safety.pregnancy",
      "value": null,
      "note": "Une grossesse est-elle possible ou en cours ?"
    }
  ]
}
```

Copy or rename it, fill the values, and pass the completed file:

```bash
cp output/answers.template.json answers.json
# Edit answers.json after obtaining the clinical answers.
bulkinout request run \
  --input input \
  --answers answers.json \
  --output output_after_answers
```

This is a complete rerun: documents are extracted again, answers are then applied, and the reference, decision, guards, and outputs are recalculated.

## `bulkinout request catalog`

Inspect the scenario set without an LLM:

```bash
bulkinout request catalog --reference reference/scenarios
```

| Option | Default | Meaning |
|---|---|---|
| `--reference` | packaged reference | Optional directory of YAML scenarios to summarize instead. |

Each output line includes ID, version, candidate count, question count, and validation status. This is a structural inventory; it does not test clinical behavior or compare against `reference/catalog.json`.

## `bulkinout request golden`

Run deterministic reference cases without an LLM:

```bash
bulkinout request golden \
  --cases tests/golden
```

| Option | Default | Meaning |
|---|---|---|
| `--cases` | `tests/golden` | Directory recursively searched for YAML golden cases. |
| `--reference` | packaged reference | Optional scenario-directory override. |

The command prints `[PASS]` or `[FAIL]` per case and exits with status 1 if any case fails. It exits with status 2 if no golden files are found. Use `--reference reference/scenarios` while authoring the canonical source reference and omit it to verify the installed default.

## `bulkinout request evaluate`

Evaluate one saved real-model run without making another provider call:

```bash
bulkinout request evaluate \
  --case tests/e2e/case_001_rlq_complete \
  --run output_e2e/case_001 \
  --report output_e2e/case_001/evaluation.json
```

| Option | Default | Meaning |
|---|---|---|
| `--case` | required | Fixture directory containing the schema-v1 `expected.json`. |
| `--run` | required | Directory containing `case.json`, Request artifacts, and the run manifest. |
| `--report` | none | Optional JSON destination for the structured evaluation report. |

Core and Request are reported separately. Exit status 0 means every encoded assertion passed, 1 means at least one assertion failed, and 2 means an expectation or generated artifact is missing or invalid. A pass is reproducible software evidence, not clinical validation.

## `bulkinout report`

```bash
bulkinout report
```

This command only reports that the post-exam workflow is reserved for a later phase. It performs no processing and writes no output.

## Output lifecycle

JSON files are written directly with UTF-8 indentation. A Request run writes nine snapshots, including the schema-v2 `run_manifest.json`, whose hashes identify its package version, distributed Python source, inputs, components, prompts, schemas, and reference revision. The output directory is created if needed, and files with the same names are overwritten individually. Writes are not transactional: an interrupted run may leave a mixture of old and new files.

Use a fresh output directory for important runs:

```bash
bulkinout request run --input input --output output/run_2026_09_04
```

Generated `output*/` directories are ignored by Git and may contain sensitive clinical content.

## Common failures

| Message or symptom | Cause | Action |
|---|---|---|
| `OPENAI_API_KEY is missing.` | Required key is not exported. | Set it in the command environment; do not commit it. |
| `No extraction model configured.` | No extraction-specific or shared model is configured. | Set `--extraction-model`, `--model`, or the corresponding environment variable. |
| `No decision model configured.` | No decision-specific or shared model is configured. | Set `--decision-model`, `--model`, or the corresponding environment variable. |
| `No supported document found` | Input is empty, wrong, or contains only unsupported extensions. | Check `--input` and the supported-file list. |
| Pydantic validation error | The provider response does not satisfy the requested schema. | Inspect model compatibility and raw provider behavior. |
| No matched scenarios | Extracted field paths or terms do not satisfy any entry predicate. | Inspect `case.json` and `reference_context.json`; add tested synonyms when appropriate. |
| `insufficient_information` | A required or high-impact fact remains unknown/conflicting. | Complete `answers.template.json` after clinical clarification. |
| `safety_blocked` | A blocking safety fact is unresolved. | Obtain and record the missing safety information. |
| Evaluation exits 1 | At least one encoded Core or Request assertion failed. | Read the stage-specific failures and inspect the named artifacts. |
| Evaluation exits 2 | `expected.json` or a required run artifact is missing or invalid. | Correct the fixture or run directory before interpreting model quality. |

See [Request](request.md) for state transitions and [Operations and safety](operations.md) for data-handling boundaries.
