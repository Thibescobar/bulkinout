"""Public Python interface for Bulkinout."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .core.interfaces import CoreExtractor
from .errors import BulkinoutError, ConfigurationError, InputError, ReferenceDataError
from .request.interfaces import RequestDecisionEngine

if TYPE_CHECKING:
    from .core.service import CoreResult
    from .request.service import RequestResult

__version__ = "0.0.0"

__all__ = [
    "BulkinoutError",
    "ConfigurationError",
    "CoreExtractor",
    "InputError",
    "ReferenceDataError",
    "RequestDecisionEngine",
    "build_radiology_case",
    "run_request",
    "write_core_outputs",
    "write_request_outputs",
]


def build_radiology_case(
    input_dir: Path,
    model: str | None = None,
    *,
    extractor: CoreExtractor | None = None,
) -> CoreResult:
    """Run the Core service without eagerly importing provider dependencies."""

    from .core.service import build_radiology_case as build

    return build(input_dir, model=model, extractor=extractor)


def run_request(
    input_dir: Path,
    *,
    reference_dir: Path = Path("reference/scenarios"),
    model: str | None = None,
    extraction_model: str | None = None,
    decision_model: str | None = None,
    answers_path: Path | None = None,
    extractor: CoreExtractor | None = None,
    decision_engine: RequestDecisionEngine | None = None,
) -> RequestResult:
    """Run the Request service without eagerly importing provider dependencies."""

    from .request.service import run_request as run

    return run(
        input_dir,
        reference_dir=reference_dir,
        model=model,
        extraction_model=extraction_model,
        decision_model=decision_model,
        answers_path=answers_path,
        extractor=extractor,
        decision_engine=decision_engine,
    )


def write_core_outputs(result: CoreResult, output_dir: Path) -> None:
    """Write Core snapshots through the shared output module."""

    from .output import write_core_outputs as write

    write(result, output_dir)


def write_request_outputs(result: RequestResult, output_dir: Path) -> None:
    """Write Request snapshots through the shared output module."""

    from .output import write_request_outputs as write

    write(result, output_dir)
