# Repository Guidelines

## Project Structure & Module Organization

Application code uses a `src` layout under `src/bulkinout/`. `core/` ingests documents and builds the shared `RadiologyCase`; `request/` applies the radiology reference workflow; `report/` is reserved for future post-exam work. Keep the dependency direction one-way: Request may import Core models, but Core must not depend on Request.

Clinical scenarios live in `reference/scenarios/*.yaml`, with catalog metadata in `reference/catalog.json`. Unit and deterministic integration tests are in `tests/test_*.py`; reference golden cases are in `tests/golden/`; manual, LLM-backed cases and their expected results are under `tests/e2e/`. Architecture and behavior documentation belongs in `docs/`, while radiologist review materials live in `review/`.

## Build, Test, and Development Commands

Create a local environment and install the package in editable mode:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run `pytest -q` for the deterministic suite with coverage (minimum 95%). Before committing, run `ruff check src tests`, `ruff format --check src tests`, `mypy`, and `python -m build`. Run `bulkinout request golden --cases tests/golden --reference reference/scenarios` to validate scenario rules without an LLM. Use `bulkinout request catalog` to inspect loaded scenarios. LLM-backed runs require `OPENAI_API_KEY` and `BULKINOUT_MODEL`; for example, `bulkinout request run --input input --output output`.

## Coding Style & Naming Conventions

Follow standard Python conventions: four-space indentation, `snake_case` for functions and modules, `PascalCase` for models, and uppercase names for constants. Type all source functions; strict mypy settings apply to `src/`. Use `pathlib.Path` for filesystem paths and typed JSON/reference structures instead of unconstrained dictionaries. Ruff owns linting, formatting, and a maximum cyclomatic complexity of 10 through `pyproject.toml`. Keep workflow rules deterministic and preserve provenance when transforming clinical facts.

## Testing Guidelines

Name tests `test_<behavior>` in `tests/test_*.py`. Any reference-rule correction should first gain a focused YAML golden case. Extraction changes should retain or add an E2E fixture plus `expected.json`; these cases make real API calls and are reviewed manually, not run by pytest. Ensure `pytest -q` preserves at least 95% coverage before submitting.

## Commit & Pull Request Guidelines

History is minimal and establishes no formal commit convention. Use short, imperative subjects such as `Add pregnancy guard for CT`. Keep commits focused. Pull requests should explain the clinical or technical motivation, list validation commands, link related issues, and call out reference-data changes. Include representative output diffs or review evidence for workflow changes.

## Security & Configuration

Never commit `.env`, API keys, generated `output*/` directories, or real patient data. The reference is marked `needs_local_validation`; do not present generated imaging decisions as autonomous clinical prescriptions, and preserve human approval gates.

## Language Policy

The repository uses English as its canonical technical language.

### English

Always use English for source code and identifiers; comments and docstrings; the README and technical documentation; tests, test names, and developer-facing fixtures; technical CLI help, errors, logs, and audit events; JSON/YAML keys and canonical values; rule and scenario metadata; and developer review templates. LLM prompts and instructions must also be in English unless another language is specifically required.

### French

Use French for clinical content presented directly to current end users: questions asked to clinicians, imaging and teleradiology request text, clinical summaries for French users, and synthetic French patient documents used as input fixtures. Treat French presentation text as content, not canonical internal data.

### Multilingual and Language-Agnostic Input

Clinical input is language-agnostic. Never assume source documents are French. Matching keywords and synonym dictionaries may be multilingual: preserve French clinical terms and add English or other synonyms when useful. Never derive a canonical representation from the source language.

### Canonical Data

Internal structured data uses stable English identifiers and values such as `right_lower_quadrant`, `pregnancy`, `iodinated_contrast_reaction`, and `pulmonary_embolism`. Do not store canonical concepts as translated presentation strings when a stable structured value is available.

### Agent Communication

Users may discuss the project in French. Respond in French unless requested otherwise, while applying this policy to repository files.

### Refactoring Safety

Do not translate or rename stable IDs, JSON keys, rule IDs, scenario IDs, or public interfaces solely for consistency. Language refactors must not change clinical behavior. After terminology, matching, scenario, or clinical-content changes:

1. Run the full automated test suite.
2. Run the golden cases.
3. Verify that multilingual clinical matching has not regressed.
