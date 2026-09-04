import pytest

from bulkinout.core import service
from bulkinout.core.models import ClinicalCase, LLMExtraction


def test_build_radiology_case_rejects_empty_input(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "collect_files", lambda path: [])

    with pytest.raises(ValueError, match="Aucun document supporté"):
        service.build_radiology_case(tmp_path)


def test_build_radiology_case_creates_artifacts_and_audit(monkeypatch, tmp_path):
    paths = [tmp_path / "letter.txt", tmp_path / "scan.pdf"]
    extraction = LLMExtraction(document_notes=["ok"])

    class FakeExtractor:
        def __init__(self, model=None):
            self.model = model or "fallback-model"

        def extract(self, received_paths):
            assert received_paths == paths
            return extraction

    monkeypatch.setattr(service, "collect_files", lambda path: paths)
    monkeypatch.setattr(service, "OpenAICoreExtractor", FakeExtractor)
    monkeypatch.setattr(
        service,
        "extraction_to_case",
        lambda result: ClinicalCase(metadata={"source": result.document_notes[0]}),
    )

    case, returned_extraction, returned_paths = service.build_radiology_case(
        tmp_path, model="test-model"
    )

    assert returned_extraction is extraction
    assert returned_paths == paths
    assert case.clinical.metadata == {
        "source": "ok",
        "documents_processed": 2,
        "model": "test-model",
    }
    assert [artifact.artifact_id for artifact in case.artifacts] == [
        "input:letter.txt",
        "input:scan.pdf",
    ]
    assert case.audit == [{"event": "core_structuring_completed", "model": "test-model"}]
