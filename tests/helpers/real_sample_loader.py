from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.models.article_fetch import FetchedArticle

REAL_SAMPLES_ROOT = REPO_ROOT / "tests" / "real_samples"


def resolve_real_sample(sample_name: str | None = None) -> Path:
    if sample_name:
        sample_path = REAL_SAMPLES_ROOT / sample_name
        if sample_path.exists():
            return sample_path
    latest_dirs = sorted(REAL_SAMPLES_ROOT.glob("latest_*"), key=lambda item: item.stat().st_mtime, reverse=True) if REAL_SAMPLES_ROOT.exists() else []
    if latest_dirs:
        return latest_dirs[0]
    dated_dirs = sorted([item for item in REAL_SAMPLES_ROOT.iterdir() if item.is_dir()], key=lambda item: item.stat().st_mtime, reverse=True) if REAL_SAMPLES_ROOT.exists() else []
    if dated_dirs:
        return dated_dirs[0]
    raise FileNotFoundError("No saved real samples found under tests/real_samples")


def load_real_sample(sample_name: str | None = None) -> dict[str, Any]:
    sample_dir = resolve_real_sample(sample_name)
    preview_payload = json.loads((sample_dir / "preview.json").read_text(encoding="utf-8"))
    metadata = json.loads((sample_dir / "metadata.json").read_text(encoding="utf-8"))
    articles_payload = json.loads((sample_dir / "articles.json").read_text(encoding="utf-8"))
    return {
        "sample_dir": sample_dir,
        "preview_payload": preview_payload,
        "metadata": metadata,
        "articles": [FetchedArticle(**item) for item in articles_payload.get("articles", [])],
    }
