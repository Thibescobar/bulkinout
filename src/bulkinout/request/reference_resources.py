"""Locate and read explicit or distribution-provided reference scenarios."""

from __future__ import annotations

from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

from ..errors import ReferenceDataError

ReferenceRoot = Path | Traversable


def _default_reference_root() -> ReferenceRoot:
    packaged = resources.files("bulkinout").joinpath("reference_data", "scenarios")
    if packaged.is_dir():
        return packaged

    # Editable source checkouts do not run the wheel build hook.
    repository_reference = Path(__file__).resolve().parents[3] / "reference" / "scenarios"
    if repository_reference.is_dir():
        return repository_reference
    raise ReferenceDataError("The packaged reference scenarios are unavailable.")


def _explicit_reference_root(reference_dir: Path) -> Path:
    try:
        if not reference_dir.exists():
            raise ReferenceDataError(f"Reference directory does not exist: {reference_dir}")
        if not reference_dir.is_dir():
            raise ReferenceDataError(f"Reference path is not a directory: {reference_dir}")
    except OSError as error:
        raise ReferenceDataError(
            f"Reference directory cannot be inspected: {reference_dir}: {error}"
        ) from error
    return reference_dir


def load_reference_documents(reference_dir: Path | None) -> list[tuple[str, str]]:
    """Return named YAML documents from an override or the packaged reference."""

    root = (
        _default_reference_root()
        if reference_dir is None
        else _explicit_reference_root(reference_dir)
    )
    label = "packaged reference" if reference_dir is None else str(reference_dir)
    try:
        scenario_files = sorted(
            (path for path in root.iterdir() if path.name.endswith(".yaml")),
            key=lambda path: path.name,
        )
    except OSError as error:
        raise ReferenceDataError(f"Reference directory cannot be read: {label}: {error}") from error
    if not scenario_files:
        raise ReferenceDataError(f"Reference directory contains no YAML scenarios: {label}")

    documents: list[tuple[str, str]] = []
    for path in scenario_files:
        try:
            documents.append((path.name, path.read_text(encoding="utf-8")))
        except (OSError, UnicodeError) as error:
            raise ReferenceDataError(f"Reference file cannot be read: {path}: {error}") from error
    return documents
