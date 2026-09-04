"""Deterministic hashes shared across Bulkinout components."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_text(value: str) -> str:
    """Hash UTF-8 text without retaining the original value."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_python_tree(root: Path) -> str:
    """Fingerprint the names and contents of all Python sources below a directory."""

    digest = hashlib.sha256()
    sources = sorted(root.rglob("*.py"), key=lambda path: path.relative_to(root).as_posix())
    for source in sources:
        relative_name = source.relative_to(root).as_posix().encode("utf-8")
        content = source.read_bytes()
        for value in (relative_name, content):
            digest.update(len(value).to_bytes(8, "big"))
            digest.update(value)
    return digest.hexdigest()
