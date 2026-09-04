# BULKINOUT Request

## Execution Order

`cmd_request_run()` currently performs:

1. `build_radiology_case()`;
2. optional answer-file application;
3. `generic_missing_questions()`;
4. `ReferenceEngine.build_context()`;
5. `OpenAIRequestDecision.decide()`;
6. `enforce_decision_guard()`;
7. `recommendation_specific_questions()`;
8. conservative blocking for critical or high-priority safety and completeness questions;
9. `build_teleradiology_request()`;
10. output JSON serialization.

## Generic Questions

`generic_missing_questions()` checks the indication and, when necessary, the symptoms or signs motivating imaging. This layer is intentionally small; the reference owns scenario-specific questions. Questions shown to clinicians remain in French, while their internal reasons use English.

## LLM Decision

`OpenAIRequestDecision.decide()` receives the structured case, unresolved generic questions, and `reference_context`. It compares candidates and returns an `ImagingDecision` that strictly satisfies the Pydantic schema. Source input is language-agnostic; canonical structured concepts use English.

## Deterministic Guard

`enforce_decision_guard()` prevents `selected` when a `required_to_choose=True` discriminating question points to an unknown or conflicting field. It changes the decision to `insufficient_information`, marks the primary candidate as not recommended, and requires a clinician call.

## Modality-Dependent Checks

`recommendation_specific_questions()` adds iodinated-contrast and renal-function checks for contrast CT; pacemaker and implant checks for MRI; and potential-pregnancy checks for ionizing modalities when patient data makes them relevant.

In v0, an unresolved `critical` or `high` modality-specific question prevents human-approval readiness. Explicit blocking safety questions use `safety_blocked`.

## Request Construction

`build_teleradiology_request()` excludes `unknown` and `conflicting` values from reliable facts. It gathers the French-facing patient summary, indication, proposed exam and protocol, history, allergies and medication, laboratory data, safety data, prior imaging, and unresolved questions.
