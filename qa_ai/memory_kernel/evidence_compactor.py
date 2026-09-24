"""
evidence_compactor.py - Compact raw evidence for minimal storage.

Screenshots → WebP thumbnail (Pillow required).
Logs → error excerpt + zstd/gzip compression.
API → status + schema hash + error excerpt only.
DB → deltas only.
AI → task/model/latency/summary (no raw prompt).

No shell. No subprocess. No eval.
"""
from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from qa_ai.memory_kernel.memory_privacy import redact_text, safe_artifact_path

logger = logging.getLogger(__name__)

# ── Screenshot compaction ──────────────────────────────────────────────────────

def compact_screenshot(
    image_bytes: bytes,
    thumbnail_width: int = 320,
    webp_quality: int = 35,
) -> Tuple[Optional[bytes], str]:
    """
    Return (webp_thumbnail_bytes, format_tag).
    Returns (None, "capability_gap") if Pillow not installed.
    """
    try:
        from PIL import Image  # type: ignore
        buf = io.BytesIO(image_bytes)
        img = Image.open(buf).convert("RGB")
        aspect = img.height / img.width if img.width > 0 else 1.0
        new_h = int(thumbnail_width * aspect)
        img = img.resize((thumbnail_width, new_h), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="WebP", quality=webp_quality)
        return (out.getvalue(), "webp_thumbnail")
    except ImportError:
        return (None, "capability_gap")
    except Exception as exc:
        logger.debug("compact_screenshot error: %s", exc)
        return (None, "error")


def compact_screenshot_file(
    src_path: str,
    artifact_root: Path,
    thumbnail_width: int = 320,
    webp_quality: int = 35,
) -> Dict[str, Any]:
    """
    Compact screenshot at src_path. Returns metadata dict.
    No path traversal — validates against artifact_root.
    """
    safe = safe_artifact_path(artifact_root, src_path)
    if safe is None:
        return {"status": "blocked", "reason": "path_traversal"}
    if not safe.exists():
        return {"status": "missing", "path": src_path}

    original_bytes = safe.read_bytes()
    original_size = len(original_bytes)

    thumb, tag = compact_screenshot(original_bytes, thumbnail_width, webp_quality)
    if thumb is None:
        return {
            "status": tag,
            "original_size": original_size,
            "compact_size": original_size,
        }

    compact_size = len(thumb)
    return {
        "status": "ok",
        "format": tag,
        "original_size": original_size,
        "compact_size": compact_size,
        "savings_bytes": original_size - compact_size,
        "ratio": round(original_size / compact_size, 2) if compact_size > 0 else 1.0,
        "thumbnail_bytes": thumb,
    }


# ── Log compaction ─────────────────────────────────────────────────────────────

