from __future__ import annotations

import pytest

from bulkinout.core.models import (
    UCUM_SYSTEM,
    ClinicalCase,
    ClinicalField,
    FieldStatus,
    SourceRef,
)
from bulkinout.core.normalization import (
    InMemoryTerminologyProvider,
    TerminologyEntry,
    TerminologyNormalizer,
    UCUMUnitProvider,
)

TEST_SYSTEM = "urn:bulkinout:test-terminology"


def observed(value: object) -> ClinicalField:
    return ClinicalField(
        value=value,
        status=FieldStatus.observed,
        confidence=0.9,
        sources=[SourceRef(document_id="test:note", filename="note.txt", excerpt=str(value))],
    )


def pulmonary_embolism_provider() -> InMemoryTerminologyProvider:
    return InMemoryTerminologyProvider(
        [
            TerminologyEntry(
                system=TEST_SYSTEM,
                code="pulmonary-embolism",
                display="Pulmonary embolism",
                synonyms=("pulmonary embolism", "embolie pulmonaire", "PE", "EP"),
                field_paths=frozenset({"current_problem.suspected_diagnosis"}),
            )
        ],
        name="test_clinical_terms",
        version="2026-09",
    )


@pytest.mark.parametrize(
    "text",
    [
        "Suspected pulmonary embolism",
        "Suspicion d'embolie pulmonaire",
        "Suspected PE",
        "Suspicion d'EP",
    ],
)
def test_in_memory_provider_maps_positive_french_and_english_terms(text):
    provider = pulmonary_embolism_provider()

    concepts = provider.concepts_for("current_problem.suspected_diagnosis", text)

    assert [(item.system, item.code, item.original_text) for item in concepts] == [
        (TEST_SYSTEM, "pulmonary-embolism", text)
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Sepsis with shock",
        "Sepsis d'origine pulmonaire",
        "No pulmonary embolism",
        "Pas d'embolie pulmonaire",
        "Negative for PE",
        "Absence d'EP",
    ],
)
def test_in_memory_provider_avoids_acronym_false_positives_and_negated_terms(text):
    provider = pulmonary_embolism_provider()

    assert provider.concepts_for("current_problem.suspected_diagnosis", text) == []


def test_in_memory_provider_keeps_positive_term_in_a_separate_clause():
    provider = pulmonary_embolism_provider()

    concepts = provider.concepts_for(
        "current_problem.suspected_diagnosis",
        "No fever, suspected PE",
    )

    assert [item.code for item in concepts] == ["pulmonary-embolism"]


def test_in_memory_provider_does_not_force_ambiguous_mapping():
    provider = InMemoryTerminologyProvider(
        [
            TerminologyEntry(TEST_SYSTEM, "one", "First", ("shared term",)),
            TerminologyEntry(TEST_SYSTEM, "two", "Second", ("shared term",)),
        ]
    )

    assert provider.concepts_for("current_problem.indication", "shared term") == []


def test_in_memory_provider_can_map_distinct_concepts_in_one_field():
    provider = InMemoryTerminologyProvider(
        [
            TerminologyEntry(TEST_SYSTEM, "hypertension", "Hypertension", ("hypertension",)),
            TerminologyEntry(TEST_SYSTEM, "diabetes", "Diabetes", ("diabète", "diabetes")),
        ]
    )

    concepts = provider.concepts_for(
        "history.relevant_conditions",
        "Hypertension artérielle et diabète de type 2",
    )

    assert {concept.code for concept in concepts} == {"hypertension", "diabetes"}


@pytest.mark.parametrize(
    ("value", "code", "number"),
    [
        ("Créatinine : 103 µmol/L", "umol/L", 103),
        ("Glucose 5,6 mmol/L", "mmol/L", 5.6),
        ("Glucose 101 mg/dL", "mg/dL", 101),
        ("Blood pressure 146 mmHg", "mm[Hg]", 146),
        ("SpO2 92 % on room air", "%", 92),
    ],
)
def test_ucum_provider_normalizes_common_units_without_replacing_value(value, code, number):
    concepts = UCUMUnitProvider().concepts_for("labs.result", value)

    assert len(concepts) == 1
    assert concepts[0].system == UCUM_SYSTEM
    assert concepts[0].code == code
    assert concepts[0].normalized_value == number


def test_ucum_provider_leaves_unknown_units_unmapped_and_keeps_distinct_measurements():
    provider = UCUMUnitProvider()

    assert provider.concepts_for("labs.result", "Value 12 arbitrary units") == []
    concepts = provider.concepts_for("labs.result", "1 mg/L and 2 g/L")
    assert [(concept.code, concept.normalized_value) for concept in concepts] == [
        ("mg/L", 1),
        ("g/L", 2),
    ]


def test_normalizer_preserves_value_status_sources_and_records_provider_identity():
    field = observed("Suspicion d'EP")
    original_sources = field.sources.copy()
    case = ClinicalCase(current_problem={"suspected_diagnosis": field})
    normalizer = TerminologyNormalizer([pulmonary_embolism_provider()])

    returned = normalizer.normalize_case(case)
    normalizer.normalize_case(case)

    assert returned is case
    assert field.value == "Suspicion d'EP"
    assert field.status == FieldStatus.observed
    assert field.sources == original_sources
    assert len(field.coded_concepts) == 1
    assert case.metadata["terminology"]["providers"][0]["name"] == "test_clinical_terms"


def test_normalizer_leaves_unmapped_free_text_usable():
    field = observed("Unmapped clinical wording")
    case = ClinicalCase(current_problem={"indication": field})

    TerminologyNormalizer([pulmonary_embolism_provider()]).normalize_case(case)

    assert field.value == "Unmapped clinical wording"
    assert field.coded_concepts == []


def test_normalizer_skips_unknown_and_conflicting_fields():
    case = ClinicalCase(
        current_problem={
            "unknown": ClinicalField(value="PE", status=FieldStatus.unknown),
            "conflicting": ClinicalField(value="PE", status=FieldStatus.conflicting),
        }
    )

    TerminologyNormalizer([pulmonary_embolism_provider()]).normalize_case(case)

    assert case.current_problem["unknown"].coded_concepts == []
    assert case.current_problem["conflicting"].coded_concepts == []
