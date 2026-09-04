from __future__ import annotations
from pathlib import Path

SUPPORTED = {".pdf", ".txt", ".md", ".png", ".jpg", ".jpeg", ".webp"}

def collect_files(input_dir: Path) -> list[Path]:
    return [
        p for p in sorted(input_dir.rglob("*"))
        if p.is_file() and p.suffix.lower() in SUPPORTED
    ]
