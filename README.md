# Bulkinout

![python](https://img.shields.io/badge/python-%E2%89%A53.11-blue)
[![license](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE.md)
[![CI](https://img.shields.io/github/actions/workflow/status/Thibescobar/bulkinout/ci.yml?branch=main&label=CI&logo=githubactions&logoColor=white)](https://github.com/Thibescobar/bulkinout/actions/workflows/ci.yml)
![tests](https://img.shields.io/badge/tests-65%20passed-brightgreen)
![coverage](https://img.shields.io/badge/coverage-96%25-brightgreen)
![linting](https://img.shields.io/badge/linting-ruff-7f54b3)

**Bulk in. Intelligence out.** Bulkinout turns heterogeneous clinical documents into an auditable radiology record, then combines a versioned reference, an LLM, and deterministic safeguards to prepare an imaging proposal and a teleradiology request.

![Bulkinout workflow overview](docs/images/bulkinout-overview.svg)

> **Decision support, not autonomous prescribing.** The v0 reference is marked `needs_local_validation`. Every prescription and transmission requires qualified human review.

## Why Bulkinout

Clinical information arrives across letters, emergency notes, laboratory results, prior reports, and images. Bulkinout creates one structured case while retaining the status and source of each fact. The Request workflow then:

- identifies matching radiology scenarios;
- asks only questions that may change the decision;
- compares candidate examinations;
- blocks unsafe or under-specified proposals;
- prepares a French clinical draft for human approval.

## What v0 supports

```text
PDF / TXT / Markdown / images
└── Bulkinout Core
    ├── multimodal extraction
    ├── canonical clinical facts
    ├── provenance and contradictions
    └── structured RadiologyCase
        ├── Request — available in v0
        │   ├── multilingual scenario matching
        │   ├── discriminating questions
        │   ├── proposal / abstention / clarification
        │   └── teleradiology request draft
        └── Report — standby
            └── future post-exam workflow
```

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env               # or export the variables manually
export OPENAI_API_KEY="..."
export BULKINOUT_MODEL="<compatible-model>"
```

Run the complete pre-exam workflow:

```bash
bulkinout request run --input input --output output
```

If the decision requires clarification, complete the generated `answers.template.json`, save it as `answers.json`, and rerun:

```bash
bulkinout request run \
  --input input \
  --answers answers.json \
  --output output_after_answers
```

## Command line

```text
bulkinout
├── core
│   └── structure     Structure documents without running Request
├── request
│   ├── run           Run the complete pre-exam workflow
│   ├── catalog       Inspect the configured scenarios
│   └── golden        Validate scenarios without an LLM
└── report            Display the Report standby notice
```

### Commands and arguments

| Command | Argument | Default | Purpose |
|---|---|---|---|
| `core structure` | `--input` | `input` | Directory scanned recursively for supported documents. |
|  | `--output` | `output` | Directory receiving Core JSON outputs. |
|  | `--model` | `BULKINOUT_MODEL` | Model used for structured extraction. |
| `request run` | `--input` | `input` | Directory containing the clinical source documents. |
|  | `--output` | `output` | Directory receiving all workflow outputs. |
|  | `--answers` | none | Optional JSON answers from a previous clarification pass. |
|  | `--reference` | `reference/scenarios` | Directory containing scenario YAML files. |
|  | `--model` | `BULKINOUT_MODEL` | Model used by Core and Request. |
| `request catalog` | `--reference` | `reference/scenarios` | Reference directory to summarize. |
| `request golden` | `--cases` | `tests/golden` | Directory containing deterministic golden cases. |
|  | `--reference` | `reference/scenarios` | Reference evaluated by the golden cases. |

`core structure` and `request run` require `OPENAI_API_KEY`. A command-line `--model` value overrides `BULKINOUT_MODEL`. Use `bulkinout COMMAND --help` and `bulkinout COMMAND SUBCOMMAND --help` for the current parser definition.

## Python integration

Bulkinout components can be imported from Python. The current component API is useful for experimentation and embedding Core or the reference engine, but it is not yet a stable public facade and there is no HTTP API.

```python
from pathlib import Path

from bulkinout.core.service import build_radiology_case
from bulkinout.request.reference_engine import ReferenceEngine

record, extraction, documents = build_radiology_case(
    Path("input"),
    model="<compatible-model>",
)

reference = ReferenceEngine(Path("reference/scenarios"))
reference_context = reference.build_context(record.clinical)

print(record.clinical.model_dump(mode="json"))
print(reference_context["matched_scenarios"])
```

This path requires `OPENAI_API_KEY` because Core calls the configured LLM. The complete Request orchestration currently lives in the CLI; applications that reproduce it manually must preserve the same decision guard and modality-specific safety checks.

## Generated outputs

| File | Purpose |
|---|---|
| `radiology_case.json` | Longitudinal container with clinical data, workflow products, artifacts, and audit events. |
| `llm_extraction.json` | Raw structured extraction returned by Core. |
| `case.json` | Current structured `ClinicalCase` view used by Request. |
| `reference_context.json` | Matched scenarios, candidate examinations, questions, and triggered rules. |
| `missing_questions.json` | Generic and modality-specific questions still requiring an answer. |
| `imaging_decision.json` | Candidate comparison, decision status, rationale, and approval readiness. |
| `teleradiology_request.json` | French clinical request draft awaiting human validation. |
| `answers.template.json` | Machine-readable template for a clarification pass. |

## Tests and validation

```bash
ruff check src tests
pytest -q
bulkinout request golden --cases tests/golden --reference reference/scenarios
```

Pytest enforces at least 95% coverage. Golden cases exercise the reference deterministically without an LLM. `tests/e2e/` contains synthetic multidocument records for manual testing with a real model; findings are recorded with the template in `review/`.

## Documentation

| Need | Document |
|---|---|
| Guided tour and reading paths | [`docs/README.md`](docs/README.md) |
| Components, data flow, boundaries, and invariants | [`docs/architecture.md`](docs/architecture.md) |
| Ingestion, extraction, provenance, and case construction | [`docs/core.md`](docs/core.md) |
| Models, statuses, and serialized data | [`docs/data-model.md`](docs/data-model.md) |
| Decision sequence, clarification, and safeguards | [`docs/request.md`](docs/request.md) |
| Scenario YAML, matching, rules, and authoring | [`docs/reference.md`](docs/reference.md) |
| Complete CLI behavior and troubleshooting | [`docs/cli.md`](docs/cli.md) |
| Development workflow and common change paths | [`docs/development.md`](docs/development.md) |
| Configuration, data handling, and safety boundaries | [`docs/operations.md`](docs/operations.md) |
| Automated, golden, and end-to-end testing | [`docs/testing.md`](docs/testing.md) |
| Module and function inventory | [`docs/code-reference.md`](docs/code-reference.md) |

## Language handling

Clinical input is language-agnostic. Internal keys and canonical values use English. French remains the presentation language for current clinical users and is preserved alongside English in matching synonym lists. The complete policy is recorded in [`AGENTS.md`](AGENTS.md).

## Limitations

- **LLM-dependent extraction and decision support:** results vary with the configured model and require representative evaluation; deterministic guards do not validate every clinical statement produced by the model.
- **No dedicated terminology normalization:** canonical field names are defined, but free-text concepts are not yet mapped through a controlled clinical terminology service.
- **Limited reconciliation and timeline logic:** contradictions are represented, but v0 has no specialized longitudinal merge engine or event timeline.
- **Reference scope and validation:** the bundled 18 scenarios are examples marked `needs_local_validation`, not a complete or locally approved imaging policy.
- **Simple reference paths:** matching reads first-level `section.field` values and does not traverse arbitrary nested clinical structures.
- **No stable application API:** Python components are importable, but the complete Request service is not exposed as a versioned facade and no HTTP API is provided.
- **No post-exam workflow:** `Report`, image-analysis integration, findings, impression, and final-report generation are placeholders.
- **Human approval is external:** v0 records readiness and warnings but does not implement authentication, signatures, persistent approval, or clinical-system integration.

## License

Apache-2.0; see [`LICENSE.md`](LICENSE.md).
