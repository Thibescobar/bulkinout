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

Run `pytest -q` for the deterministic suite with coverage (minimum 95%). Run `ruff check src tests` before committing. Run `bulkinout request golden --cases tests/golden --reference reference/scenarios` to validate scenario rules without an LLM. Use `bulkinout request catalog` to inspect loaded scenarios. LLM-backed runs require `OPENAI_API_KEY` and `BULKINOUT_MODEL`; for example, `bulkinout request run --input input --output output`.

## Coding Style & Naming Conventions

Follow standard Python conventions: four-space indentation, `snake_case` for functions and modules, `PascalCase` for Pydantic models, and uppercase names for constants. Add type hints to new public functions and use `pathlib.Path` for filesystem paths. Keep workflow rules deterministic where possible and preserve provenance when transforming clinical facts. Ruff is configured in `pyproject.toml`; keep imports grouped and changes consistent with nearby code.

## Testing Guidelines

Name tests `test_<behavior>` in `tests/test_*.py`. Any reference-rule correction should first gain a focused YAML golden case. Extraction changes should retain or add an E2E fixture plus `expected.json`; these cases make real API calls and are reviewed manually, not run by pytest. Ensure `pytest -q` preserves at least 95% coverage before submitting.

## Commit & Pull Request Guidelines

History is minimal and establishes no formal commit convention. Use short, imperative subjects such as `Add pregnancy guard for CT`. Keep commits focused. Pull requests should explain the clinical or technical motivation, list validation commands, link related issues, and call out reference-data changes. Include representative output diffs or review evidence for workflow changes.

## Security & Configuration

Never commit `.env`, API keys, generated `output*/` directories, or real patient data. The reference is marked `needs_local_validation`; do not present generated imaging decisions as autonomous clinical prescriptions, and preserve human approval gates.
