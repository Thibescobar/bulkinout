# Request reference

The reference is a versioned, auditable input to Request. Each YAML file describes when a clinical scenario applies, what information matters, which examinations are candidates, and which simple deterministic rules can fire.

All 18 bundled scenarios are marked `needs_local_validation`. They are implementation examples derived from public guidance, primarily ACR Appropriateness Criteria; they are not a complete or locally approved protocol library.

## Scenario anatomy

```yaml
id: renal_colic                         # Stable technical identifier
version: 0.1.0
title: Suspected renal colic / urinary stone disease
status: needs_local_validation

sources:
  - organization: ACR
    title: Acute Onset Flank Pain-Suspicion of Stone Disease
    url: https://acsearch.acr.org/docs/69362/Narrative/

entry:
  any:
    - field: current_problem.suspected_diagnosis
      contains_any: ["colique", "renal colic"]
    - field: current_problem.location
      contains_any: ["flanc", "flank"]

questions:
  - id: pregnancy
    field: imaging_safety.pregnancy
    question: "Une grossesse est-elle possible ou en cours ?"
    priority: 1
    material: true
    reason: Pregnancy changes the modality hierarchy.

candidates:
  - id: ct_noncontrast
    exam_name: TDM abdomen-pelvis sans injection
    modality: CT
    contrast: no
    appropriateness: usually_appropriate
    when:
      all:
        - field: imaging_safety.pregnancy
          not_equals: true

rules: []
notes:
  - The reference encodes modality hierarchy, not local dose parameters.
```

### Language boundary

| Content | Language rule |
|---|---|
| IDs, keys, titles, reasons, notes, statuses | Canonical technical English. |
| Questions shown to clinicians | French for current users. |
| Examination names shown in requests | French for current users. |
| Matching terms | Multilingual; retain French and add English or other useful synonyms. |
| Structured comparison values | Canonical English, such as `low`, `negative`, or boolean values. |

Do not translate a French matching term away. Adding `"renal colic"` beside `"colique"` expands recognition; replacing `"colique"` would regress French input.

## Matching operators

Predicates read known values from first-level `ClinicalCase` dictionary paths.

| Operator | Behavior | Example |
|---|---|---|
| `equals` | Python equality with the supplied value. | `{field: imaging_safety.pregnancy, equals: true}` |
| `not_equals` | Python inequality with the supplied value. | `{field: imaging_safety.pregnancy, not_equals: true}` |
| `contains` | Case-insensitive substring search. Lists are joined as text first. | `{field: current_problem.indication, contains: "appendic"}` |
| `contains_any` | Case-insensitive substring search for any synonym in a list. | `{field: current_problem.location, contains_any: ["flanc", "flank"]}` |
| `contains_token` | Case-insensitive whole-term search for one acronym or term. | `{field: current_problem.suspected_diagnosis, contains_token: "EP"}` |
| `contains_any_term` | Whole-term search for any synonym without changing the predicate count. | `{field: current_problem.location, contains_any_term: ["RLQ", "right lower quadrant"]}` |
| `in` | Exact membership in a supplied list. | `{field: labs.d_dimer, in: ["negative", "normal"]}` |

Unknown and conflicting fields never satisfy a predicate. Use substring operators for intentional roots such as `appendic`; use boundary-aware term operators for short acronyms so `EP` does not match `sepsis`. Matching does not currently remove accents, lemmatize words, expand abbreviations automatically, or use a terminology server.

## `all`, `any`, and scoring

An `entry.all` scenario qualifies only when every predicate matches. Its score is the number of hits divided by the number of predicates, so a qualifying `all` entry scores `1.0`.

An `entry.any` scenario qualifies when at least one predicate matches. Its score uses the same fraction:

```text
match score = matching predicates / total entry predicates
```

For an `any` block with three predicates, one hit scores `0.33`, two score `0.67`, and three score `1.0`. Matches are sorted by descending score; equal scores retain scenario load order because Python sorting is stable and files are loaded alphabetically.

`build_context()` keeps at most three scenarios by default. The score is a simple routing heuristic, not a clinical probability or calibrated confidence measure.

