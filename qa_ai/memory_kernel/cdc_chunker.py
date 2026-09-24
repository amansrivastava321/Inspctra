"""
cdc_chunker.py - Content-Defined Chunking for large logs/traces.

Uses rolling hash (Rabin fingerprint variant) to split at natural
boundaries. Pure Python, no shell, no subprocess.
Chunks are deduplicated by hash before storage.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Generator, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default CDC params
_DEFAULT_MIN_CHUNK = 512      # bytes
_DEFAULT_MAX_CHUNK = 8192     # bytes
_DEFAULT_TARGET_CHUNK = 2048  # bytes (~1/gear trigger probability)
_GEAR_MOD = 0x1000            # 4096


@dataclass
class Chunk:
    index: int
    offset: int
    length: int
    content_hash: str    # sha256 hex
    data: bytes          # raw chunk bytes


def _gear_hash(data: bytes, start: int, window: int = 64) -> int:
    """
    Simple gear-hash step for CDC boundary detection.
    XORs bytes in a sliding window with position-dependent multipliers.
    """
    h = 0
    end = min(start + window, len(data))
    for i in range(start, end):
        h = (h * 31 + data[i]) & 0xFFFFFFFF
    return h


def chunk_bytes(
    data: bytes,
    min_size: int = _DEFAULT_MIN_CHUNK,
    max_size: int = _DEFAULT_MAX_CHUNK,
    target_mask: int = _GEAR_MOD - 1,
) -> List[Chunk]:
    """
    Split data into variable-size chunks using rolling hash.
    Returns list of Chunk objects.
    """
    if not data:
        return []

    chunks: List[Chunk] = []
    offset = 0
    chunk_index = 0
    n = len(data)

    while offset < n:
        # Start of new chunk
        start = offset
        pos = start + min_size  # skip min_size bytes

        # Find boundary via rolling hash
        while pos < n and (pos - start) < max_size:
            h = _gear_hash(data, pos)
            if (h & target_mask) == 0:
                pos += 1
                break
            pos += 1

        chunk_data = data[start:pos]
        ch = hashlib.sha256(chunk_data).hexdigest()[:32]
        chunks.append(Chunk(
            index=chunk_index,
            offset=start,
            length=len(chunk_data),
            content_hash=ch,
            data=chunk_data,
        ))
        chunk_index += 1
        offset = pos

    return chunks


_MAX_INPUT_BYTES = 512 * 1024 * 1024  # 512 MB hard ceiling for chunking


def chunk_text(
    text: str,
    min_size: int = _DEFAULT_MIN_CHUNK,
    max_size: int = _DEFAULT_MAX_CHUNK,
    encoding: str = "utf-8",
    max_input_bytes: int = _MAX_INPUT_BYTES,
) -> List[Chunk]:
    """Chunk text string (UTF-8 encoded). Input capped at max_input_bytes."""
    data = text.encode(encoding, errors="replace")
    if len(data) > max_input_bytes:
        data = data[:max_input_bytes]
        logger.warning("chunk_text: input truncated to %d bytes", max_input_bytes)
    return chunk_bytes(data, min_size=min_size, max_size=max_size)


def chunk_log_file(
    content: bytes,
    min_size: int = _DEFAULT_MIN_CHUNK,
    max_size: int = _DEFAULT_MAX_CHUNK,
) -> List[Chunk]:
    """
    Chunk log file content.
    Tries to split at newline boundaries first (line-aware CDC).
    """
    if not content:
        return []

    # Line-aware: align chunk boundaries to nearest newline
    lines = content.split(b"\n")
    current: List[bytes] = []
    current_size = 0
    all_chunks: List[Chunk] = []
    offset = 0

    for line in lines:
        line_data = line + b"\n"
        current.append(line_data)
        current_size += len(line_data)

        if current_size >= min_size:
            # Check if we should cut here
            chunk_data = b"".join(current)
            if current_size >= max_size or _should_cut(chunk_data, min_size):
                ch = hashlib.sha256(chunk_data).hexdigest()[:32]
                all_chunks.append(Chunk(
                    index=len(all_chunks),
                    offset=offset,
                    length=len(chunk_data),
                    content_hash=ch,
                    data=chunk_data,
                ))
                offset += len(chunk_data)
                current = []
                current_size = 0

    # Remaining
    if current:
        chunk_data = b"".join(current)
        ch = hashlib.sha256(chunk_data).hexdigest()[:32]
        all_chunks.append(Chunk(
            index=len(all_chunks),
            offset=offset,
            length=len(chunk_data),
            content_hash=ch,
            data=chunk_data,
        ))

    return all_chunks


def _should_cut(data: bytes, min_size: int) -> bool:
    """Trigger cut if gear hash of last 64 bytes has low bits clear."""
    if len(data) < min_size:
        return False
    h = _gear_hash(data, max(0, len(data) - 64))
    return (h & (_GEAR_MOD - 1)) == 0


def deduplicate_chunks(chunks: List[Chunk]) -> Tuple[List[Chunk], int]:
    """
    Remove exact-duplicate chunks (same content_hash).
    Returns (unique_chunks, dedup_count).
    """
    seen: set = set()
    unique: List[Chunk] = []
    dedup = 0
    for chunk in chunks:
        if chunk.content_hash not in seen:
            seen.add(chunk.content_hash)
            unique.append(chunk)
        else:
            dedup += 1
    return unique, dedup


def chunk_summary(chunks: List[Chunk]) -> dict:
    """Return stats about a chunk list."""
    if not chunks:
        return {"count": 0, "total_bytes": 0, "avg_bytes": 0, "unique_hashes": 0}
    sizes = [c.length for c in chunks]
    hashes = {c.content_hash for c in chunks}
    return {
        "count": len(chunks),
        "total_bytes": sum(sizes),
        "avg_bytes": round(sum(sizes) / len(sizes), 1),
        "min_bytes": min(sizes),
        "max_bytes": max(sizes),
        "unique_hashes": len(hashes),
        "dedup_ratio": round(1 - len(hashes) / len(chunks), 3) if chunks else 0.0,
    }
