# Python API

The package facade exposes the same application services used by the CLI. Use it when another Python process should control persistence, inspect intermediate state, or integrate Bulkinout into a larger workflow.

## Request workflow

```python
from pathlib import Path

from bulkinout import run_request, write_request_outputs

result = run_request(
    Path("input"),
    reference_dir=Path("reference/scenarios"),
    model="<compatible-model>",
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

The service owns the full order of operations: Core extraction, answer application, reference matching, model decision, required-discriminator guard, modality checks, clinical draft construction, and audit update. Do not reproduce that sequence in an integration.

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

## Configuration and failures

LLM-backed services require `OPENAI_API_KEY` plus either the `model` argument or `BULKINOUT_MODEL`. Catch `BulkinoutError` for expected application failures:

```python
from pathlib import Path

from bulkinout import BulkinoutError, run_request

try:
    result = run_request(Path("input"))
except BulkinoutError as error:
    handle_expected_failure(str(error))
```

`ConfigurationError`, `InputError`, and `ReferenceDataError` provide narrower handling. OpenAI, filesystem, JSON, YAML, and Pydantic exceptions keep their original types rather than being hidden inside a generic wrapper.

The API is synchronous and has no global mutable workflow state. HTTP transport, authentication, durable persistence, request isolation, retries, and approval storage remain integration responsibilities.