## Material questions

Questions connect a stable clinical field to French presentation text and English metadata.

| Property | Meaning |
|---|---|
| `id` | Stable question identifier inside the scenario. |
| `field` | `section.field` path inspected for an answer. |
| `question` | Clinical text shown to the current French user. |
| `priority` | Sort order; lower numbers appear first. |
| `material` | Whether the unresolved question is included in reference context. |
| `required_to_choose` | Whether an unresolved answer deterministically prevents examination selection. |
| `blocking` | Whether an unresolved constraint blocks the workflow; safety fields produce `safety_blocked`. |
| `reason` | Developer-facing explanation of why the fact matters. |

`unresolved_material_questions()` returns relevant questions whose field is absent, unknown, or conflicting. A material question may inform comparison without being mandatory. Required and blocking questions are converted to deterministic `MissingQuestion` objects after matching; the LLM may add questions but cannot remove or weaken these constraints. Questions from all sources are deduplicated by canonical field while retaining the strongest requirement.

## Candidate filtering

Every candidate has a stable ID and French examination name. A candidate without `when` is always exposed. A candidate with `when` is included only when its condition evaluates true.

This filtering is deterministic and happens before the context reaches the decision model. It is appropriate for explicit facts such as pregnancy-dependent modality eligibility, but it should not encode complex or locally disputed clinical reasoning without review and tests.

## Rules

Rules express small deterministic consequences:

```yaml
rules:
  - id: low_probability_negative_ddimer
    if:
      all:
        - {field: current_problem.pe_pretest_probability, in: ["low", "intermediate"]}
        - {field: labs.d_dimer, equals: "negative"}
    result:
      no_imaging_recommended: true
      reason: ACR: initial imaging is generally not appropriate for this variant.
```

`evaluate_rules()` returns matching rule IDs and result dictionaries. It does not directly mutate `ImagingDecision`; the results become part of the LLM reference context. This distinction matters when debugging: a correctly triggered rule can still be interpreted incorrectly by the model.

## Authoring a scenario

Use this sequence to keep reference changes reviewable:

1. **Choose a stable ID.** Use `snake_case`; do not rename an existing ID solely to improve wording.
2. **Record the source.** Include organization, exact source title, and a durable URL.
3. **Define narrow entry predicates.** Prefer recognizable clinical phrases over very broad fragments that create false positives.
4. **Add multilingual synonyms.** Preserve existing French terms and add English equivalents in one `contains_any` or `contains_any_term` predicate so scoring does not change accidentally.
5. **Classify questions explicitly.** Use `material` for decision-relevant context, `required_to_choose` only when selection is invalid without the answer, and `blocking` for an unresolved workflow or safety constraint.
6. **List candidates and explicit conditions.** Keep French presentation names separate from English IDs and values.
7. **Use rules sparingly.** Encode only behavior that is clear enough to test deterministically.
8. **Keep `needs_local_validation`.** Change validation status only through an explicit clinical governance process.
9. **Add golden cases.** Cover a positive match, important rule branches, missing material fields, and both French and English terminology where relevant.
10. **Regenerate or update the catalog.** Ensure title and counts agree with the YAML source.

## Regression traps

- Adding a second synonym as a separate `entry.any` predicate changes the score denominator. Use one `contains_any` or `contains_any_term` predicate when the terms represent one concept.
- Translating canonical values such as `negative` into display language breaks exact `equals` and `in` predicates.
- Changing a question field path can prevent answer files and guards from finding the same fact.
- Reusing a vague fragment such as `pain` across scenarios produces broad matches and unstable top-three selection.
- Setting `material: false` removes the question from reference context even when its priority is high.
- A candidate `when` condition on an unknown field evaluates false and hides that candidate.

## Validation commands

```bash
pytest -q tests/test_reference_engine.py tests/test_reference_engine_v0.py
bulkinout request catalog --reference reference/scenarios
bulkinout request golden --cases tests/golden --reference reference/scenarios
```

Run the complete suite after any terminology, field-path, matching, candidate, or rule change. Golden cases validate deterministic behavior; manual E2E review remains necessary for model interpretation and French clinical output.
