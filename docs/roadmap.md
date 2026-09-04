# Roadmap and remediation plan

## Purpose

This document orders the work required to turn the current Request proof of concept into a reliable and evaluable system. It combines confirmed defects, known v0 limitations, clinical-assurance requirements, operational gaps, and future product work. Priorities express dependency and risk, while status records whether work belongs to the current proof-of-concept scope.

The following foundations are already in place and should be preserved: strict typing, Ruff and mypy checks, deterministic tests with a coverage floor, golden cases, package builds, a public Python service, provider-neutral LLM interfaces, separate extraction and decision models, provenance, and mandatory human review.

## Scope and status

- **Active**: required to correct or distribute the current Request proof of concept.
- **Completed**: implemented and checked against the milestone exit criteria.
- **Next**: follows the active work and provides minimum evidence for model-backed behavior.
- **Gate**: required before the named use, but not necessarily implemented during the current synthetic-data proof of concept.
- **Standby**: deliberately deferred until Request correctness and evaluation are established.
- **Optional**: implemented only when a demonstrated need justifies it.

The current implementation scope is R01–R04. R05 and R06 define gates for clinical claims and real patient data. R07–R15 remain on standby unless the scope is explicitly changed.

## Work register

| ID | Issue | Category | Priority | Status | Planned milestone |
|---|---|---|---|---|---|
| R01 | Short acronyms can match unrelated substrings, such as `EP` in `sepsis` | Correctness defect | P0 | Completed | Reference integrity |
| R02 | Material YAML questions can be omitted by the LLM and escape deterministic guards | Safety defect | P0 | Completed | Reference integrity |
| R03 | Installed packages contain no default scenarios and accept an empty reference silently | Distribution defect | P0 | Completed | Package integrity |
| R04 | Real-model behavior is assessed mainly through manual E2E review | Assurance limitation | P1 | Active | Evaluation and governance |
| R05 | The 18 bundled scenarios are not locally validated or comprehensive | Clinical-governance limitation | P1 | Gate before clinical claims | Evaluation and governance |
| R06 | OpenAI uploads have no application-managed deletion, pseudonymization, or retention policy | Data-governance gate | P1 | Gate before real patient data | Data lifecycle |
| R07 | No ready-to-use local LLM adapter is included | Provider capability | P1 | Standby, optional | Provider evaluation |
| R08 | Free text is not mapped through deterministic terminology normalization | Domain limitation | P2 | Standby | Clinical data foundations |
| R09 | Reconciliation, contradiction handling, and chronology remain limited | Domain limitation | P2 | Standby | Clinical data foundations |
| R10 | Reference paths support only simple first-level `section.field` access | Domain limitation | P2 | Standby, conditional | Clinical data foundations |
| R11 | File snapshots are not atomic, versioned, locked, or concurrency-safe | Operational limitation | P3 | Standby | Runtime foundations |
| R12 | Logging, retries, timeouts, monitoring, cost controls, and stable error codes are incomplete | Operational limitation | P3 | Standby | Runtime foundations |
| R13 | No authenticated HTTP service, durable workflow state, or clinical-system integration exists | Platform limitation | P3 | Standby | Service boundary |
| R14 | Human approval is external and has no persisted identity or signature | Integration limitation | P3 | Standby | Approval boundary |
| R15 | Report and post-exam processing are placeholders | Product roadmap | P4 | Standby | Report |

## P0 — Stabilize Request

P0 work corrects current behavior. It must precede new clinical features, provider expansion, logging, an HTTP API, or Report.

### Reference integrity

1. Introduce explicit matching semantics for normalized equality, whole tokens or acronyms, phrases, and intentionally partial stems.
2. Migrate ambiguous short terms such as `EP`, `AVC`, `RLQ`, and `RUQ` without weakening useful multilingual stems such as `appendic`, `lithi`, or `spondylodisc`.
3. Add positive and negative French and English regression cases. `sepsis` must not match pulmonary embolism, while genuine `EP` inputs must continue to match.
4. Extend reference-question metadata to distinguish:
   - `material`: may alter the decision;
   - `required_to_choose`: must be known before selection;
   - `blocking`: unresolved safety condition.
5. Convert required reference questions into deterministic `MissingQuestion` objects. The LLM may add questions or presentation detail, but it must not be able to remove a required constraint.
6. Deduplicate generic, reference, LLM-generated, and modality-specific questions by canonical field while preserving the strongest requirement.

Exit criteria:

- adversarial or empty decision-engine output cannot bypass required questions;
- matching regression tests include ambiguous acronyms and multilingual positives;
- selected and approval-ready states are derived consistently from explicit reference semantics;
- all existing stable scenario IDs, rule IDs, and public JSON keys remain unchanged.

### Package integrity

1. Include the default scenarios and catalog in wheel and source distributions.
2. Resolve the packaged reference with `importlib.resources`; keep `--reference` and `reference_dir=` as explicit overrides.
3. Raise `ReferenceDataError` when a requested reference is missing, unreadable, or empty instead of reporting zero scenarios.
4. Smoke-test the installed wheel from outside the repository.

Exit criteria:

