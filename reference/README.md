# Radiology Reference v0.1

This directory contains an initial set of scenarios encoded from public guidance, primarily the ACR Appropriateness Criteria.

**Status: `needs_local_validation` throughout.**

The goal is not to reproduce source guidance, but to derive an auditable software structure containing:

- entry criteria and multilingual matching terms;
- data to retrieve;
- potentially discriminating clinical questions;
- candidate examinations;
- simple rules;
- source and version metadata.

Scenario IDs, rule IDs, keys, titles, reasons, and notes use English. Questions and examination names displayed to current clinical users remain in French. Matching predicates may include French and English synonyms.

Detailed technical parameters such as dose, exact phases, reconstruction, and MRI sequences must be added and validated locally by the radiology team.
