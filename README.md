# BULKINOUT

![python](https://img.shields.io/badge/python-%E2%89%A53.11-blue)
[![license](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE.md)
[![CI](https://img.shields.io/github/actions/workflow/status/Thibescobar/bulkinout/ci.yml?branch=main&label=CI&logo=githubactions&logoColor=white)](https://github.com/Thibescobar/bulkinout/actions/workflows/ci.yml)
![tests](https://img.shields.io/badge/tests-65%20passed-brightgreen)
![coverage](https://img.shields.io/badge/coverage-96%25-brightgreen)
![linting](https://img.shields.io/badge/linting-ruff-7f54b3)

**Bulk in. Intelligence out.** BULKINOUT transforms heterogeneous clinical documents into a structured radiology record, then uses a radiology reference and an LLM to prepare an imaging proposal and a teleradiology request.

> **v0 is a decision-support proof of concept.** The reference is marked `needs_local_validation`; every prescription and transmission remains subject to human approval.

## What v0 Supports

```text
PDF / TXT / images
        ↓
BULKINOUT Core
        ↓
Structured RadiologyCase + provenance
        ↓
BULKINOUT Request
        ↓
scenarios + discriminating questions
        ↓
proposal / abstention / clarification
        ↓
teleradiology request draft
```

`Report`, the post-exam workflow, is reserved for a later release.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env               # or export the variables manually
export OPENAI_API_KEY="..."
export BULKINOUT_MODEL="<compatible-model>"
```

v0 deliberately does not pin an LLM: configure it with `BULKINOUT_MODEL` or `--model`.

## Usage

Structure documents without running the Request workflow:

```bash
bulkinout core structure --input input --output output_core
```

Run the complete pre-exam workflow:

```bash
bulkinout request run   --input input   --output output   --reference reference/scenarios
```

If clarification is required, complete the generated `answers.template.json` and rerun:

```bash
bulkinout request run   --input input   --answers answers.json   --output output_after_answers
```

Inspect the reference or run deterministic domain tests:

```bash
bulkinout request catalog
bulkinout request golden
pytest -q
```

## Main Outputs

| File | Purpose |
|---|---|
| `radiology_case.json` | Main longitudinal object. |
| `case.json` | Structured clinical context extracted from documents. |
| `reference_context.json` | Scenarios, candidates, questions, and reference rules. |
| `imaging_decision.json` | Assisted decision, candidates, rationale, and clarification status. |
| `teleradiology_request.json` | Draft awaiting human approval. |
| `answers.template.json` | Discriminating questions to complete when needed. |

## Included Tests

- `tests/golden/`: fast reference tests that make **no LLM calls**.
- `tests/e2e/`: realistic synthetic patient records for manual full-pipeline testing.
- `review/`: radiologist review template.

## Documentation

Start with **[`docs/README.md`](docs/README.md)**. It covers the architecture, data model, Core, Request, reference, tests, and v0 code surface.

## Language Handling

Clinical input is language-agnostic. The extraction layer must not assume French source documents. Internal keys and canonical values use English, while French is retained for clinical text presented to current users and for French matching synonyms.

## Known Limitations

Advanced terminology normalization, dedicated reconciliation, the clinical timeline, and the `Report` workflow remain architectural placeholders. The current Core relies mainly on structured LLM extraction and document provenance. The v0 reference must be reviewed and validated locally before any real clinical use.
