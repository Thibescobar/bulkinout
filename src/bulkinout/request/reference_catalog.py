from __future__ import annotations
from pathlib import Path
import yaml

def build_catalog(reference_dir: Path) -> list[dict]:
    out = []
    for path in sorted(reference_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        out.append({
            "id": data.get("id"),
            "version": data.get("version"),
            "title": data.get("title"),
            "status": data.get("status"),
            "source_file": path.name,
            "candidate_count": len(data.get("candidates", [])),
            "question_count": len(data.get("questions", [])),
            "source_count": len(data.get("sources", [])),
        })
    return out
