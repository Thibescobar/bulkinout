# BULKINOUT Core

## Ingestion

`core.ingestion.files.collect_files(input_dir)` recursively collects `.pdf`, `.txt`, `.md`, `.png`, `.jpg`, `.jpeg`, and `.webp` files. Test JSON and unsupported files are ignored.

## LLM Extraction

`OpenAICoreExtractor` uses the OpenAI SDK. Configure the model with `--model` or `BULKINOUT_MODEL`. TXT and Markdown files are inserted as text, images are sent as `input_image` data URLs, and other supported files such as PDFs are uploaded as `input_file`.

The response must satisfy the `LLMExtraction` Pydantic schema. The prompt prohibits invented facts, preserves provenance and source wording, distinguishes `observed` from `inferred`, detects contradictions, and prohibits inferred MRI compatibility or renal function. Input may be written in any language; canonical identifiers and structured concepts use English.

## Clinical Case Conversion

`extraction_to_case()` maps `section.field` facts into `ClinicalCase` dictionaries. Recognized sections are `patient`, `current_problem`, `history`, `medications`, `allergies`, `labs`, and `imaging_safety`. Structured prior imaging becomes `PriorImaging` objects.

## Core Service

`build_radiology_case()` orchestrates ingestion, extraction, and conversion. It returns `(RadiologyCase, LLMExtraction, paths)`. The case includes input artifacts and a `core_structuring_completed` audit event.

## Not Yet Implemented

`normalization`, `reconciliation`, and `timeline` are empty in v0. Current reconciliation relies on structured LLM output, contradictions, provenance, and Request behavior; no dedicated deterministic longitudinal merge engine exists yet.
