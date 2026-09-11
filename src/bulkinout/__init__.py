"""Public Python interface for Bulkinout."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .core.interfaces import CoreExtractor
from .core.normalization import TerminologyNormalizer
from .errors import BulkinoutError, ConfigurationError, InputError, ReferenceDataError
from .request.interfaces import RequestDecisionEngine
from .request.types import DecisionMode

if TYPE_CHECKING:
    from .core.service import CoreResult
    from .request.service import RequestResult

__version__ = "0.1.0"

__all__ = [
    "BulkinoutError",
    "ConfigurationError",
    "CoreExtractor",
    "DecisionMode",
    "InputError",
    "ReferenceDataError",
    "RequestDecisionEngine",
    "TerminologyNormalizer",
    "build_radiology_case",
    "run_request",
    "run_request_from_core",
    "write_core_outputs",
    "write_request_outputs",
]


def build_radiology_case(
    input_dir: Path,
    model: str | None = None,
    *,
    cold: bool = False,
    extractor: CoreExtractor | None = None,
    terminology_normalizer: TerminologyNormalizer | None = None,
) -> CoreResult:
    """Run the Core service without eagerly importing provider dependencies."""

    from .core.service import build_radiology_case as build

    return build(
        input_dir,
        model=model,
        cold=cold,
        extractor=extractor,
        terminology_normalizer=terminology_normalizer,
    )


def run_request(
    input_dir: Path,
    *,
    reference_dir: Path | None = None,
    model: str | None = None,
    extraction_model: str | None = None,
    decision_model: str | None = None,
    cold: bool = False,
    answers_path: Path | None = None,
    extractor: CoreExtractor | None = None,
    decision_engine: RequestDecisionEngine | None = None,
    terminology_normalizer: TerminologyNormalizer | None = None,
    decision_mode: DecisionMode = "llm",
) -> RequestResult:
    """Run the Request service without eagerly importing provider dependencies."""

    from .request.service import run_request as run

    return run(
        input_dir,
        reference_dir=reference_dir,
        model=model,
        extraction_model=extraction_model,
        decision_model=decision_model,
        cold=cold,
        answers_path=answers_path,
        extractor=extractor,
        decision_engine=decision_engine,
        terminology_normalizer=terminology_normalizer,
        decision_mode=decision_mode,
    )


def run_request_from_core(
    core_result: CoreResult,
    *,
    reference_dir: Path | None = None,
    model: str | None = None,
    decision_model: str | None = None,
    cold: bool = False,
    answers_path: Path | None = None,
    decision_engine: RequestDecisionEngine | None = None,
    terminology_normalizer: TerminologyNormalizer | None = None,
    decision_mode: DecisionMode = "llm",
) -> RequestResult:
    """Run Request from an existing Core result without repeating extraction."""

    from .request.service import run_request_from_core as run

    return run(
        core_result,
        reference_dir=reference_dir,
        model=model,
        decision_model=decision_model,
        cold=cold,
        answers_path=answers_path,
        decision_engine=decision_engine,
        terminology_normalizer=terminology_normalizer,
        decision_mode=decision_mode,
    )


def write_core_outputs(result: CoreResult, output_dir: Path) -> None:
    """Write Core snapshots through the shared output module."""

    from .output import write_core_outputs as write

    write(result, output_dir)


def write_request_outputs(result: RequestResult, output_dir: Path) -> None:
    """Write Request snapshots through the shared output module."""

    from .output import write_request_outputs as write

    write(result, output_dir)
