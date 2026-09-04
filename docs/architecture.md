# Architecture

## Purpose and boundaries

Bulkinout separates information extraction from radiology workflow decisions. Core creates a reusable longitudinal record; Request consumes that record for the pre-exam workflow; Report is reserved for future post-exam processing.

```mermaid
flowchart TB
    subgraph Inputs
        DOCS[PDF, TXT, Markdown, images]
        ANSWERS[Optional clarification answers]
        YAML[Versioned YAML scenarios]
    end

    subgraph Core
        INGEST[File discovery]
        EXTRACT[Structured LLM extraction]
        CASE[ClinicalCase construction]
    end

    RECORD[(RadiologyCase)]

    subgraph Request
        MATCH[Scenario matching]
        DECIDE[LLM candidate comparison]
        GUARD[Deterministic decision guard]
        SAFETY[Modality-specific checks]
        BUILD[Request builder]
    end

    REVIEW[Human clinical approval]
    REPORT[Report workflow — standby]

    DOCS --> INGEST --> EXTRACT --> CASE --> RECORD
    ANSWERS --> CASE
    YAML --> MATCH
    RECORD --> MATCH --> DECIDE --> GUARD --> SAFETY --> BUILD
    BUILD --> RECORD
    BUILD --> REVIEW
    RECORD -. future .-> REPORT
```

The architecture does not claim that an LLM output is trustworthy by itself. It makes model output explicit, typed, inspectable, and subject to deterministic state transitions and human review.

## Component responsibilities

### Core

Core owns document ingestion and clinical fact representation. It:

1. recursively discovers supported files;
2. sends text, images, and uploaded documents to the configured model;
3. validates the structured response as `LLMExtraction`;
4. maps recognized `section.field` facts into `ClinicalCase`;
5. stores artifacts and an audit event in `RadiologyCase`.

Core must not choose an examination. Keeping that boundary allows the same record to support Request today and Report later.

### Request

Request owns pre-exam decision support. It:

1. applies optional clinician answers as sourced observed facts;
2. identifies generic missing information;
3. matches up to three relevant reference scenarios;
4. asks an LLM to compare candidate examinations;
5. merges generic, required reference, model-generated, and modality-specific questions;
6. rejects a selected state when a required or blocking question is unresolved;
7. builds a French teleradiology request draft and a reproducibility manifest.

Request may import Core models. Core must never import Request. This one-way dependency prevents pre-exam rules from leaking into the shared clinical record.

### Report

`src/bulkinout/report/` currently contains no post-exam processing. The corresponding fields in `RadiologyCase` reserve space for acquisition metadata, AI results, radiologist observations, findings, impression, and a final report. Their presence is an architectural promise, not implemented behavior.

## LLM provider boundary

Application services depend on two structural protocols rather than a provider SDK:

```mermaid
flowchart LR
    CORE[Core service] --> EXTRACT[CoreExtractor]
    REQUEST[Request service] --> DECISION[RequestDecisionEngine]
    EXTRACT --> OPENAI_E[OpenAI extractor]
    EXTRACT -. injection .-> CUSTOM_E[Custom or local extractor]
    DECISION --> OPENAI_D[OpenAI decision engine]
    DECISION -. injection .-> CUSTOM_D[Custom or local decision engine]
```

`CoreExtractor` accepts source paths and returns `LLMExtraction`. `RequestDecisionEngine` accepts a `ClinicalCase`, unresolved questions, and `ReferenceContext`, then returns `ImagingDecision`. OpenAI is the built-in default, but Python callers may inject either component independently. Provider-specific transport, prompts, credentials, and response parsing stay inside adapters. Reference matching, deterministic guards, request construction, and human-approval boundaries remain in Bulkinout services and cannot be replaced through these interfaces.

## End-to-end sequence

