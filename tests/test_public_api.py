from bulkinout import build_radiology_case, run_request, write_core_outputs, write_request_outputs


def test_public_service_facade_delegates(monkeypatch, tmp_path):
    from bulkinout.core import service as core_service
    from bulkinout.request import service as request_service

    calls = []
    extractor = object()
    decision_engine = object()
    monkeypatch.setattr(
        core_service,
        "build_radiology_case",
        lambda input_dir, **kwargs: calls.append(("core", input_dir, kwargs)) or "core-result",
    )
    monkeypatch.setattr(
        request_service,
        "run_request",
        lambda input_dir, **kwargs: (
            calls.append(("request", input_dir, kwargs)) or "request-result"
        ),
    )

    assert build_radiology_case(tmp_path, model="model", extractor=extractor) == "core-result"
    assert (
        run_request(
            tmp_path,
            reference_dir=tmp_path / "reference",
            model="model",
            extraction_model="extraction-model",
            decision_model="decision-model",
            extractor=extractor,
            decision_engine=decision_engine,
        )
        == "request-result"
    )
    assert calls == [
        ("core", tmp_path, {"model": "model", "extractor": extractor}),
        (
            "request",
            tmp_path,
            {
                "reference_dir": tmp_path / "reference",
                "model": "model",
                "extraction_model": "extraction-model",
                "decision_model": "decision-model",
                "answers_path": None,
                "extractor": extractor,
                "decision_engine": decision_engine,
            },
        ),
    ]


def test_public_output_facade_delegates(monkeypatch, tmp_path):
    from bulkinout import output

    calls = []
    monkeypatch.setattr(
        output,
        "write_core_outputs",
        lambda result, output_dir: calls.append(("core", result, output_dir)),
    )
    monkeypatch.setattr(
        output,
        "write_request_outputs",
        lambda result, output_dir: calls.append(("request", result, output_dir)),
    )

    write_core_outputs("core-result", tmp_path)
    write_request_outputs("request-result", tmp_path)

    assert calls == [
        ("core", "core-result", tmp_path),
        ("request", "request-result", tmp_path),
    ]
