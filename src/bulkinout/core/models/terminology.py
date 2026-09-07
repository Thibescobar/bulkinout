"""Language-independent terminology models shared by clinical workflows."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...types import JsonValue

SNOMED_CT_SYSTEM = "http://snomed.info/sct"
LOINC_SYSTEM = "http://loinc.org"
UCUM_SYSTEM = "http://unitsofmeasure.org"
RADLEX_SYSTEM = "http://radlex.org"


class CodedConcept(BaseModel):
    """A terminology annotation that never replaces the original clinical value."""

    system: str = Field(min_length=1)
    code: str = Field(min_length=1)
    display: str = Field(min_length=1)
    original_text: str = Field(min_length=1)
    version: str | None = None
    normalized_value: JsonValue = None
