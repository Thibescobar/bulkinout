# Python API

The package facade exposes the same application services used by the CLI. Use it when another Python process should control persistence, inspect intermediate state, or integrate Bulkinout into a larger workflow.

## Request workflow

```python
from pathlib import Path

from bulkinout import run_request, write_request_outputs

result = run_request(
    Path("input"),
    extraction_model="<multimodal-model>",
    decision_model="<decision-model>",
    answers_path=None,
)

if result.imaging_decision.decision_ready_for_human_approval:
    print(result.teleradiology_request)

write_request_outputs(result, Path("output"))
```

`run_request()` performs no local writes. It returns a slot-based `RequestResult`, then `write_request_outputs()` optionally creates the same eight snapshots as `bulkinout request run`.

```text
run_request()
├── radiology_case
├── extraction
├── clinical_case
├── reference_context
├── missing_questions[]
├── imaging_decision
├── teleradiology_request
└── source_paths[]
```

The service owns the full order of operations: Core extraction, answer application, reference matching, model decision, required-discriminator guard, modality checks, clinical draft construction, and audit update. By default it loads the reference shipped in the installed package. Pass `reference_dir=Path("reference/scenarios")` only when intentionally selecting an override. Do not reproduce the workflow sequence in an integration.

## Core only

```python
from pathlib import Path

from bulkinout import build_radiology_case, write_core_outputs

result = build_radiology_case(Path("input"), model="<compatible-model>")
print(result.radiology_case.clinical)
write_core_outputs(result, Path("output_core"))
```

`CoreResult` has named attributes and remains tuple-compatible for existing callers:

```python
record, extraction, source_paths = result
```

## Custom and local LLM components

The services accept two small provider-neutral protocols:

```text
CoreExtractor
└── extract(paths) -> LLMExtraction

RequestDecisionEngine
└── decide(case, missing_questions, reference_context) -> ImagingDecision
```

An extractor also exposes `name` and `model` strings so Core can preserve the implementation identity in case metadata and audit output. A custom adapter owns document decoding, transport, prompting, and response parsing. It must return the existing Pydantic contract; it must not add reference matching or clinical safeguards.

```python
from pathlib import Path

from bulkinout import CoreExtractor, RequestDecisionEngine, run_request

extractor: CoreExtractor = MyLocalExtractor(model="local-extractor")
decision_engine: RequestDecisionEngine = MyLocalDecisionEngine(model="local-decision")

result = run_request(
    Path("input"),
    extractor=extractor,
    decision_engine=decision_engine,
)
```

Supplying both components removes the OpenAI configuration requirement. Mixed configurations are also valid: for example, a local extractor can be combined with the default OpenAI decision engine. In that case, stage-specific model arguments configure the corresponding default component. The legacy `model=` argument remains a shared fallback, followed by `BULKINOUT_EXTRACTION_MODEL` or `BULKINOUT_DECISION_MODEL`, then `BULKINOUT_MODEL`. Any default component still requires `OPENAI_API_KEY`.

This is dependency injection, not automatic provider discovery. Bulkinout ships OpenAI adapters only; an Ollama, llama.cpp, vLLM, or other local integration must implement these protocols and demonstrate that its outputs validate as `LLMExtraction` and `ImagingDecision`. Deterministic guards run after every decision engine in the same order.

## Configuration and failures

The default OpenAI components require `OPENAI_API_KEY` plus a stage-specific model setting or the shared `model=` / `BULKINOUT_MODEL` fallback. Injected components own their configuration. Catch `BulkinoutError` for expected application failures:

```python
from pathlib import Path

from bulkinout import BulkinoutError, run_request

try:
    result = run_request(Path("input"))
except BulkinoutError as error:
    handle_expected_failure(str(error))
```

`ConfigurationError`, `InputError`, and `ReferenceDataError` provide narrower handling. Provider, filesystem, JSON, YAML, and Pydantic exceptions keep their original types rather than being hidden inside a generic wrapper.

The API is synchronous and has no global mutable workflow state. HTTP transport, authentication, durable persistence, request isolation, retries, and approval storage remain integration responsibilities.