```mermaid
sequenceDiagram
    actor Operator
    participant CLI
    participant Service as Request service
    participant Core
    participant Model as LLM provider
    participant Ref as ReferenceEngine
    participant Guard as Deterministic guards

    Operator->>CLI: request run --input ...
    CLI->>Service: run_request()
    Service->>Core: build_radiology_case()
    Core->>Model: documents + extraction schema
    Model-->>Core: LLMExtraction JSON
    Core-->>Service: CoreResult
    opt Answer file supplied
        Service->>Service: apply_answers()
    end
    Service->>Ref: build_context(ClinicalCase)
    Ref-->>Service: scenarios + questions + candidates + rules
    Service->>Model: case + reference context
    Model-->>Service: ImagingDecision JSON
    Service->>Guard: merge and enforce required questions
    Guard-->>Service: guarded decision
    Service->>Guard: add modality-specific checks
    Service->>Service: build_teleradiology_request()
    Service-->>CLI: RequestResult
    CLI-->>Operator: JSON outputs + manifest + status
```

If clarification is necessary, the operator completes `answers.template.json` and starts a new run with `--answers`. v0 does not maintain an interactive server-side session; the answer file is the handoff between passes.

A separate `request evaluate` command reads one saved run and its schema-v1 E2E expectations. It performs no model call and attributes structured assertion failures to Core or Request. The schema-v2 run manifest fingerprints the distributed Python source as well as the inputs and configured components, so changed safeguards cannot retain the same run identity. The evaluator does not turn synthetic assertions into clinical validation.

## Trust boundaries

| Boundary | Untrusted or variable side | Enforced side |
|---|---|---|
| Documents → extraction | Source format, wording, completeness | Supported extensions and Pydantic response schema |
| LLM → clinical case | Model interpretation and omissions | Typed fields, statuses, confidence, provenance |
| Reference → decision | Scenario scope and local suitability | Versioned YAML, deterministic matching, validation tests |
| LLM → selected state | Candidate reasoning | Required-question guard and modality-specific checks |
| Draft → clinical action | Generated wording and proposal | External qualified human approval |

Pydantic validation proves structural conformity, not clinical correctness. Golden cases prove encoded rule behavior, not guideline completeness. Human review remains a separate and mandatory boundary.

## Architectural invariants

The following rules should remain true across refactors:

- Missing information remains `unknown`; absence of mention is not converted to a negative fact.
- Every non-unknown extracted fact should carry provenance.
- Conflicting evidence is represented rather than silently resolved.
- Source language does not determine the canonical internal concept.
- French matching terms are preserved when English synonyms are added.
- Required unresolved discriminators prevent `selected` and approval-ready states.
- Unknown or conflicting facts are excluded from reliable request fields.
- Human validation is never inferred from successful program execution.
- Stable IDs and public data keys are not renamed for stylistic reasons.

## State and persistence

The shared output writer creates snapshots rather than using a database. The CLI calls it automatically; Python integrations may keep `RequestResult` in memory or call `write_request_outputs()`. `radiology_case.json` is the most complete object, while the other files expose intermediate stages for inspection and debugging.

```text
source documents       immutable input supplied by the operator
answer file            optional input for a later pass
output directory       replaceable run snapshot
radiology_case.json    aggregate record for that run
intermediate JSON      evidence for debugging and review
run_manifest.json      reproducibility fingerprints for that run
```

There is no concurrency control, durable workflow engine, identity model, or persistence service in v0. Production integration would need to define ownership, retention, access control, idempotency, and audit durability around these files.

## Extension points

- Add deterministic normalization behind `core/normalization/` without changing document ingestion.
- Add evidence reconciliation behind `core/reconciliation/` while preserving original provenance.
- Build a chronological view behind `core/timeline/` from dated facts and prior imaging.
- Add scenarios under `reference/scenarios/` with golden cases before changing matching behavior.
- Add an LLM provider by implementing `CoreExtractor` and/or `RequestDecisionEngine`; keep provider transport outside application services.
- Add an authenticated HTTP boundary around the public Python service only after defining request isolation, persistence, and operational error contracts.
- Implement Report against `RadiologyCase` without importing Request-specific behavior into Core.
