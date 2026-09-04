# Code Reference

This inventory was generated from the v0 AST and then annotated. Private functions (`_...`) are documented when they contribute to the proof-of-concept behavior.

## `bulkinout.cli`

Source: `src/bulkinout/cli.py`

### `_dump(path: Path, payload)`

Serializes a Python payload as indented UTF-8 JSON and creates the parent directory.

### `cmd_core_structure(args)`

Runs only Core and writes its two JSON outputs.

### `_write_answer_template(output_dir: Path, decision)`

Writes required discriminating questions to `answers.template.json`.

### `cmd_request_run(args)`

Orchestrates the Core and Request pipeline and writes every request output.

### `cmd_request_golden(args)`

Runs golden cases and exits with a nonzero status when a case fails.

### `cmd_request_catalog(args)`

Prints summarized scenario catalog metadata.

### `main()`

Builds the argparse parser and dispatches subcommands.

## `bulkinout.core.extraction.llm`

Source: `src/bulkinout/core/extraction/llm.py`

### `_schema_format(model: type[T]) -> dict`

Builds the `json_schema` configuration used for structured output.

### `_extract_json(response) -> str`

Retrieves JSON text from an SDK response, with a fallback over output content blocks.

### `OpenAICoreExtractor`

Service class whose methods are documented below.

### `OpenAICoreExtractor.__init__(self, model: str | None = None)`

Initializes the OpenAI client and resolves the configured model.

### `OpenAICoreExtractor._call_structured(self, prompt: str, content: list[dict], model_cls: type[T]) -> T`

Calls the Responses API with a strict Pydantic schema and validates the response.

### `OpenAICoreExtractor._upload_or_inline(self, path: Path) -> dict`

Encodes images as data URLs and uploads other files as `input_file` content.

### `OpenAICoreExtractor.extract(self, paths: list[Path]) -> LLMExtraction`

Builds multimodal input from all files and returns an `LLMExtraction`.

### `extraction_to_case(extraction: LLMExtraction) -> ClinicalCase`

Converts `LLMExtraction` into a `ClinicalCase`, including provenance and prior imaging.

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

### `build_radiology_case(input_dir: Path, model: str | None = None)`

Builds a `RadiologyCase` from a document directory through the Core extractor.

## `bulkinout.request.answers`

Source: `src/bulkinout/request/answers.py`

### `load_answers(path: Path) -> AnswerFile`

Loads an answer file in either dictionary or list form.

### `apply_answers(case: ClinicalCase, answer_file: AnswerFile, filename: str) -> ClinicalCase`

Adds answers to the `ClinicalCase` as sourced observed facts.

## `bulkinout.request.decision_guard`

Source: `src/bulkinout/request/decision_guard.py`

### `_get_case_value(case: ClinicalCase, field_path: str)`

Reads a `section.field` path and reports whether it is unknown or conflicting.

### `enforce_decision_guard(case: ClinicalCase, decision: ImagingDecision) -> ImagingDecision`

Blocks a selection when a required discriminating question remains unanswered.

## `bulkinout.request.decision_llm`

Source: `src/bulkinout/request/decision_llm.py`

### `_schema_format(model: type[T]) -> dict`

Builds the structured output format for `ImagingDecision`.

### `_extract_json(response) -> str`

Extracts JSON text from the decision-engine response.

### `OpenAIRequestDecision`

Service class whose methods are documented below.

### `OpenAIRequestDecision.__init__(self, model: str | None = None)`

Initializes the OpenAI client and resolves the decision model.

### `OpenAIRequestDecision.decide(self, case: ClinicalCase, missing_questions: list[dict], reference_context: dict | None = None) -> ImagingDecision`

Sends the case, questions, and reference data to the LLM and validates an `ImagingDecision`.

## `bulkinout.request.golden`

Source: `src/bulkinout/request/golden.py`

### `_observed(value)`

Creates an observed `ClinicalField` with confidence 1 for tests.

### `case_from_facts(facts: dict[str, Any]) -> ClinicalCase`

Converts YAML `section.field` facts into a `ClinicalCase`.

### `GoldenResult`

Dataclass containing a golden-case result.

### `run_golden_case(path: Path, reference_dir: Path) -> GoldenResult`

Runs one golden case against the `ReferenceEngine` and returns the differences.

### `discover_golden_cases(case_dir: Path) -> list[Path]`

Recursively discovers golden-case YAML files.

## `bulkinout.request.reference_catalog`

Source: `src/bulkinout/request/reference_catalog.py`

### `build_catalog(reference_dir: Path) -> list[dict]`

Produces summarized metadata for every scenario YAML file.

## `bulkinout.request.reference_engine`

Source: `src/bulkinout/request/reference_engine.py`

### `ScenarioMatch`

Dataclass representing a matched scenario and its score.

### `_raw(case: ClinicalCase, field: str)`

Reads a known `ClinicalField` from a `section.field` path.

### `_predicate(case: ClinicalCase, pred: dict) -> bool`

Evaluates a YAML predicate against a known clinical value. Supported operators include `equals`, `contains`, `contains_any`, and `in`.

### `_condition(case: ClinicalCase, node: dict) -> bool`

Evaluates an `all` or `any` predicate group.

### `_candidate_applicable(case: ClinicalCase, candidate: dict) -> bool`

Evaluates a candidate's optional `when` clause.

### `ReferenceEngine`

Service class whose methods are documented below.

### `ReferenceEngine.__init__(self, reference_dir: Path)`

Loads all scenario YAML files from the reference directory.

### `ReferenceEngine.match(self, case: ClinicalCase) -> list[ScenarioMatch]`

Returns scenarios whose entry criteria match, ordered by score.

### `ReferenceEngine.unresolved_material_questions(self, case: ClinicalCase, scenario: dict) -> list[dict]`

Returns material questions whose field is still unknown.

### `ReferenceEngine.evaluate_rules(self, case: ClinicalCase, scenario: dict) -> list[dict]`

Evaluates a scenario's conditional rules.

### `ReferenceEngine.build_context(self, case: ClinicalCase, max_scenarios: int = 3) -> dict`

Builds the decision-engine context from scenarios, filtered candidates, questions, and rules.

## `bulkinout.request.request_builder`

Source: `src/bulkinout/request/request_builder.py`

### `_clean_value(section, key)`

Returns only the value of a known, nonconflicting field.

### `_fmt(label, value)`

Formats `label: value`; this helper is currently unused by the builder.

### `build_teleradiology_request(case: ClinicalCase, decision: ImagingDecision, questions: list[MissingQuestion]) -> TeleradiologyRequest`

Assembles the request draft from the case, decision, and questions.

## `bulkinout.request.rules`

Source: `src/bulkinout/request/rules.py`

### `_unknown(section: dict, key: str) -> bool`

Checks whether a clinical field is absent, unknown, or conflicting.

### `generic_missing_questions(case: ClinicalCase) -> list[MissingQuestion]`

Generates generic indication and symptom checks.

### `recommendation_specific_questions(case: ClinicalCase, decision) -> list[MissingQuestion]`

Adds safety and completeness checks specific to the proposed modality.
