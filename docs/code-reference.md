# Code Reference

This inventory describes the public services and the private helpers that define workflow behavior.

## `bulkinout`

Source: `src/bulkinout/__init__.py`

The public Python facade exports `build_radiology_case()`, `run_request()`, `run_request_from_core()`, provider-neutral `CoreExtractor` and `RequestDecisionEngine` protocols, output writers, and the `BulkinoutError` hierarchy. Lightweight wrappers defer provider imports until an LLM-backed service is actually called; returned objects remain fully typed.

## `bulkinout.errors` and `bulkinout.types`

`errors.py` defines expected configuration, input, and reference-data failures under `BulkinoutError`. `types.py` defines recursive JSON-compatible values used instead of unconstrained application dictionaries. Provider response objects remain an explicit dynamic boundary.

## `bulkinout.cli`

Source: `src/bulkinout/cli.py`

### `cmd_core_structure(args)`

Runs only Core and writes its two JSON outputs.

### `cmd_request_run(args)`

Calls the Request service, optionally runs one local browser clarification round, writes every request output, and displays final statuses plus actionable file-based guidance for unresolved required questions.

### `cmd_request_golden(args)`

Runs golden cases and exits with a nonzero status when a case fails.

### `cmd_request_catalog(args)`

Prints summarized scenario catalog metadata.

### `cmd_request_evaluate(args)`

Evaluates saved E2E artifacts, reports Core and Request independently, and optionally writes JSON results.

### `build_parser() -> argparse.ArgumentParser`

Builds the parser independently for help rendering and tests.

### `main(argv: Sequence[str] | None = None)`

Dispatches subcommands and renders expected `BulkinoutError` failures without a traceback.

## `bulkinout.output`

Source: `src/bulkinout/output.py`

### `write_json(path: Path, payload: JsonValue)`

Writes one indented UTF-8 JSON value, creating parent directories.

### `write_core_outputs(result: CoreResult, output_dir: Path)`

Writes `radiology_case.json` and `llm_extraction.json`.

### `write_request_outputs(result: RequestResult, output_dir: Path)`

Writes ten documented JSON snapshots plus the self-contained HTML radiology handoff, including the answer template and run manifest.

## `bulkinout.clarification_browser`

Source: `src/bulkinout/clarification_browser.py`

### `collect_clinician_answers(questions, *, timeout_seconds=600) -> BrowserClarification | None`

Runs one browser form on a random loopback port with a single-use token. It returns typed answers or direct-escalation intent and returns `None` after browser failure or timeout.

### `next_interactive_answer_path(output_dir: Path) -> Path`

Selects the first unused `answers.interactive.N.json` path.

### `write_interactive_answers(path: Path, answer_file: AnswerFile)`

Creates a new UTF-8 answer file without overwriting an existing one and requests owner-only permissions.

## `bulkinout.evaluation`

Source: `src/bulkinout/evaluation.py`

### `E2EExpectations`

Strict schema-v1 model for Core and Request assertions stored in `tests/e2e/*/expected.json`. Request assertions can require all or any named scenarios and explicitly reject forbidden matches.

### `EvaluationReport`

Contains separately attributed Core and Request check counts and assertion failures.

### `evaluate_e2e_case(case_dir: Path, run_dir: Path) -> EvaluationReport`

Validates saved artifacts and applies structured assertions without invoking an LLM.

## `bulkinout.run_manifest`

Source: `src/bulkinout/run_manifest.py`

### `RunManifest`

Schema-v2 technical fingerprints for one Request run: package version, distributed Python source, inputs, components, prompts, schemas, reference revision, and matched scenarios.

### `build_run_manifest(...) -> RunManifest`

Builds stable SHA-256 metadata without retaining prompt or source-document contents.

## `bulkinout.fingerprints`

Source: `src/bulkinout/fingerprints.py`

Workflow-neutral SHA-256 helpers used by Core adapters and Request run manifests. Keeping these helpers independent prevents Core from importing Request-specific manifest types.

