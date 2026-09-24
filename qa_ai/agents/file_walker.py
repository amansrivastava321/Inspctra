"""
file_walker.py - Production-grade source file iterator.
Filters, limits, and tracks scanned files for the Discovery Agent.
"""

from pathlib import Path
from typing import Iterator, Optional
import logging
import time

from qa_ai.agents.constants import (
    EXCLUDED_DIRS,
    EXCLUDED_FILE_SUFFIXES,
    SOURCE_EXTENSIONS,
)

logger = logging.getLogger(__name__)

# Additional exclusions not in constants
_EXCLUDED_FILE_PATTERNS = [
    ".min.js", ".min.css", ".bundle.js", ".chunk.js",
    ".bundle.css", ".chunk.css",
    ".map",           # Source maps
    ".d.ts",          # TypeScript declaration files (generated)
    ".g.dart",        # Generated Dart files (json_serializable, etc.)
    ".freezed.dart",  # Freezed generated code
    ".gr.dart",       # gRPC generated Dart
    ".pb.dart",       # Protobuf generated Dart
    ".pb.go",         # Protobuf generated Go
    "_pb2.py",        # Protobuf generated Python
    ".generated.",    # Any generated file marker
]

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_FILES_TO_SCAN = 50000
BINARY_CHECK_BYTES = 512


def is_binary_file(file_path: Path) -> bool:
    """Check if a file is binary by reading the first few bytes."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(BINARY_CHECK_BYTES)
        return b"\x00" in chunk
    except Exception as e:
        logger.debug("Binary check failed for %s: %s", file_path, e)
        return False


def should_skip_path(path: Path) -> bool:
    """
    Check if a path should be excluded from scanning.
    
    Returns True if the path matches any exclusion rule.
    """
    # Check directory exclusions
    parts = set(path.parts)
    if parts.intersection(EXCLUDED_DIRS):
        return True

    # Check file name exclusions
    name_lower = path.name.lower()

    # Exact suffix matches
    for suffix in EXCLUDED_FILE_SUFFIXES:
        if name_lower.endswith(suffix):
            return True

    # Pattern matches (for .min.js, .bundle.js, etc.)
    for pattern in _EXCLUDED_FILE_PATTERNS:
        if pattern in name_lower:
            return True

    # Exclude lock files specifically (not files with 'lock' in name)
    if name_lower in ["package-lock.json", "yarn.lock", "pubspec.lock",
                       "gemfile.lock", "poetry.lock", "cargo.lock",
                       "composer.lock", "pnpm-lock.yaml"]:
        return True

    # Exclude files that start with dot (hidden) unless they're important configs
    if name_lower.startswith(".") and name_lower not in [
        ".env", ".env.local", ".env.development", ".env.production",
        ".eslintrc", ".prettierrc", ".babelrc", ".dockerignore",
    ]:
        return True

    return False


def iter_source_files(
    app_path: Path,
    max_files: int = MAX_FILES_TO_SCAN,
    max_file_size: int = MAX_FILE_SIZE_BYTES,
    show_progress: bool = True,
) -> Iterator[Path]:
    """
    Iterate over source files in the app directory.
    
    Args:
        app_path: Root directory of the application
        max_files: Maximum number of files to yield (prevents hanging on huge repos)
        max_file_size: Maximum file size in bytes (skip massive files)
        show_progress: Log progress every 1000 files
    
    Yields:
        Path objects for source files that pass all filters
    """
    start_time = time.time()
    files_scanned = 0
    files_skipped = 0
    files_yielded = 0
    files_too_large = 0
    files_binary = 0

    logger.info(f"Scanning: {app_path}")

    for path in app_path.rglob("*"):
        files_scanned += 1

        # Progress logging
        if show_progress and files_scanned % 1000 == 0:
            elapsed = time.time() - start_time
            logger.debug(
                f"  Scanned {files_scanned} files, "
                f"yielded {files_yielded}, "
                f"skipped {files_skipped} "
                f"({elapsed:.1f}s)"
            )

        # Hard limit
        if files_yielded >= max_files:
            logger.warning(
                f"Reached max file limit ({max_files}). "
                f"Stopping scan. {files_scanned} files examined."
            )
            break

        # Must be a file
        if not path.is_file():
            continue

        # Must have source extension
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue

        # Check exclusions
        if should_skip_path(path):
            files_skipped += 1
            continue

        # Check file size
        try:
            size = path.stat().st_size
            if size > max_file_size:
                files_too_large += 1
                logger.debug(f"Skipping large file ({size} bytes): {path}")
                continue
        except OSError:
            files_skipped += 1
            continue

        # Check binary
        if is_binary_file(path):
            files_binary += 1
            continue

        files_yielded += 1
        yield path

    # Final summary
    elapsed = time.time() - start_time
    logger.info(
        f"File scan complete: "
        f"{files_scanned} examined, "
        f"{files_yielded} yielded, "
        f"{files_skipped} skipped, "
        f"{files_too_large} too large, "
        f"{files_binary} binary "
        f"({elapsed:.1f}s)"
    )


def count_source_files(app_path: Path) -> int:
    """Quick count of scannable source files without yielding them."""
    return sum(1 for _ in iter_source_files(app_path, show_progress=False))