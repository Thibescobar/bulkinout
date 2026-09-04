# Data Model

Pydantic models are defined in `src/bulkinout/core/models/case.py`.

## Provenance: `ClinicalField`

A clinical datum is not stored as a bare value. It carries:

- `value`: the extracted value;
- `status`: `observed`, `inferred`, `unknown`, or `conflicting`;
- `sources`: `SourceRef` entries containing a filename, optional page, and excerpt;
- `confidence`: a score from 0 to 1;
- `validated`: human-validation state, `False` by default.

Absence of mention must never be converted automatically to `False`. Provenance excerpts retain the source language.

## `ClinicalCase`

Clinical context is divided into dictionaries of `ClinicalField`: `patient`, `current_problem`, `history`, `medications`, `allergies`, `labs`, and `imaging_safety`, plus `prior_imaging` and `metadata`. Field paths use stable English identifiers such as `current_problem.location` and `imaging_safety.pregnancy`.

## `RadiologyCase`

`RadiologyCase` is the shared longitudinal container. v0 mainly uses `workflow`, `clinical`, `artifacts`, `referral`, and `audit`. `acquisition`, `ai_results`, `radiologist_observations`, `findings`, `impression`, and `final_report` are reserved for the future post-exam workflow.

## Request Decision

`ImagingDecision` contains `decision_status`, candidates, discriminating questions, recommendations, clinician-call state, and human-approval readiness. Valid statuses are `selected`, `insufficient_information`, `no_imaging_recommended`, and `safety_blocked`.

`TeleradiologyRequest.status` is `draft`, `ready_for_human_approval`, or `blocked`. None represents an autonomous prescription: `validated_by_clinician` remains `False` until an external validation mechanism is implemented.