- `bulkinout request catalog` finds all 18 packaged scenarios from an unrelated working directory;
- an invalid override fails clearly;
- CLI, Python API, build metadata, README, and reference documentation agree on resolution rules.

## P1 — Establish evidence and governance

### Model evaluation

1. Build an evaluation runner that measures Core extraction and Request decision behavior separately.
2. Record provider, model, prompt revision, schema revision, reference version, inputs, and structured outcomes for every run.
3. Use clinical assertions and tolerances rather than exact equality for variable prose.
4. Expand synthetic E2E coverage for omissions, contradictions, multilingual documents, unsafe selections, abstention, and French presentation quality.
5. Keep pull-request CI deterministic. Run real-model evaluations on demand or on a controlled schedule and archive comparable reports.

Exit criteria:

- a model or prompt change produces a reviewable before/after report;
- extraction and decision failures are attributed to their owning stage;
- a green deterministic CI run is never presented as proof of clinical model quality.

### Reference governance

1. Assign clinical ownership and review the 18 scenarios against local practice.
2. Record reviewer, evidence, date, scope, version, and limitations.
3. Change `needs_local_validation` only through an explicit approval process.
4. Expand scenario coverage only after the validation workflow and negative golden cases exist.

### Data lifecycle

Before any real patient data is accepted:

1. inventory every local and provider-side data copy;
2. track uploaded file identifiers and define cleanup behavior for success and failure paths;
3. add an approved minimization or pseudonymization boundary before provider transport;
4. define retention, encryption, regional processing, access control, incident handling, and operator responsibilities;
5. document equivalent boundaries for custom and local providers.

Until these controls exist, development and evaluation must use synthetic data only.

### Provider evaluation

A concrete Ollama, llama.cpp, vLLM, or other local adapter is optional rather than a prerequisite for Request stabilization. Add the first adapter only after the evaluation runner exists, then subject it to the same schemas, clinical assertions, and safety guards as the default OpenAI components.

## P2 — Strengthen clinical data foundations

### Terminology normalization

Introduce deterministic canonicalization behind `core/normalization/`. Preserve original wording and provenance while mapping recognized concepts to stable English identifiers and values. Multilingual synonyms must add recognition capacity rather than replace French terms.

This work is separate from the P0 substring defect: P0 fixes incorrect matching immediately; P2 builds broader terminology capability.

### Reconciliation and timeline

Implement evidence-aware reconciliation behind `core/reconciliation/` and chronological views behind `core/timeline/`. Equivalent observations may be grouped, but conflicting evidence must remain visible and source-grounded. Do not silently select one source as truth.

### Reference paths

Add a typed nested-path resolver only when the clinical model requires nested structures. Do not generalize traversal pre-emptively; preserve explicit allowed roots and safe handling of missing, unknown, and conflicting values.

## P3 — Build runtime and service foundations

Work in this milestone remains intentionally deferred until Request correctness and assurance are established.

1. Add structured logging, correlation IDs, provider timing, token or cost measurements, and auditable event names without logging clinical content by default.
2. Define stable application error codes, timeouts, bounded retries, cancellation, and idempotency rules.
3. Replace sequential overwrite-only snapshots with atomic, versioned, concurrency-safe persistence.
4. Define case ownership, workflow state, retention, and recovery behavior.
5. Add an authenticated HTTP boundary only after persistence and isolation contracts are stable.
6. Integrate identity, authorization, clinical-system transport, and a persisted approval record.

Human approval remains an invariant. The goal is to authenticate and retain evidence of approval, not to automate it away.

## P4 — Implement Report

Report begins only after the shared case, assurance, and runtime boundaries are stable.

1. Define post-exam inputs, outputs, ownership, and non-goals.
2. Validate the reserved acquisition, AI-result, observation, finding, impression, and final-report structures.
3. Specify provenance, disagreement, amendment, and human-approval behavior.
4. Design Report-specific evaluation cases and deterministic safeguards.
5. Implement the workflow without importing Request-specific behavior into Core.

Until then, Report remains an explicitly documented architectural placeholder.

## Delivery sequence

```text
P0  reference integrity
 └─ package integrity
     └─ P1 model evaluation + reference governance
         ├─ data lifecycle gate
         └─ optional local-provider evaluation
             └─ P2 terminology + reconciliation + timeline
                 └─ P3 logging + persistence + HTTP + approval integration
                     └─ P4 Report
```

Suggested branch sequence:

1. `fix/reference_integrity`
2. `fix/reference_packaging`
3. `quality/llm_evaluation`
4. `security/data_lifecycle`
5. `feature/clinical_normalization`
6. `feature/runtime_operations`
7. `feature/report`

## Definition of done

Every milestone change must:

1. preserve the repository language policy and stable interfaces unless a reviewed migration is necessary;
2. add focused unit tests and golden cases before changing clinical matching or rules;
3. exercise French and English recognition without assuming the source language;
4. run Ruff, formatting, strict mypy, the full pytest suite, package build, installed-wheel smoke test, and all golden cases;
5. update README, architecture, operations, testing, and code-reference documentation where behavior changes;
6. state whether clinical behavior changed and identify the evidence used to validate it.
