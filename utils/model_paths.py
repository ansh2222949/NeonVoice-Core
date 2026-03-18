"""Helpers for resolving local model caches to portable defaults."""

from __future__ import annotations

import os
from pathlib import Path

from utils.storage_paths import BASE_DIR


LOCAL_EMBEDDING_DIR = Path(BASE_DIR) / "models" / "embeddings" / "all-MiniLM-L6-v2"
REMOTE_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def resolve_embedding_model() -> str:
    if LOCAL_EMBEDDING_DIR.exists():
        return str(LOCAL_EMBEDDING_DIR)
    return REMOTE_EMBEDDING_MODEL


def configure_embedding_runtime() -> str:
    model_source = resolve_embedding_model()
    if Path(model_source) == LOCAL_EMBEDDING_DIR:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    return model_source
