# Architecture

## Overview

```text
                     BULKINOUT
                        │
                 ┌──────┴──────┐
                 │             │
               Core         Workflows
                 │        ┌────┴────┐
                 │      Request   Report
                 │        v0      standby
                 ↓
           RadiologyCase
```

### Core

Core does not select an imaging examination. It collects supported files, submits them to an LLM extractor with structured output, converts the extraction into a `ClinicalCase`, and builds a `RadiologyCase` containing artifacts and an initial audit event. Source documents are treated as language-agnostic.

### Request

Request consumes `RadiologyCase.clinical`. It adds generic checks, builds context from YAML scenarios, asks the LLM to compare candidates, applies a deterministic guard to discriminating questions, and adds modality-dependent safety checks. It then builds a `TeleradiologyRequest` and stores outputs in `RadiologyCase.referral`.

### Report

`bulkinout/report/` is intentionally on standby. v0 implements no post-exam processing, computer-vision result, dictation, or report generation.

## Layer Dependencies

`core` must not depend on `request`; `request` may import Core models. This direction allows the same `RadiologyCase` to support `report` later without depending on pre-exam relevance logic.
