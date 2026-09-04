from pathlib import Path

import pytest

from bulkinout.errors import ReferenceDataError
from bulkinout.request import reference_resources
from bulkinout.request.reference_catalog import build_catalog
from bulkinout.request.reference_engine import ReferenceEngine


def test_default_reference_loads_all_packaged_scenarios():
    assert len(build_catalog()) == 18


def test_default_reference_prefers_distribution_resources(monkeypatch, tmp_path):
    scenario_dir = tmp_path / "reference_data" / "scenarios"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "packaged.yaml").write_text(
        "id: packaged\ntitle: Packaged scenario\n", encoding="utf-8"
    )
    monkeypatch.setattr(reference_resources.resources, "files", lambda package: tmp_path)

    assert [item["id"] for item in ReferenceEngine().scenarios] == ["packaged"]


def test_missing_distribution_resources_fail_clearly(monkeypatch, tmp_path):
    monkeypatch.setattr(reference_resources.resources, "files", lambda package: tmp_path)
    fake_module = tmp_path / "checkout" / "src" / "bulkinout" / "request" / "module.py"
    monkeypatch.setattr(reference_resources, "__file__", str(fake_module))

    with pytest.raises(ReferenceDataError, match="packaged reference scenarios are unavailable"):
        ReferenceEngine()


def test_explicit_reference_override_is_preserved(tmp_path):
    scenario = tmp_path / "custom.yaml"
    scenario.write_text("id: custom\ntitle: Custom scenario\n", encoding="utf-8")

    engine = ReferenceEngine(tmp_path)

    assert [item["id"] for item in engine.scenarios] == ["custom"]


def test_missing_reference_directory_fails_clearly(tmp_path):
    missing = tmp_path / "missing"

    with pytest.raises(ReferenceDataError, match="Reference directory does not exist"):
        ReferenceEngine(missing)


def test_reference_path_must_be_a_directory(tmp_path):
    reference_file = tmp_path / "scenario.yaml"
    reference_file.write_text("id: custom\ntitle: Custom scenario\n", encoding="utf-8")

    with pytest.raises(ReferenceDataError, match="Reference path is not a directory"):
        ReferenceEngine(reference_file)


def test_empty_reference_directory_fails_clearly(tmp_path):
    with pytest.raises(ReferenceDataError, match="contains no YAML scenarios"):
        ReferenceEngine(tmp_path)


def test_unreadable_reference_directory_fails_clearly(monkeypatch, tmp_path):
    original_iterdir = Path.iterdir

    def fail_for_reference(path: Path):
        if path == tmp_path:
            raise OSError("permission denied")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", fail_for_reference)

    with pytest.raises(ReferenceDataError, match="Reference directory cannot be read"):
        ReferenceEngine(tmp_path)


def test_uninspectable_reference_directory_fails_clearly(monkeypatch, tmp_path):
    def fail_to_inspect(path: Path):
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "exists", fail_to_inspect)

    with pytest.raises(ReferenceDataError, match="Reference directory cannot be inspected"):
        ReferenceEngine(tmp_path)


def test_unreadable_reference_file_fails_clearly(monkeypatch, tmp_path):
    scenario = tmp_path / "scenario.yaml"
    scenario.write_text("id: custom\ntitle: Custom scenario\n", encoding="utf-8")
    original_read_text = Path.read_text

    def fail_for_scenario(path: Path, *args, **kwargs):
        if path == scenario:
            raise OSError("permission denied")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_for_scenario)

    with pytest.raises(ReferenceDataError, match="Reference file cannot be read"):
        ReferenceEngine(tmp_path)


def test_invalid_yaml_fails_with_reference_error(tmp_path):
    (tmp_path / "invalid.yaml").write_text("entry: [\n", encoding="utf-8")

    with pytest.raises(ReferenceDataError, match="contains invalid YAML"):
        ReferenceEngine(tmp_path)
