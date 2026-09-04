# Operations guide

This guide explains how to run Bulkinout v0 safely, what data crosses each boundary, and what an operator must verify. Bulkinout is a decision-support proof of concept: it prepares structured information and a draft request, but it does not prescribe, transmit, or approve an examination.

## Configuration and precedence

The LLM-backed CLI commands currently use the built-in OpenAI adapters and require credentials plus a model for each active stage:

| Setting | Purpose | Resolution order |
|---|---|---|
| `OPENAI_API_KEY` | Authenticates OpenAI SDK requests | Environment only |
| `BULKINOUT_EXTRACTION_MODEL` | Default Core extraction model | After explicit extraction and shared arguments |
| `BULKINOUT_DECISION_MODEL` | Default Request decision model | After explicit decision and shared arguments |
| `BULKINOUT_MODEL` | Backward-compatible shared fallback | Last |

For `run_request()`, the exact priority is stage-specific argument, shared `model=` argument, stage-specific environment variable, then `BULKINOUT_MODEL`. The CLI applies the same order with `--extraction-model`, `--decision-model`, and `--model`. `build_radiology_case(model=...)` configures extraction only. Python callers may inject custom components; their configuration is owned by those components.

The application does **not** load `.env` files itself. Export the variables in the shell, source a protected file through your process manager, or inject them through the deployment environment:

```bash
export OPENAI_API_KEY="..."
export BULKINOUT_MODEL="<compatible-model>"
bulkinout request run --input input --output output
```

Input, output, answer, and golden-case paths are interpreted relative to the current working directory unless absolute paths are supplied. Their defaults are `input/`, `output/`, and `tests/golden/`. The reference defaults to the 18 scenarios shipped in the package; an explicit `--reference` path is resolved from the current directory unless absolute.

## Execution and data flow

The complete pre-exam command performs two LLM calls separated by deterministic processing:

```text
Supported documents
       |
       v
recursive collection --> LLM extraction --> ClinicalCase
                                             |
optional answers ----------------------------+
                                             v
generic questions --> YAML reference --> LLM decision
                                             |
                                             v
                              deterministic guards and safety checks
                                             |
                                             v
                           JSON artifacts + French request draft
```

`core structure` stops after the first LLM call and writes the structured longitudinal container. `request run` executes the entire diagram. When `--answers` is supplied, Bulkinout starts again from the source documents, repeats extraction, applies the answer file, and then repeats the Request phase. It does not resume from an earlier `radiology_case.json`.

The deterministic reference engine loads every packaged scenario, or every `*.yaml` file directly inside an explicit reference directory. It matches multilingual terms, selects applicable candidate exams, reports unresolved questions, and evaluates rules. Required or blocking reference questions are enforced after the LLM response, so the model may add context but cannot remove those constraints.

## LLM and clinical data handling

Source documents may be in any language. Technical identifiers and canonical values are English, while current clinician- and radiologist-facing clinical text is French.

With the built-in OpenAI extractor, data reaches the OpenAI SDK as follows:

- `.txt` and `.md` content is inserted directly into the model request.
- `.png`, `.jpg`, `.jpeg`, and `.webp` files are base64-encoded as high-detail image inputs.
- `.pdf` files are uploaded through the Files API with purpose `user_data`, then referenced by file identifier.
- Filenames are included in model input, and provenance excerpts may be written to output JSON.

Bulkinout does not currently delete uploaded files, redact identifiers, pseudonymize filenames, select a regional endpoint, or enforce a retention policy. Custom or local adapters own their transport and retention behavior and must document it independently. Before using any sensitive data, the deploying organization must establish an approved processing agreement, retention policy, access model, and data-minimization procedure. Use synthetic data for development and CI.

The extraction prompt prohibits invented facts and treats absent information as unknown. This is a model instruction, not a mathematical guarantee. Every extracted value retains a status, confidence, and available provenance so a human can inspect its origin.

## Outputs and lifecycle

`request run` creates or reuses the output directory and writes these files:

