"""Load the target app's files for the static audit agents.

The security, code-quality, dependency, database and release-readiness audits
inspect ``file_contents`` / ``dependency_files`` / ``file_list``. When nothing
supplies them they silently audit nothing, so the workflow loads them here.

Loading is bounded (file count, per-file and total bytes) and never follows
symlinks, so a link inside the target cannot pull in files from outside it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from qa_ai.agents.constants import EXCLUDED_DIRS, EXCLUDED_FILE_SUFFIXES, SOURCE_EXTENSIONS
from qa_ai.agents.file_walker import is_binary_file

logger = logging.getLogger(__name__)

MAX_LISTED_FILES = 20_000
MAX_CONTENT_FILES = 2_000
MAX_FILE_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024

# Read as source text for the code/security/database/release audits.
_CONTENT_EXTENSIONS = frozenset(SOURCE_EXTENSIONS) | {".sql"}
# The dependency audit recognises these manifests by name.
_DEPENDENCY_BASENAMES = frozenset({"package.json", "pubspec.yaml"})

# The discovery walker skips these as "not source", but the audits need to see them by name
# (manifests, docs, key material and database files are release/database/security signals).
_LISTED_DESPITE_SUFFIX = frozenset({
    ".txt", ".md", ".rst", ".key", ".pem", ".p12", ".pfx", ".cer", ".crt", ".db", ".sqlite", ".sqlite3",
})
_BINARY_SUFFIXES = frozenset(EXCLUDED_FILE_SUFFIXES) - _LISTED_DESPITE_SUFFIX
_GENERATED_MARKERS = (
    ".min.js", ".min.css", ".bundle.js", ".chunk.js", ".map", ".d.ts",
    ".g.dart", ".freezed.dart", ".gr.dart", ".pb.dart", ".pb.go", "_pb2.py", ".generated.",
)
_LOCK_FILES = frozenset({
    "package-lock.json", "yarn.lock", "pubspec.lock", "gemfile.lock",
    "poetry.lock", "cargo.lock", "composer.lock", "pnpm-lock.yaml",
})


@dataclass
class AuditInputs:
    """Files of one target, keyed by path relative to the target root (POSIX style)."""

    file_contents: Dict[str, str] = field(default_factory=dict)
    dependency_files: Dict[str, str] = field(default_factory=dict)
    file_list: List[str] = field(default_factory=list)


def _is_excluded(relative: Path) -> bool:
    """Skip vendored/build directories, generated files, lock files and binaries.

    Only *directory* parts are matched against EXCLUDED_DIRS, so a file named ``.env`` is still listed.
    """
    if any(part in EXCLUDED_DIRS or part.endswith(".egg-info") for part in relative.parts[:-1]):
        return True
    name = relative.name.lower()
    if name in _LOCK_FILES or any(marker in name for marker in _GENERATED_MARKERS):
        return True
    return relative.suffix.lower() in _BINARY_SUFFIXES


def _is_dependency_manifest(name: str) -> bool:
    lower = name.lower()
    return lower in _DEPENDENCY_BASENAMES or (lower.startswith("requirements") and lower.endswith(".txt"))


def load_audit_inputs(
    app_path: str | Path,
    *,
    max_content_files: int = MAX_CONTENT_FILES,
    max_file_bytes: int = MAX_FILE_BYTES,
    max_total_bytes: int = MAX_TOTAL_BYTES,
) -> AuditInputs:
    root = Path(app_path)
    inputs = AuditInputs()
    if not root.is_dir():
        return inputs

    total_bytes = 0
    for path in sorted(root.rglob("*")):
        if len(inputs.file_list) >= MAX_LISTED_FILES:
            logger.warning("Audit file list truncated at %d files under %s", MAX_LISTED_FILES, root)
            break
        try:
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(root)
        except (OSError, ValueError):
            continue
        if _is_excluded(relative):
            continue

        key = relative.as_posix()
        inputs.file_list.append(key)

        wants_content = path.suffix.lower() in _CONTENT_EXTENSIONS
        wants_dependencies = _is_dependency_manifest(path.name)
        if not (wants_content or wants_dependencies):
            continue
        if wants_content and not wants_dependencies and len(inputs.file_contents) >= max_content_files:
            continue
        try:
            size = path.stat().st_size
            if size > max_file_bytes or total_bytes + size > max_total_bytes or is_binary_file(path):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        total_bytes += size
        if wants_dependencies:
            inputs.dependency_files[key] = text
        if wants_content:
            inputs.file_contents[key] = text

    return inputs
