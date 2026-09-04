from pathlib import Path
from bulkinout.request.golden import discover_golden_cases, run_golden_case

ROOT = Path(__file__).parents[1]

def test_golden_cases_exist():
    assert len(discover_golden_cases(ROOT / "tests" / "golden")) >= 10

def test_all_golden_cases_pass():
    failures = []
    for path in discover_golden_cases(ROOT / "tests" / "golden"):
        result = run_golden_case(path, ROOT / "reference" / "scenarios")
        if not result.passed:
            failures.append((result.case_id, result.errors))
    assert not failures, failures