| Artifact | Operational role |
|---|---|
| `radiology_case.json` | Main container, including workflow state, artifacts, referral results, and audit events |
| `llm_extraction.json` | Raw structured extraction returned by the first LLM call |
| `case.json` | Clinical facts after optional answers are applied |
| `reference_context.json` | Matched scenarios, candidates, triggered rules, and unresolved material questions |
| `missing_questions.json` | Generic and modality-specific questions considered by the workflow |
| `imaging_decision.json` | LLM proposal after deterministic guards |
| `teleradiology_request.json` | French clinical draft; never an automatically approved transmission |
| `answers.template.json` | Required discriminating questions to complete before rerunning |
| `run_manifest.json` | Technical fingerprints for the package, code, inputs, components, prompts, schemas, and reference used |

Existing files with these names are overwritten. Writes are not atomic, versioned, or locked, so do not run two cases into the same directory concurrently. Use one private output directory per case and execution, then move validated artifacts into the organization’s controlled record system. Output JSON may contain clinical content and source excerpts; the manifest stores hashes rather than contents but can still expose filenames. Protect every artifact like the input documents. Generated `output*/` directories are intentionally excluded from Git.

## Decision and approval states

The main decision states are `selected`, `insufficient_information`, `no_imaging_recommended`, and `safety_blocked`. A required unanswered discriminator forces `insufficient_information`. Missing high-impact modality information can also prevent approval, while explicit unresolved safety checks can force `safety_blocked`.

The request status is independently derived:

- `blocked`: a blocking question or clinician call remains.
- `draft`: generated, but not ready for approval.
- `ready_for_human_approval`: ready to be reviewed, not already approved.

`validated_by_clinician` defaults to `false`. Bulkinout provides no authentication, electronic signature, order-entry integration, or transmission mechanism. A qualified clinician remains responsible for verifying the patient, indication, extracted facts, contraindications, examination, protocol, urgency, and destination before any use.

## Failure modes and troubleshooting

The CLI prints concise progress to standard output. Expected configuration, input, and reference failures use the `BulkinoutError` hierarchy and are rendered as one-line CLI errors with exit code 2. Provider, filesystem, and Pydantic exceptions remain unwrapped so Python integrations can handle their original types and developers retain useful diagnostics. Structured operational logging is not implemented yet.

| Symptom | Likely cause | Check |
|---|---|---|
| `OPENAI_API_KEY is missing.` | Key is absent from the process environment | Use `test -n "$OPENAI_API_KEY" && echo configured` without printing the value |
| `No extraction model configured` | No extraction-specific or shared model is configured | Set the extraction option or environment variable, or a shared fallback |
| `No decision model configured` | No decision-specific or shared model is configured | Set the decision option or environment variable, or a shared fallback |
| `No supported document found` | Empty path, wrong path, or unsupported extensions | Confirm the directory and use PDF, TXT, Markdown, PNG, JPEG, or WebP |
| OpenAI authentication or network error | Invalid credentials, connectivity, quota, or service failure | Verify the runtime environment and provider status; no retry policy is implemented |
| Pydantic validation error after a model call | Returned structured data did not satisfy the schema | Preserve the exception and model name; retry only after assessing whether the failure is transient |
| YAML/parser error | Malformed scenario file | Run `bulkinout request catalog` and the golden cases before deployment |
| Decision remains blocked | Required clinical or safety facts are unknown/conflicting | Review `missing_questions.json`, complete an answer file, and rerun |
| Partial or mixed output files | Process stopped during sequential writes | Discard the directory and rerun into a new empty directory |

For deterministic reference diagnostics, run:

```bash
bulkinout request catalog
bulkinout request golden --cases tests/golden
```

## Production readiness gaps

Before production use, the system still needs locally validated clinical reference content and model behavior; authenticated service boundaries; encryption and access controls; pseudonymization and retention controls; structured audit logging; atomic/versioned case storage; concurrency isolation; retries, timeouts, and idempotency; monitoring and cost controls; stable error codes; and integration with clinical identity, order, and approval systems.

The current normalization, reconciliation, timeline, audit, and post-exam Report packages are architectural placeholders. Provenance and deterministic guards reduce risk, but they do not replace clinical validation, operational governance, or qualified human approval.
