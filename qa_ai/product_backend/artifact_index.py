"""
artifact_index.py - Safe artifact file indexer and streamer.

Security:
- All file paths validated with .resolve() + prefix check.
- No path traversal possible: any relative_path that escapes artifacts_dir raises ValueError.
- No execution of artifact files.
- MIME type inferred by extension only (no magic bytes, no subprocess).
- File content streamed in chunks; never loaded fully into memory.
"""
from __future__ import annotations

import logging
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

# Only index these extensions (others are ignored for safety)
_INDEXED_EXTENSIONS = frozenset({
    ".json", ".html", ".txt", ".md", ".csv", ".log",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".pdf", ".zip",
})

_CHUNK_SIZE = 65_536  # 64 KiB per read chunk


class ArtifactIndex:
    """
    Indexes and streams files from the artifacts directory.

    All access is read-only. Path traversal is blocked at resolve time.
    """

    def __init__(self, artifacts_dir: "str | Path") -> None:
        self._base = Path(artifacts_dir).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    # ── public ────────────────────────────────────────────────────────────────

    def list_files(self, subdir: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List artifact files (non-recursive by default, recursive if subdir given).
        Returns metadata dicts — never file content.
        """
        if subdir:
            try:
                scan_root = self._resolve_safe(subdir)
            except ValueError:
                logger.warning("ArtifactIndex.list_files: blocked path %r", subdir)
                return []
        else:
            scan_root = self._base

        if not scan_root.is_dir():
            return []

        results = []
        try:
            for entry in scan_root.rglob("*"):
                if not entry.is_file():
                    continue
                if entry.suffix.lower() not in _INDEXED_EXTENSIONS:
                    continue
                try:
                    rel = entry.relative_to(self._base)
                    stat = entry.stat()
                    results.append({
                        "name": entry.name,
                        "relative_path": str(rel),
                        "size_bytes": stat.st_size,
                        "mime_type": _guess_mime(entry.name),
                        "modified_at": _mtime_iso(stat.st_mtime),
                    })
                except Exception as exc:
                    logger.debug("ArtifactIndex: skip %s: %s", entry, exc)
        except PermissionError as exc:
            logger.warning("ArtifactIndex: permission error scanning %s: %s", scan_root, exc)

        return results

    def stream_file(self, relative_path: str) -> Generator[bytes, None, None]:
        """
        Stream file content in chunks.
        Raises ValueError immediately (before returning generator) if path is
        outside artifacts_dir. Raises FileNotFoundError if file does not exist.

        Path validation is eager (not lazy) — the ValueError is raised on call,
        not during iteration, so route handlers can catch it before StreamingResponse.
        """
        # Validate path EAGERLY before returning generator.
        # _resolve_safe raises ValueError immediately if traversal detected.
        target = self._resolve_safe(relative_path)
        if not target.is_file():
            raise FileNotFoundError(f"Artifact not found: {relative_path!r}")
        # Return a separate generator to keep stream_file itself a normal function
        return self._read_chunks(target)

    def _read_chunks(self, target: Path) -> Generator[bytes, None, None]:
        """Yield file content in _CHUNK_SIZE chunks. Called after path validation."""
        with target.open("rb") as fh:
            while True:
                chunk = fh.read(_CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk

    def file_info(self, relative_path: str) -> Optional[Dict[str, Any]]:
        """Return metadata for one file, or None if not found / outside base."""
        try:
            target = self._resolve_safe(relative_path)
        except ValueError:
            return None
        if not target.is_file():
            return None
        try:
            stat = target.stat()
            return {
                "name": target.name,
                "relative_path": relative_path,
                "size_bytes": stat.st_size,
                "mime_type": _guess_mime(target.name),
                "modified_at": _mtime_iso(stat.st_mtime),
            }
        except Exception:
            return None

    def write_file(self, relative_path: str, content: bytes) -> str:
        """
        Write bytes to a path within artifacts_dir.
        Creates parent directories as needed.
        Raises ValueError if path escapes artifacts_dir.
        Returns the relative_path that was written.
        """
        target = self._resolve_safe(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return relative_path

    # ── path safety ───────────────────────────────────────────────────────────

    def _resolve_safe(self, relative_path: str) -> Path:
        """
        Resolve relative_path within self._base.
        Raises ValueError if the resolved path escapes the base directory.
        """
        # Normalize: strip leading slashes/dots that could escape
        clean = Path(relative_path)
        # Build candidate: base / path
        candidate = (self._base / clean).resolve()
        # Ensure candidate starts with base (handles symlinks via resolve)
        base_str = str(self._base)
        cand_str = str(candidate)
        if cand_str != base_str and not cand_str.startswith(base_str + os.sep):
            raise ValueError(
                f"Path traversal blocked: {relative_path!r} resolves outside artifacts directory."
            )
        return candidate


# ── helpers ───────────────────────────────────────────────────────────────────

def _guess_mime(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


def _mtime_iso(mtime: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
