import pytest

from bulkinout.core import service
from bulkinout.core.models import ClinicalCase, LLMExtraction, LLMFact, LLMSource
from bulkinout.errors import ConfigurationError, InputError


def test_build_radiology_case_rejects_empty_input(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "collect_files", lambda path: [])

    with pytest.raises(InputError, match="No supported document"):
        service.build_radiology_case(tmp_path)


def test_default_extractor_requires_api_key_after_input_validation(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "collect_files", lambda path: [tmp_path / "letter.txt"])
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY is missing"):
        service.build_radiology_case(tmp_path, model="test-model")


def test_build_radiology_case_creates_artifacts_and_audit(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    paths = [tmp_path / "letter.txt", tmp_path / "scan.pdf"]
    extraction = LLMExtraction(document_notes=["ok"])

    class FakeExtractor:
        name = "test_extractor"
        model = "local-model"

        def extract(self, received_paths):
            assert received_paths == paths
            return extraction

    monkeypatch.setattr(service, "collect_files", lambda path: paths)
    monkeypatch.setattr(
        service,
        "extraction_to_case",
        lambda result: ClinicalCase(metadata={"source": result.document_notes[0]}),
    )

    case, returned_extraction, returned_paths = service.build_radiology_case(
        tmp_path,
        extractor=FakeExtractor(),
    )

    assert returned_extraction is extraction
    assert returned_paths == paths
    assert case.clinical.metadata == {
        "source": "ok",
        "terminology": {
            "providers": [
                {
                    "name": "builtin_ucum_units",
                    "version": "1",
                    "content_sha256": service.default_terminology_normalizer()
                    .providers[0]
                    .content_sha256,
                }
            ]
        },
        "extractor": "test_extractor",
        "documents_processed": 2,
        "model": "local-model",
        "extractor_manifest": {
            "provider": "unreported",
            "name": "test_extractor",
            "model": "local-model",
            "prompt_sha256": "unreported",
            "inference_parameters": {},
        },
    }
    assert [artifact.artifact_id for artifact in case.artifacts] == [
        "input:letter.txt",
        "input:scan.pdf",
    ]
    assert case.audit == [{"event": "core_structuring_completed", "model": "local-model"}]


def test_build_radiology_case_annotates_units_without_losing_extraction_provenance(
    monkeypatch, tmp_path
):
    source = tmp_path / "laboratory.txt"
    extraction = LLMExtraction(
        facts=[
            LLMFact(
                field="labs.creatinine",
                value="Créatinine : 103 µmol/L",
                status="observed",
                confidence=0.98,
                sources=[
                    LLMSource(
                        filename=source.name,
                        excerpt="Créatinine : 103 µmol/L",
                    )
                ],
            )
        ]
    )

    class FakeExtractor:
        name = "local"
        model = "deterministic"

        def extract(self, paths):
            return extraction

    monkeypatch.setattr(service, "collect_files", lambda path: [source])

    result = service.build_radiology_case(tmp_path, extractor=FakeExtractor())
    field = result.radiology_case.clinical.labs["creatinine"]

    assert field.value == "Créatinine : 103 µmol/L"
    assert field.sources[0].excerpt == "Créatinine : 103 µmol/L"
    assert field.coded_concepts[0].code == "umol/L"
    assert field.coded_concepts[0].normalized_value == 103
