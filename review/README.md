# Radiologist Review

For each end-to-end case, record whether the following are correct:

- scenario;
- clinical questions;
- examination;
- protocol;
- clinician callback decision;
- whether the handoff provides sufficient evidence, clarification trace, and safety context for review;
- whether citations are presented as scenario background rather than patient-specific endorsement;
- identification of missing critical information.

Error categories:
`core_extraction`, `scenario_matching`, `reference_question`, `reference_rule`,
`decision_llm`, `safety_guard`, `request_generation`, `other`.

The CSV headings and review categories are developer-facing and use English. Review comments may quote French clinical presentation text when necessary.
