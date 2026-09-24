"""
json_io.py - Atomic JSON I/O utilities for the QA platform.
Provides safe read/write with versioning support.
"""

from pathlib import Path
from typing import Any, Optional
import json
import logging
import tempfile
import shutil

logger = logging.getLogger(__name__)


def read_json(path: Path) -> Any:
    """Read and parse a JSON file. Returns None on failure."""
    path = Path(path)
    if not path.exists():
        logger.warning(f"JSON file not found: {path}")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to read {path}: {e}")
        return None


def write_json(path: Path, data: Any, indent: int = 2) -> bool:
    """Atomically write data as JSON. Uses temp file + rename for safety."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent),
            suffix=".tmp",
            prefix=f".{path.stem}_",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent, default=str, ensure_ascii=False)
            shutil.move(tmp_path, str(path))
        except Exception as e:
            logger.debug("Write failed, cleaning up temp file %s: %s", tmp_path, e)
            if Path(tmp_path).exists():
                Path(tmp_path).unlink()
            raise
        logger.debug(f"JSON written: {path}")
        return True
    except Exception as e:
        logger.error(f"Failed to write {path}: {e}")
        return False


import os  # noqa: E402  (needed for fdopen)


def update_json(path: Path, updates: dict) -> bool:
    """Load JSON, merge updates, write back atomically."""
    existing = read_json(path) or {}
    if isinstance(existing, dict):
        existing.update(updates)
        return write_json(path, existing)
    return False
