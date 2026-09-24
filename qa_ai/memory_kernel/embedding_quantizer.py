"""
embedding_quantizer.py - float32 → int8 quantization for compact embedding storage.

Uses numpy if available, pure Python fallback.
No FAISS required in MVP.
"""
from __future__ import annotations

import hashlib
import struct
from typing import List, Optional, Tuple

# ── Numpy or pure-Python ──────────────────────────────────────────────────────

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


def quantize_float32_to_int8(vector: List[float]) -> bytes:
    """Convert float32 vector to int8 blob. Returns raw bytes."""
    if not vector:
        return b""
    if _HAS_NUMPY:
        arr = np.array(vector, dtype=np.float32)
        # L2 normalize
        norm = np.linalg.norm(arr)
        if norm > 1e-9:
            arr = arr / norm
        # Scale to int8 range
        scaled = np.clip(arr * 127.0, -128, 127).astype(np.int8)
        return scaled.tobytes()
    else:
        # Pure Python fallback
        norm = sum(x * x for x in vector) ** 0.5
        if norm > 1e-9:
            vector = [x / norm for x in vector]
        clipped = [max(-128, min(127, int(x * 127.0))) for x in vector]
        return struct.pack(f"{len(clipped)}b", *clipped)


def dequantize_int8_to_float32(blob: bytes, dims: int) -> List[float]:
    """Convert int8 blob back to approximate float32 vector."""
    if not blob:
        return []
    if _HAS_NUMPY:
        arr = np.frombuffer(blob, dtype=np.int8).astype(np.float32)
        return (arr / 127.0).tolist()
    else:
        ints = struct.unpack(f"{len(blob)}b", blob)
        return [x / 127.0 for x in ints]


def cosine_similarity_int8(blob_a: bytes, blob_b: bytes) -> float:
    """Approximate cosine similarity between two int8 vectors."""
    if not blob_a or not blob_b or len(blob_a) != len(blob_b):
        return 0.0
    if _HAS_NUMPY:
        a = np.frombuffer(blob_a, dtype=np.int8).astype(np.float32)
        b = np.frombuffer(blob_b, dtype=np.int8).astype(np.float32)
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom < 1e-9:
            return 0.0
        return float(np.dot(a, b) / denom)
    else:
        a = struct.unpack(f"{len(blob_a)}b", blob_a)
        b = struct.unpack(f"{len(blob_b)}b", blob_b)
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a < 1e-9 or norm_b < 1e-9:
            return 0.0
        return dot / (norm_a * norm_b)


def vector_hash(vector: List[float]) -> str:
    """Stable hash of a float vector for deduplication."""
    if not vector:
        return ""
    # Quantize then hash for stability
    blob = quantize_float32_to_int8(vector)
    return hashlib.sha256(blob).hexdigest()[:24]


def matryoshka_slice(vector: List[float], dims: int) -> List[float]:
    """Slice first N dims for matryoshka-style search."""
    return vector[:dims]


def matryoshka_blob(blob: bytes, dims: int) -> bytes:
    """Slice first N int8 values from blob."""
    return blob[:dims]


def top_k_similar(
    query_blob: bytes,
    candidates: List[Tuple[str, bytes]],
    k: int = 5,
    tier1_dims: int = 64,
    use_matryoshka: bool = True,
) -> List[Tuple[str, float]]:
    """
    Find top-k similar blobs using optional matryoshka 2-stage search.

    candidates: list of (id, blob).
    Returns list of (id, score) sorted by score desc.
    """
    if not query_blob or not candidates:
        return []

    if use_matryoshka and tier1_dims > 0:
        # Stage 1: cheap tier-1 search
        q_t1 = matryoshka_blob(query_blob, tier1_dims)
        stage1: List[Tuple[str, float]] = []
        for cid, cblob in candidates:
            c_t1 = matryoshka_blob(cblob, tier1_dims)
            score = cosine_similarity_int8(q_t1, c_t1)
            stage1.append((cid, score))
        stage1.sort(key=lambda x: x[1], reverse=True)
        # Stage 2: full rerank on top 2k
        rerank_ids = {cid for cid, _ in stage1[:k * 2]}
        scores: List[Tuple[str, float]] = []
        for cid, cblob in candidates:
            if cid in rerank_ids:
                score = cosine_similarity_int8(query_blob, cblob)
                scores.append((cid, score))
    else:
        scores = [
            (cid, cosine_similarity_int8(query_blob, cblob))
            for cid, cblob in candidates
        ]

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:k]