## `bulkinout.core.extraction.llm`

Source: `src/bulkinout/core/extraction/llm.py`

### `_schema_format(model: type[T]) -> JsonObject`

Builds the `json_schema` configuration used for structured output.

### `_extract_json(response) -> str`

Retrieves JSON text from an SDK response, with a fallback over output content blocks.

### `OpenAICoreExtractor`

Service class whose methods are documented below.

### `OpenAICoreExtractor.__init__(self, model: str | None = None)`

Initializes the OpenAI client and resolves the extraction model from the argument, `BULKINOUT_EXTRACTION_MODEL`, or `BULKINOUT_MODEL`.

### `OpenAICoreExtractor._call_structured(self, prompt: str, content: list[JsonObject], model_cls: type[T]) -> T`

Calls the Responses API with a strict Pydantic schema and validates the response.

### `OpenAICoreExtractor._upload_or_inline(self, path: Path) -> JsonObject`

Encodes images as data URLs and uploads other files as `input_file` content.

### `OpenAICoreExtractor.extract(self, paths: list[Path]) -> LLMExtraction`

Builds multimodal input from all files and returns an `LLMExtraction`.

### `extraction_to_case(extraction: LLMExtraction) -> ClinicalCase`

Converts `LLMExtraction` into a `ClinicalCase`, including provenance and prior imaging.

## `bulkinout.core.interfaces`

Source: `src/bulkinout/core/interfaces.py`

### `CoreExtractor`

Protocol for components that expose `name` and `model`, accept source paths, and return `LLMExtraction`.

## `bulkinout.core.ingestion.files`

Source: `src/bulkinout/core/ingestion/files.py`

### `collect_files(input_dir: Path) -> list[Path]`

Recursively collects files whose extension is listed in `SUPPORTED`.

## `bulkinout.core.models.case`

Source: `src/bulkinout/core/models/case.py`

### `FieldStatus`

Pydantic model or enum described in [Data Model](data-model.md).

### `SourceRef`

Pydantic model or enum described in [Data Model](data-model.md).

### `ClinicalField`

Pydantic model or enum described in [Data Model](data-model.md).

### `PriorImaging`

Pydantic model or enum described in [Data Model](data-model.md).

### `ClinicalCase`

Pydantic model or enum described in [Data Model](data-model.md).

### `ArtifactRef`

Pydantic model or enum described in [Data Model](data-model.md).

### `WorkflowState`

Pydantic model or enum described in [Data Model](data-model.md).

### `RadiologyCase`

Pydantic model or enum described in [Data Model](data-model.md).

### `MissingQuestion`

Pydantic model or enum described in [Data Model](data-model.md).

### `CandidateExam`

Pydantic model or enum described in [Data Model](data-model.md).

### `DiscriminatingQuestion`

Pydantic model or enum described in [Data Model](data-model.md).

### `ImagingRecommendation`

Pydantic model or enum described in [Data Model](data-model.md).

### `ImagingDecision`

Pydantic model or enum described in [Data Model](data-model.md).

### `TeleradiologyRequest`

Pydantic model or enum described in [Data Model](data-model.md).

### `LLMSource`

Pydantic model or enum described in [Data Model](data-model.md).

### `LLMFact`

Pydantic model or enum described in [Data Model](data-model.md).

### `LLMExtraction`

Pydantic model or enum described in [Data Model](data-model.md).

### `AnswerItem`

Pydantic model or enum described in [Data Model](data-model.md).

### `AnswerFile`

Pydantic model or enum described in [Data Model](data-model.md).

## `bulkinout.core.service`

Source: `src/bulkinout/core/service.py`

### `CoreResult`

Typed, tuple-compatible Core result containing the radiology case, extraction, and source paths.

### `build_radiology_case(input_dir: Path, model: str | None = None, *, extractor: CoreExtractor | None = None) -> CoreResult`

Builds a `RadiologyCase` from a document directory through the default OpenAI extractor or an injected implementation.

## `bulkinout.request.answers`

