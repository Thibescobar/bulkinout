from pathlib import Path

import pytest

from bulkinout.errors import ReferenceDataError
from bulkinout.request.reference_catalog import build_catalog


def test_reference_has_at_least_16_scenarios():
    ref = Path(__file__).parents[1] / "reference" / "scenarios"
    catalog = build_catalog(ref)
    assert len(catalog) >= 16


def test_every_scenario_is_versioned_and_sourced():
    ref = Path(__file__).parents[1] / "reference" / "scenarios"
    catalog = build_catalog(ref)
    assert all(x["version"] for x in catalog)
    assert all(x["status"] == "needs_local_validation" for x in catalog)
    assert all(x["source_count"] >= 1 for x in catalog)


def test_catalog_rejects_a_non_mapping_scenario(tmp_path):
    (tmp_path / "invalid.yaml").write_text("- invalid\n", encoding="utf-8")

    with pytest.raises(ReferenceDataError, match="must contain a mapping"):
        build_catalog(tmp_path)
