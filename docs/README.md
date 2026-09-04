# BULKINOUT v0 Documentation

This documentation describes the code that is actually present in v0. Components that are not implemented are explicitly identified.

1. [Architecture](architecture.md) — Core, Request, and Report responsibilities.
2. [Data model](data-model.md) — `RadiologyCase`, `ClinicalCase`, decisions, and provenance.
3. [BULKINOUT Core](core.md) — file ingestion, multimodal extraction, and case construction.
4. [BULKINOUT Request](request.md) — reference data, decision logic, safeguards, and final request.
5. [Reference](reference.md) — YAML format and reference-engine behavior.
6. [Tests](testing.md) — pytest, golden cases, and synthetic E2E fixtures.
7. [CLI](cli.md) — commands, arguments, and generated files.
8. [Code reference](code-reference.md) — v0 modules, classes, and functions.

## v0 Boundaries

`core/normalization/`, `core/reconciliation/`, `core/timeline/`, `core/audit/`, and `report/` stabilize the architecture but do not yet contain substantial domain logic. The active audit mechanism is `RadiologyCase.audit`, populated by `core.service` and the Request CLI.
