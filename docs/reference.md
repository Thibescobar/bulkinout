# Request Reference

Scenarios are YAML files in `reference/scenarios/`. v0 contains 18 scenarios, all marked `needs_local_validation`.

## Structure

```yaml
id: renal_colic
version: 0.1.0
title: Suspected renal colic / urinary stone disease
status: needs_local_validation
sources: [...]
entry:
  any:
    - {field: current_problem.location, contains_any: ["flanc", "flank"]}
questions: [...]
candidates: [...]
rules: [...]
```

Scenario titles, reasons, notes, and rule metadata are technical content and use English. Clinical questions and examination names presented to French users remain in French.

## Matching

`ReferenceEngine.match()` evaluates `entry.all` or `entry.any`. v0 supports `equals`, `not_equals`, `contains`, `contains_any`, and `in`. `contains_any` accepts a synonym list and succeeds when any term is present. An `unknown` or `conflicting` field satisfies no predicate. Matching terms may be multilingual; French terms are preserved and English synonyms are added rather than replacing them.

## Material Questions and Candidates

`unresolved_material_questions()` returns only `material: true` questions whose field is unknown, ordered by `priority`. `build_context()` includes only candidates whose optional `when` clause matches; candidates without `when` are always included.

## Rules

`evaluate_rules()` applies each `rules[].if` condition and returns its `result`. v0 can encode a preferred candidate or `no_imaging_recommended`; final interpretation is supplied to Request through `reference_context`.

## Field-Path Limitation

The rule engine reads first-level `ClinicalCase` dictionaries through `section.field` paths. It does not traverse arbitrary nested lists or objects. v0 scenarios therefore use fields that can be queried and completed within those sections.
