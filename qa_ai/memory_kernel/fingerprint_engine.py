"""
fingerprint_engine.py - Generate compact fingerprints for evidence and state.

Security:
- No shell. No subprocess. No eval.
- blake3 → sha256 fallback.
- imagehash + Pillow → manual fallback.
- Never stores full content by default.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import struct
from typing import Any, Dict, List, Optional, Tuple

from qa_ai.memory_kernel.memory_privacy import redact_text

logger = logging.getLogger(__name__)

# ── Hash helpers ───────────────────────────────────────────────────────────────

def _content_hash(data: bytes) -> str:
    """blake3 if available, else sha256."""
    try:
        import blake3  # type: ignore
        return blake3.blake3(data).hexdigest()[:48]
    except ImportError:
        return hashlib.sha256(data).hexdigest()[:48]


def _text_hash(text: str) -> str:
    return _content_hash(text.encode("utf-8", errors="replace"))


# ── 1. Content hash ────────────────────────────────────────────────────────────

def fingerprint_bytes(data: bytes) -> str:
    return _content_hash(data)


def fingerprint_text(text: str) -> str:
    return _text_hash(text)


# ── 2. Screenshot perceptual hash ──────────────────────────────────────────────

def perceptual_hash_screenshot(image_path: str) -> Tuple[str, bool]:
    """
    Return (phash_hex, is_real_phash).
    is_real_phash=False if Pillow/imagehash unavailable.
    """
    try:
        from PIL import Image  # type: ignore
        try:
            import imagehash  # type: ignore
            img = Image.open(image_path).convert("RGB")
            ph = imagehash.phash(img)
            return (str(ph), True)
        except ImportError:
            pass

        # Manual average hash fallback
        from PIL import Image as _Image  # type: ignore
        img = _Image.open(image_path).convert("L").resize((8, 8))
        pixels = list(img.getdata())
        avg = sum(pixels) / len(pixels)
        bits = "".join("1" if p >= avg else "0" for p in pixels)
        # Pack bits to hex
        val = int(bits, 2)
        return (format(val, "016x"), True)
    except ImportError:
        return ("", False)
    except Exception as exc:
        logger.debug("perceptual_hash_screenshot error: %s", exc)
        return ("", False)


def perceptual_hash_bytes(image_bytes: bytes) -> Tuple[str, bool]:
    """Try to compute phash from raw PNG/JPEG bytes."""
    try:
        import io
        from PIL import Image  # type: ignore
        buf = io.BytesIO(image_bytes)
        try:
            import imagehash  # type: ignore
            img = Image.open(buf).convert("RGB")
            ph = imagehash.phash(img)
            return (str(ph), True)
        except ImportError:
            pass
        buf.seek(0)
        img = Image.open(buf).convert("L").resize((8, 8))
        pixels = list(img.getdata())
        avg = sum(pixels) / len(pixels)
        bits = "".join("1" if p >= avg else "0" for p in pixels)
        return (format(int(bits, 2), "016x"), True)
    except ImportError:
        return ("", False)
    except Exception as exc:
        logger.debug("perceptual_hash_bytes error: %s", exc)
        return ("", False)


# ── 3. Log fingerprint ────────────────────────────────────────────────────────

_UUID_PATTERN = re.compile(
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I
)
_TIMESTAMP_PATTERN = re.compile(
    r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?'
)
_IP_PATTERN = re.compile(r'\b\d{1,3}(?:\.\d{1,3}){3}\b')
_HEX_ID = re.compile(r'\b[0-9a-f]{12,}\b', re.I)


def _normalize_log_line(line: str) -> str:
    line = _TIMESTAMP_PATTERN.sub("<TS>", line)
    line = _UUID_PATTERN.sub("<UUID>", line)
    line = _IP_PATTERN.sub("<IP>", line)
    line = _HEX_ID.sub("<HEX>", line)
    return line.strip()


def fingerprint_log(
    log_text: str,
    error_only: bool = True,
    max_lines: int = 200,
) -> str:
    """
    Hash normalized error/warning lines from log.
    Ignores timestamps, UUIDs, IPs.
    Redacts secrets first.
    """
    clean = redact_text(log_text)
    lines = clean.splitlines()[:max_lines]
    if error_only:
        lines = [
            l for l in lines
            if any(kw in l.lower() for kw in ("error", "exception", "traceback", "fail", "critical", "warn"))
        ]
    normalized = [_normalize_log_line(l) for l in lines if l.strip()]
    combined = "\n".join(normalized)
    return _text_hash(combined)


# ── 4. API fingerprint ────────────────────────────────────────────────────────

def fingerprint_api_response(
    status_code: int,
    response_body: Optional[Any],
    max_error_bytes: int = 512,
) -> str:
    """
    Hash: status + schema shape + first N bytes of error body.
    Never stores full response.
    """
    schema_shape = _extract_json_schema(response_body)
    error_excerpt = ""
    if status_code >= 400 and response_body:
        try:
            raw = json.dumps(response_body, default=str)
            error_excerpt = raw[:max_error_bytes]
        except Exception:
            pass
    fingerprint_data = {
        "status": status_code,
        "schema": schema_shape,
        "error": error_excerpt,
    }
    return _text_hash(json.dumps(fingerprint_data, sort_keys=True))


def _extract_json_schema(data: Any, _depth: int = 0) -> Any:
    """Extract shape (types only, no values) of a JSON structure."""
    if _depth > 5:
        return "..."
    if isinstance(data, dict):
        return {k: _extract_json_schema(data[k], _depth + 1) for k in sorted(data.keys())}
    if isinstance(data, list):
        return ["array", len(data)]
    if data is None:
        return "null"
    return type(data).__name__


# ── 5. DB fingerprint ─────────────────────────────────────────────────────────

def fingerprint_db_state(
    table_name: str,
    row_count: int,
    schema: Optional[Dict[str, str]] = None,
    sample_hashes: Optional[List[str]] = None,
) -> str:
    """Row count + schema hash + optional row sample hashes. No full dumps."""
    data = {
        "table": table_name,
        "rows": row_count,
        "schema": schema or {},
        "samples": sorted(sample_hashes or [])[:10],
    }
    return _text_hash(json.dumps(data, sort_keys=True))


# ── 6. Workflow fingerprint ───────────────────────────────────────────────────

def fingerprint_workflow(
    steps: List[Dict[str, Any]],
) -> str:
    """Hash ordered sequence of step_id/action/verdict."""
    seq = []
    for step in steps:
        seq.append({
            "step": step.get("step_id", step.get("id", "")),
            "action": step.get("action", step.get("action_type", "")),
            "verdict": step.get("verdict", step.get("status", "")),
        })
    return _text_hash(json.dumps(seq, sort_keys=True))


# ── 7. Connector fingerprint ──────────────────────────────────────────────────

def fingerprint_connector(
    connector_type: str,
    status: str,
    readiness: bool,
    capability_gaps: Optional[List[str]] = None,
) -> str:
    data = {
        "type": connector_type,
        "status": status,
        "ready": readiness,
        "gaps": sorted(capability_gaps or []),
    }
    return _text_hash(json.dumps(data, sort_keys=True))


# ── 8. Semantic hash (simhash) ────────────────────────────────────────────────

def semantic_hash(text: str, bits: int = 64) -> str:
    """
    64-bit simhash of token fingerprints.
    Fallback if no embedding model — good for near-duplicate detection.
    """
    tokens = re.split(r'\W+', text.lower())
    tokens = [t for t in tokens if len(t) > 2]
    if not tokens:
        return _text_hash(text)[:16]

    v = [0] * bits
    for token in tokens:
        h = int(hashlib.sha256(token.encode()).hexdigest(), 16)
        for i in range(bits):
            bit = (h >> i) & 1
            v[i] += 1 if bit else -1

    result = 0
    for i in range(bits):
        if v[i] > 0:
            result |= (1 << i)
    return format(result, f"0{bits // 4}x")


# ── Evidence manifest hash ────────────────────────────────────────────────────

def fingerprint_evidence_manifest(
    fingerprint_ids: List[str],
) -> str:
    """Hash ordered list of fingerprint IDs."""
    return _text_hash(json.dumps(sorted(fingerprint_ids)))
