from pathlib import Path
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
