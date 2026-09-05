# Interactive clarification and radiology handoff

This feature connects three distinct responsibilities without treating any software state as clinical approval:

1. Bulkinout identifies information that can change or block the imaging proposal.
2. The requesting clinician may supply typed answers locally.
3. The remote radiologist receives a traceable proposal or an explicit escalation package.

## Workflow

```mermaid
flowchart TD
    A[Clinical documents] --> B[Core extraction once]
    B --> C[Request evaluation]
    C --> D{Required answer missing?}
    D -- No --> H[Build radiology handoff]
    D -- Yes, interactive --> E[Loopback browser form]
    E --> F{Answer available?}
    F -- Yes --> G[Recalculate Request from the same Core result]
    G --> H
    F -- No --> I[Direct teleradiologist contact required]
    D -- Yes, non-interactive --> J[Terminal guidance + answer template]
    J --> I
    H --> K[Remote radiologist review]
```

The first Request evaluation discovers reference, model-generated, and modality-specific questions. All currently known required or blocking questions appear together in one form; Request is not run between individual answers. Submitting the form changes the button state and displays an animated progress indicator while triggering a second Request evaluation, but not another Core extraction or source-document upload. The same browser request remains open during this calculation, then the form is replaced by the final review handoff. The refreshed reference context, safeguards, request, manifest, and handoff are written over the initial snapshots in the selected output directory.

## Interactive mode

```bash
bulkinout request run \
  --input input \
  --output output/run_001 \
  --interactive
```

The CLI opens a browser form only when a required or blocking question remains. Boolean, integer, numeric, and text questions use distinct controls so canonical values retain their JSON types. Leaving a field empty records it as unavailable; it never converts missing information into an observed fact. The clinician may instead choose direct teleradiologist escalation.

The form:

- binds only to `127.0.0.1` on a random port;
- uses a high-entropy, single-use URL token;
- contains no remote scripts, fonts, images, or analytics;
- uses one nonce-authorized inline script only for click feedback and the progress indicator;
- rejects an unexpected host, path, form shape, or oversized request;
- allows ten minutes to submit, remains open during recalculation, and closes its local server only after serving the final handoff;
- writes `answers.interactive.N.json` with owner-only permissions where supported.

Browser failure or submission timeout leaves the initial guarded result intact and returns the operator to the file-based workflow. `--interactive` and `--answers` are mutually exclusive for one invocation. A new required question discovered only after recalculation is shown in the final handoff and terminal guidance; v0 deliberately performs one bounded interactive round.

## Non-interactive mode

The default remains suitable for scripts. When answers are missing, the terminal lists the questions, identifies `answers.template.json`, and prints the required `--answers` handoff. A file-based second run still performs a complete workflow, including a new Core extraction, because it is an independent invocation.

Never run different cases into the same output directory. Existing snapshot filenames are overwritten sequentially and writes are not transactional.

## Answer trace

An interactive answer retains:

```text
question ID and canonical field
├── French question and clinical impact
├── typed answer or explicit unavailability
├── declared responder role
├── UTC timestamp
├── response method
└── answer filename used as fact provenance
```

`apply_answers()` stores non-empty answers as observed facts with confidence `1.0` and `validated=false`. `false` and `0` are valid answers. `null`, an empty string, or whitespace remains unresolved. The role and timestamp are declarations, not authentication, identity proof, or an electronic signature.

## Teleradiology review package

Every Request run writes two additive artifacts:

- `radiology_handoff.json` is the canonical schema-v1 review package;
- `radiology_handoff.html` is its escaped, self-contained French presentation.

The package contains:

- the proposal or explicit requirement for clinician contact;
- all known and conflicting structured facts with document provenance;
- a dedicated safety-fact view;
- answered and unanswered clarifications;
- matched scenario IDs, versions, validation statuses, candidates, and locally triggered rules;
- the model rationale and alternatives;
- reference citations and mandatory warnings.

The visible review layer uses French clinical labels, translated display values for known canonical concepts, and source wording for free-text evidence. Developer-facing field paths, raw canonical values, confidence, validation flags, exact answer filenames, and scenario metadata remain unchanged in JSON and are grouped under the collapsed **Afficher la traçabilité technique** section. This separation changes presentation only; it does not translate source excerpts or modify clinical data.

A proposed examination is linked to a YAML candidate only when its examination name exactly matches an applicable reference candidate. Model-generated candidate IDs are retained separately and must not be mistaken for validated reference IDs.

## Citation semantics

Current references are attached at scenario level. The handoff therefore labels them `scenario_background`, for example:

```text
ACR — Right Lower Quadrant Pain
Scenario: rlq_appendicitis, version 0.1.0
Reference status: needs_local_validation
Relationship: scenario_background
```

This means that the material informed the local scenario. It does not mean that the source organization approved the model output, the local encoding, or the patient-specific proposal. When a source has no explicit ID, Bulkinout derives a run-local ID such as `rlq_appendicitis:source:1` without inventing a guideline locator.

## Outcomes for the remote radiologist

`ready_for_radiologist_review` provides a proposal with its clinical evidence, clarifications, uncertainties, safety data, alternatives, and references. The radiologist still accepts, modifies, or refuses it outside Bulkinout.

`clinician_contact_required` provides no apparently approved examination. It explains why Bulkinout abstained and which questions or conflicts require direct discussion. In time-critical care, the form's escalation action must not delay direct contact.

## Security and current limits

The loopback form reduces accidental network exposure but does not secure a compromised workstation. Browser history, extensions, screenshots, local processes, and the output directory remain in the local trust boundary. The form provides no login, access control, durable session, remote collaboration, prescription, transmission, or radiologist signature.

Treat source documents, questions, answer files, JSON snapshots, and the HTML handoff as clinical data. Use only synthetic data until the data-lifecycle gate in the [roadmap](roadmap.md) is satisfied.