def compact_log(
    log_text: str,
    context_lines: int = 30,
    compress: bool = True,
) -> Dict[str, Any]:
    """
    Extract error/warning lines with context. Redact secrets. Compress.
    """
    redacted = redact_text(log_text)
    lines = redacted.splitlines()
    error_indices = [
        i for i, l in enumerate(lines)
        if any(kw in l.lower() for kw in ("error", "exception", "traceback", "fail", "critical"))
    ]

    # Gather context around each error index
    kept_indices = set()
    for idx in error_indices:
        for j in range(max(0, idx - context_lines // 2), min(len(lines), idx + context_lines // 2 + 1)):
            kept_indices.add(j)

    if not kept_indices:
        # Keep last N lines
        kept_indices = set(range(max(0, len(lines) - context_lines), len(lines)))

    excerpt = "\n".join(lines[i] for i in sorted(kept_indices))
    original_size = len(log_text.encode())
    excerpt_bytes = excerpt.encode("utf-8", errors="replace")

    if compress:
        compressed, algo = _compress(excerpt_bytes)
    else:
        compressed = excerpt_bytes
        algo = "none"

    return {
        "status": "ok",
        "algorithm": algo,
        "original_lines": len(lines),
        "kept_lines": len(kept_indices),
        "original_size": original_size,
        "compact_size": len(compressed),
        "ratio": round(original_size / len(compressed), 2) if compressed else 1.0,
        "compressed": compressed,
        "error_line_count": len(error_indices),
    }


_MAX_DECOMPRESS_BYTES = 10 * 1024 * 1024  # 10 MB hard ceiling


def decompress_log(data: bytes, algorithm: str) -> str:
    """Decompress a log excerpt. Returns empty string on failure.
    Output is capped at 10 MB to prevent decompression-bomb DoS."""
    try:
        if algorithm == "zstd":
            import zstandard as zstd  # type: ignore
            raw = zstd.ZstdDecompressor().decompress(data, max_output_size=_MAX_DECOMPRESS_BYTES)
            return raw.decode("utf-8", errors="replace")
        if algorithm == "gzip":
            import gzip
            raw = gzip.decompress(data)
            return raw[:_MAX_DECOMPRESS_BYTES].decode("utf-8", errors="replace")
        return data[:_MAX_DECOMPRESS_BYTES].decode("utf-8", errors="replace")
    except Exception as exc:
        logger.debug("decompress_log error: %s", exc)
        return ""


def _compress(data: bytes) -> Tuple[bytes, str]:
    """Try zstd, then gzip, then none."""
    try:
        import zstandard as zstd  # type: ignore
        compressed = zstd.ZstdCompressor(level=3).compress(data)
        return compressed, "zstd"
    except ImportError:
        pass
    try:
        import gzip
        compressed = gzip.compress(data, compresslevel=6)
        return compressed, "gzip"
    except Exception:
        pass
    return data, "none"


# ── API compaction ─────────────────────────────────────────────────────────────

def compact_api_evidence(
    status_code: int,
    response_body: Any,
    headers: Optional[Dict[str, str]] = None,
    max_error_bytes: int = 512,
) -> Dict[str, Any]:
    """
    Store status + schema hash + error excerpt only.
    Never stores full response.
    """
    from qa_ai.memory_kernel.fingerprint_engine import _extract_json_schema, _text_hash

    schema_shape = _extract_json_schema(response_body)
    schema_hash = _text_hash(json.dumps(schema_shape, sort_keys=True))

    error_excerpt = ""
    if status_code >= 400:
        try:
            raw = json.dumps(response_body, default=str)
            error_excerpt = redact_text(raw[:max_error_bytes])
        except Exception:
            pass

    # Safe headers (drop auth)
    safe_headers: Dict[str, str] = {}
    if headers:
        for k, v in headers.items():
            if k.lower() not in ("authorization", "cookie", "x-api-key", "x-auth-token"):
                safe_headers[k.lower()] = v[:200]

    return {
        "status_code": status_code,
        "schema_hash": schema_hash,
        "error_excerpt": error_excerpt,
        "headers": safe_headers,
    }


# ── DB compaction ─────────────────────────────────────────────────────────────

def compact_db_evidence(
    table_name: str,
    before_count: int,
    after_count: int,
    changed_keys: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Store only row count deltas. No full table dumps."""
    return {
        "table": table_name,
        "before_count": before_count,
        "after_count": after_count,
        "delta": after_count - before_count,
        "changed_keys": (changed_keys or [])[:20],
    }


# ── AI output compaction ──────────────────────────────────────────────────────

def compact_ai_evidence(
    task: str,
    model: str,
    latency_ms: float,
    output_summary: str,
    status: str = "ok",
) -> Dict[str, Any]:
    """
    Store task/model/latency/redacted summary. Never stores raw prompt.
    output_summary is caller's responsibility to not contain PII/secrets.
    """
    return {
        "task": task,
        "model": model,
        "latency_ms": round(latency_ms, 1),
        "status": status,
        "summary": redact_text(output_summary[:500]),
    }