Source: `src/bulkinout/request/answers.py`

### `load_answers(path: Path) -> AnswerFile`

Loads an answer file in either dictionary or list form.

### `apply_answers(case: ClinicalCase, answer_file: AnswerFile, filename: str) -> ClinicalCase`

Adds non-empty answers to the `ClinicalCase` as sourced observed facts and records clarification metadata. Boolean `false` and numeric `0` remain valid; null and blank strings remain unresolved.

## `bulkinout.request.clarification`

Source: `src/bulkinout/request/clarification.py`

### `required_clarification_questions(questions: list[MissingQuestion]) -> list[MissingQuestion]`

Returns required or blocking questions in a stable clinical priority order. The CLI and answer-template writer share this selector.

## `bulkinout.request.handoff`

Source: `src/bulkinout/request/handoff.py`

### `RadiologyHandoff`

Schema-v1 remote-review package containing the request, proposal or escalation state, sourced facts, safety facts, clarification trace, unresolved questions, decision trace, and scenario-level citations.

### `build_radiology_handoff(...) -> RadiologyHandoff`

Builds the review package without converting model output or reference background into clinical approval.

### `render_radiology_handoff_html(handoff: RadiologyHandoff) -> str`

Produces an escaped, self-contained French review page. Blocked states display any retained model examination only as considered and not proposed.

## `bulkinout.request.decision_guard`

Source: `src/bulkinout/request/decision_guard.py`

### `_get_case_value(case: ClinicalCase, field_path: str)`

Reads a `section.field` path and reports whether it is unknown or conflicting.

### `enforce_decision_guard(case: ClinicalCase, decision: ImagingDecision) -> ImagingDecision`

Blocks a selection when a required discriminating question remains unanswered.

## `bulkinout.request.decision_llm`

Source: `src/bulkinout/request/decision_llm.py`

### `_schema_format(model: type[T]) -> JsonObject`

Builds the structured output format for `ImagingDecision`.

### `_extract_json(response) -> str`

Extracts JSON text from the decision-engine response.

### `OpenAIRequestDecision`

Service class whose methods are documented below.

### `OpenAIRequestDecision.__init__(self, model: str | None = None)`

Initializes the OpenAI client and resolves the decision model from the argument, `BULKINOUT_DECISION_MODEL`, or `BULKINOUT_MODEL`.

### `OpenAIRequestDecision.decide(self, case: ClinicalCase, missing_questions: list[JsonObject], reference_context: ReferenceContext | None = None) -> ImagingDecision`

Sends the case, questions, and reference data to the LLM and validates an `ImagingDecision`.

## `bulkinout.request.interfaces`

Source: `src/bulkinout/request/interfaces.py`

### `RequestDecisionEngine`

Protocol for components that turn a clinical case, unresolved questions, and reference context into `ImagingDecision`.

## `bulkinout.request.golden`

Source: `src/bulkinout/request/golden.py`

### `_observed(value)`

Creates an observed `ClinicalField` with confidence 1 for tests.

### `case_from_facts(facts: JsonObject) -> ClinicalCase`

Converts YAML `section.field` facts into a `ClinicalCase`.

### `GoldenResult`

Dataclass containing a golden-case result.

### `run_golden_case(path: Path, reference_dir: Path | None = None) -> GoldenResult`

Runs one golden case against the `ReferenceEngine` and returns the differences.

### `discover_golden_cases(case_dir: Path) -> list[Path]`

Recursively discovers golden-case YAML files.

## `bulkinout.request.reference_catalog`

Source: `src/bulkinout/request/reference_catalog.py`

### `build_catalog(reference_dir: Path | None = None) -> list[CatalogEntry]`

Produces summarized metadata for every scenario YAML file.

## `bulkinout.request.reference_resources`

Source: `src/bulkinout/request/reference_resources.py`

### `load_reference_documents(reference_dir: Path | None) -> list[tuple[str, str]]`

Reads an explicit scenario directory or the packaged default as named YAML documents. Missing, empty, or unreadable references raise `ReferenceDataError`.

