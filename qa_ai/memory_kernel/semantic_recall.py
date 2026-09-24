"""
semantic_recall.py - Index and recall memory via embeddings + simhash fallback.

Store schema: embedding_id, scope_id, source_type, source_id, model,
dimensions, quantization, vector_blob, vector_hash, created_at.

Primary: bge-m3 via task_router.embed().
Fallback: simhash from fingerprint_engine (no model required).
No raw prompts stored. No PII in index keys.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from qa_ai.memory_kernel.fingerprint_engine import semantic_hash
from qa_ai.memory_kernel.embedding_quantizer import (
    quantize_float32_to_int8,
    top_k_similar,
    vector_hash,
)
from qa_ai.memory_kernel.memory_privacy import redact_text

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _try_embed(text: str) -> Optional[List[float]]:
    """
    Try to embed text via task_router.embed().
    Returns None (capability_gap) if unavailable.
    """
    try:
        from qa_ai.task_router import embed  # type: ignore
        result = embed(text)
        if result and isinstance(result, list) and isinstance(result[0], float):
            return result
        return None
    except Exception as exc:
        logger.debug("semantic_recall._try_embed failed: %s", exc)
        return None


# ── Index ───────────────────────────────────────────────────────────────────────

def index_memory(
    store,
    source_type: str,
    source_id: str,
    text: str,
    scope_id: str,
) -> Dict[str, Any]:
    """
    Index a memory record for semantic recall.

    source_type: "fingerprint" | "summary" | "trajectory" | "pattern" | "finding"
    source_id: the record's primary key
    Returns {"indexed": True, "method": "embedding"|"simhash"} or {"indexed": False, "reason": str}.
    """
    safe_text = redact_text(text[:1000])

    # Try real embedding
    vector = _try_embed(safe_text)
    if vector:
        blob = quantize_float32_to_int8(vector)
        vh = vector_hash(vector)
        try:
            store.store_embedding({
                "embedding_id": str(uuid.uuid4()),
                "scope_id": scope_id,
                "source_type": source_type,
                "source_id": source_id,
                "model": "bge-m3",
                "dimensions": len(vector),
                "quantization": "int8",
                "vector_blob": blob,
                "vector_hash": vh,
                "created_at": _now_iso(),
            })
            return {"indexed": True, "method": "embedding", "dims": len(vector)}
        except Exception as exc:
            logger.warning("index_memory: store failed: %s", exc)
            return {"indexed": False, "reason": str(exc)}

    # Simhash fallback
    sh = semantic_hash(safe_text)
    try:
        store.store_embedding({
            "embedding_id": str(uuid.uuid4()),
            "scope_id": scope_id,
            "source_type": source_type,
            "source_id": source_id,
            "model": "simhash",
            "dimensions": 0,
            "quantization": "none",
            "vector_blob": sh[:16].encode("utf-8", errors="replace"),
            "vector_hash": sh,
            "created_at": _now_iso(),
        })
        return {"indexed": True, "method": "simhash"}
    except Exception as exc:
        logger.warning("index_memory: simhash store failed: %s", exc)
        return {"indexed": False, "reason": str(exc)}


# ── Recall ──────────────────────────────────────────────────────────────────────

def recall_similar(
    store,
    query: str,
    scope_id: str,
    source_types: Optional[List[str]] = None,
    top_k: int = 10,
    min_score: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Find top-k similar memory records to query.

    Returns list of {source_type, source_id, score, method}.
    Falls back to simhash if no embeddings available.
    """
    safe_query = redact_text(query[:1000])

    # Load candidates
    if source_types:
        candidates = []
        for st in source_types:
            candidates.extend(store.list_embeddings(scope_id=scope_id, source_type=st))
    else:
        candidates = store.list_embeddings(scope_id=scope_id)

    if not candidates:
        return []

    # Use embedding path if any real-dim records exist
    real_embed = [c for c in candidates if int(c.get("dimensions", 0)) > 0]

    if real_embed:
        query_vector = _try_embed(safe_query)
        if query_vector:
            query_blob = quantize_float32_to_int8(query_vector)
            blob_candidates = [
                (c["source_id"], bytes(c["vector_blob"]) if isinstance(c["vector_blob"], (bytes, bytearray)) else b"")
                for c in real_embed
            ]
            scored = top_k_similar(query_blob, blob_candidates, k=top_k)
            id_map = {c["source_id"]: c for c in real_embed}
            results = []
            for src_id, score in scored:
                if score < min_score:
                    continue
                meta = id_map.get(src_id, {})
                results.append({
                    "source_type": meta.get("source_type", ""),
                    "source_id": src_id,
                    "score": round(float(score), 4),
                    "method": "embedding",
                })
            return results

    # Simhash fallback
    query_hash = semantic_hash(safe_query)
    scored_sh: List[Tuple[float, Dict[str, Any]]] = []
    for c in candidates:
        vh = str(c.get("vector_hash", ""))
        sim = _hex_similarity(query_hash, vh)
        scored_sh.append((sim, c))
    scored_sh.sort(key=lambda x: x[0], reverse=True)

    return [
        {
            "source_type": c.get("source_type", ""),
            "source_id": c.get("source_id", ""),
            "score": round(float(score), 4),
            "method": "simhash",
        }
        for score, c in scored_sh[:top_k]
        if score >= min_score
    ]


def _hex_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    return sum(ca == cb for ca, cb in zip(a[:n], b[:n])) / n


# ── Deduplication ───────────────────────────────────────────────────────────────

def is_duplicate_evidence(
    store,
    scope_id: str,
    content_hash: str,
    text: Optional[str] = None,
    semantic_threshold: float = 0.92,
) -> Tuple[bool, Optional[str]]:
    """
    Check if evidence is duplicate.
    1. Exact content_hash match.
    2. Semantic similarity if text provided.

    Returns (is_duplicate, matching_source_id).
    """
    existing_id = store.find_duplicate_fingerprint(content_hash=content_hash, scope_id=scope_id)
    if existing_id:
        return (True, existing_id)

    if text:
        similar = recall_similar(
            store=store,
            query=text,
            scope_id=scope_id,
            top_k=1,
            min_score=semantic_threshold,
        )
        if similar:
            return (True, similar[0]["source_id"])

    return (False, None)
