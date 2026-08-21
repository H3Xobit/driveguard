"""Hash embeddings + guideline retrieval (pgvector optional)."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

DIM = 384
ASSETS = Path(__file__).resolve().parents[1] / "assets"


def embed(text: str) -> np.ndarray:
    """Deterministic 384-d hashing embedder. No model download."""
    vec = np.zeros(DIM, dtype=np.float64)
    tokens = text.lower().split()
    for tok in tokens:
        h = hashlib.sha256(tok.encode()).digest()
        idx = int.from_bytes(h[:2], "big") % DIM
        sign = 1.0 if h[2] % 2 == 0 else -1.0
        vec[idx] += sign
    n = np.linalg.norm(vec)
    if n > 0:
        vec /= n
    return vec


@lru_cache
def load_corpus() -> list[dict]:
    path = ASSETS / "corpus.json"
    return json.loads(path.read_text(encoding="utf-8"))


def retrieve(query: str, top_k: int = 4) -> list[dict]:
    q = embed(query)
    scored: list[tuple[float, dict]] = []
    for chunk in load_corpus():
        v = embed(chunk["text"])
        scored.append((float(q @ v), chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for score, chunk in scored[:top_k]:
        row = dict(chunk)
        row["score"] = round(score, 4)
        out.append(row)
    return out