## `bulkinout.request.reference_engine`

Source: `src/bulkinout/request/reference_engine.py`

### `ScenarioMatch`

Dataclass representing a matched scenario and its score.

### `_raw(case: ClinicalCase, field: str)`

Reads a known `ClinicalField` from a `section.field` path.

### `_predicate(case: ClinicalCase, pred: Predicate) -> bool`

Evaluates a YAML predicate against a known clinical value. Supported operators include equality, substring, boundary-aware term, and membership checks.

### `_condition(case: ClinicalCase, node: Condition) -> bool`

Evaluates an `all` or `any` predicate group.

### `_candidate_applicable(case: ClinicalCase, candidate: ReferenceCandidate) -> bool`

Evaluates a candidate's optional `when` clause.

### `ReferenceEngine`

Service class whose methods are documented below.

### `ReferenceEngine.__init__(self, reference_dir: Path | None = None)`

Loads all scenario YAML files from an explicit directory or from the packaged reference by default. Missing, unreadable, invalid, or empty references raise `ReferenceDataError`.

### `ReferenceEngine.match(self, case: ClinicalCase) -> list[ScenarioMatch]`

Returns scenarios whose entry criteria match, ordered by score.

### `ReferenceEngine.unresolved_material_questions(self, case: ClinicalCase, scenario: ReferenceScenario) -> list[ReferenceQuestion]`

Returns material, required, or blocking questions whose field is still unknown.

### `ReferenceEngine.evaluate_rules(self, case: ClinicalCase, scenario: ReferenceScenario) -> list[TriggeredRule]`

Evaluates a scenario's conditional rules.

### `ReferenceEngine.build_context(self, case: ClinicalCase, max_scenarios: int = 3) -> ReferenceContext`

Builds the decision-engine context from scenarios, filtered candidates, questions, and rules.

## `bulkinout.request.request_builder`

Source: `src/bulkinout/request/request_builder.py`

### `_clean_value(section, key)`

Returns only the value of a known, nonconflicting field.

### `build_teleradiology_request(case: ClinicalCase, decision: ImagingDecision, questions: list[MissingQuestion]) -> TeleradiologyRequest`

Assembles the request draft from the case, decision, and questions.

## `bulkinout.request.rules`

Source: `src/bulkinout/request/rules.py`

### `_unknown(section: dict[str, ClinicalField], key: str) -> bool`

Checks whether a clinical field is absent, unknown, or conflicting.

### `pregnancy_is_relevant(case: ClinicalCase) -> bool`

Applies the shared conservative demographic rule used by reference and modality questions.

### `generic_missing_questions(case: ClinicalCase) -> list[MissingQuestion]`

Generates generic indication and symptom checks.

### `recommendation_specific_questions(case: ClinicalCase, decision: ImagingDecision) -> list[MissingQuestion]`

Adds safety and completeness checks specific to the proposed modality.

## `bulkinout.request.service`

Source: `src/bulkinout/request/service.py`

### `RequestResult`

Slot-based dataclass containing every in-memory artifact of one Request run, including the optional run manifest and radiology handoff.

### `run_request(input_dir: Path, *, reference_dir: Path | None = None, model: str | None = None, extraction_model: str | None = None, decision_model: str | None = None, answers_path: Path | None = None, extractor: CoreExtractor | None = None, decision_engine: RequestDecisionEngine | None = None) -> RequestResult`

Executes Core, optional answers, matching, model decision, deterministic guards, request construction, and audit updates. The packaged reference is used when no override is supplied. Custom LLM components replace only extraction or candidate comparison. The service performs no output writes.

### `run_request_from_core(core_result: CoreResult, *, reference_dir: Path | None = None, model: str | None = None, decision_model: str | None = None, answers_path: Path | None = None, decision_engine: RequestDecisionEngine | None = None) -> RequestResult`

Deep-copies one Core baseline and executes Request without document discovery, upload, or extraction. This is the in-process resumption boundary used by interactive clarification.
