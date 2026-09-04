import base64
from types import SimpleNamespace

import pytest

from bulkinout.core.extraction import llm
from bulkinout.core.models import FieldStatus, LLMExtraction, LLMFact, LLMSource


class FakeResponses:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def test_schema_format_uses_strict_pydantic_schema():
    result = llm._schema_format(LLMExtraction)

    assert result["type"] == "json_schema"
    assert result["name"] == "LLMExtraction"
    assert result["strict"] is True
    assert result["schema"]["title"] == "LLMExtraction"


def test_extract_json_prefers_output_text_and_falls_back_to_chunks():
    assert llm._extract_json(SimpleNamespace(output_text='{"facts": []}')) == '{"facts": []}'

    response = SimpleNamespace(
        output_text="",
        output=[
            SimpleNamespace(
                content=[SimpleNamespace(text="first"), SimpleNamespace(text=None)]
            ),
            SimpleNamespace(content=[SimpleNamespace(text="second")]),
        ],
    )
    assert llm._extract_json(response) == "firstsecond"
    assert llm._extract_json(SimpleNamespace()) == ""


def test_extractor_requires_a_model(monkeypatch):
    monkeypatch.delenv("BULKINOUT_MODEL", raising=False)
    monkeypatch.setattr(llm, "OpenAI", lambda: SimpleNamespace())

    with pytest.raises(ValueError, match="No model configured"):
        llm.OpenAICoreExtractor()


def test_structured_call_uses_configured_model(monkeypatch):
    responses = FakeResponses(SimpleNamespace(output_text='{"facts": []}'))
    client = SimpleNamespace(responses=responses)
    monkeypatch.setattr(llm, "OpenAI", lambda: client)
    extractor = llm.OpenAICoreExtractor(model="test-model")

    result = extractor._call_structured("prompt", [{"type": "input_text"}], LLMExtraction)

    assert result == LLMExtraction()
    assert responses.calls[0]["model"] == "test-model"
    assert responses.calls[0]["text"]["format"]["strict"] is True


def test_upload_or_inline_handles_images_and_documents(tmp_path):
    uploads = []

    def create_file(*, file, purpose):
        uploads.append((file.read(), purpose))
        return SimpleNamespace(id="file-123")

    extractor = llm.OpenAICoreExtractor.__new__(llm.OpenAICoreExtractor)
    extractor.client = SimpleNamespace(files=SimpleNamespace(create=create_file))
    image = tmp_path / "scan.png"
    image.write_bytes(b"image-bytes")
    document = tmp_path / "report.pdf"
    document.write_bytes(b"pdf-bytes")

    inline = extractor._upload_or_inline(image)
    uploaded = extractor._upload_or_inline(document)

    encoded = base64.b64encode(b"image-bytes").decode("ascii")
    assert inline == {
        "type": "input_image",
        "image_url": f"data:image/png;base64,{encoded}",
        "detail": "high",
    }
    assert uploaded == {"type": "input_file", "file_id": "file-123"}
    assert uploads == [(b"pdf-bytes", "user_data")]


def test_extract_builds_multimodal_content(tmp_path):
    text_path = tmp_path / "note.txt"
    text_path.write_text("clinical note", encoding="utf-8")
    image_path = tmp_path / "scan.jpg"
    image_path.write_bytes(b"image")
    extractor = llm.OpenAICoreExtractor.__new__(llm.OpenAICoreExtractor)
    captured = {}
    extractor._upload_or_inline = lambda path: {"type": "uploaded", "name": path.name}

    def structured(prompt, content, model_cls):
        captured.update(prompt=prompt, content=content, model_cls=model_cls)
        return LLMExtraction(document_notes=["done"])

    extractor._call_structured = structured

    result = extractor.extract([text_path, image_path])

    assert result.document_notes == ["done"]
    assert captured["prompt"] == llm.EXTRACTION_PROMPT
    assert captured["model_cls"] is LLMExtraction
    assert "clinical note" in captured["content"][1]["text"]
    assert captured["content"][-1] == {"type": "uploaded", "name": "scan.jpg"}


def test_extraction_to_case_preserves_facts_provenance_and_prior_imaging():
    extraction = LLMExtraction(
        facts=[
            LLMFact(
                field="patient.age",
                value=42,
                status="observed",
                confidence=0.9,
                sources=[LLMSource(filename="letter.pdf", page=2, excerpt="42 ans")],
            ),
            LLMFact(field="invalid", value="ignored", status="observed", confidence=1.0),
            LLMFact(
                field="unsupported.value",
                value="ignored",
                status="observed",
                confidence=1.0,
            ),
        ],
        prior_imaging=[
            {
                "modality": "CT",
                "region": "abdomen",
                "date": "2025-01-02",
                "summary": "Normal",
                "filename": "prior.pdf",
            },
            {"modality": None, "result": []},
        ],
        contradictions=["allergy conflict"],
        document_notes=["handwritten"],
    )

    case = llm.extraction_to_case(extraction)

    assert case.patient["age"].value == 42
    assert case.patient["age"].status == FieldStatus.observed
    assert case.patient["age"].sources[0].document_id == "llm:letter.pdf"
    assert case.prior_imaging[0].result.value == "Normal"
    assert case.prior_imaging[0].source_document == "prior.pdf"
    assert case.prior_imaging[1].modality.status == FieldStatus.unknown
    assert case.metadata["contradictions"] == ["allergy conflict"]
    assert case.metadata["document_notes"] == ["handwritten"]
