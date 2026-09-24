"""
log_watcher.py - Stream and store logs from app/backend processes.

Captures stdout/stderr, searches for expected tags, redacts secrets,
and stores matching lines as evidence.
"""
from __future__ import annotations

import logging
import re
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Patterns that look like secrets — redacted in stored logs
_SECRET_PATTERNS = [
    re.compile(r'(api[_-]?key\s*[=:]\s*)["\']?[\w\-]{8,}', re.I),
    re.compile(r'(secret\s*[=:]\s*)["\']?[\w\-]{8,}', re.I),
    re.compile(r'(password\s*[=:]\s*)["\']?\S+', re.I),
    re.compile(r'(bearer\s+)[\w\-\.]{20,}', re.I),
    re.compile(r'(token\s*[=:]\s*)["\']?[\w\-\.]{20,}', re.I),
]


def _redact(line: str) -> str:
    for pat in _SECRET_PATTERNS:
        line = pat.sub(r'\1[REDACTED]', line)
    return line


class LogWatcher:
    """
    Stream logs from one or more sources and match expected tags.

    Usage:
        watcher = LogWatcher(expected_tags=["[AI_CONFIG]", "[ERROR]"])
        watcher.ingest_line("[AI_CONFIG] model=gpt-4o", source="app")
        matched = watcher.get_matched_lines("[AI_CONFIG]")
    """

    def __init__(
        self,
        expected_tags: Optional[List[str]] = None,
        redact_secrets: bool = True,
    ):
        self._expected_tags = expected_tags or []
        self._redact = redact_secrets
        self._all_lines: List[Dict] = []          # {ts, source, line}
        self._matched: Dict[str, List[str]] = defaultdict(list)
        self._lock = threading.Lock()
        self._callbacks: List[Callable[[str, str], None]] = []

    # ── ingestion ─────────────────────────────────────────────────────────────

    def ingest_line(self, line: str, source: str = "app") -> None:
        """Ingest a single log line from a named source."""
        if self._redact:
            line = _redact(line)

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "line": line,
        }

        with self._lock:
            self._all_lines.append(entry)
            for tag in self._expected_tags:
                if tag in line:
                    self._matched[tag].append(line)

        for cb in self._callbacks:
            try:
                cb(source, line)
            except Exception as exc:
                logger.debug("Log callback error: %s", exc)

    def ingest_lines(self, lines: List[str], source: str = "app") -> None:
        for line in lines:
            self.ingest_line(line, source)

    def watch_process_stdout(self, process, source: str = "app") -> threading.Thread:
        """Start a daemon thread that ingests lines from process.stdout."""
        def _reader():
            try:
                for line in iter(process.stdout.readline, ""):
                    if line:
                        self.ingest_line(line.rstrip(), source)
            except Exception as exc:
                logger.debug("Log reader thread ended: %s", exc)

        t = threading.Thread(target=_reader, daemon=True, name=f"log-watcher-{source}")
        t.start()
        return t

    # ── queries ───────────────────────────────────────────────────────────────

    def get_matched_lines(self, tag: str) -> List[str]:
        with self._lock:
            return list(self._matched.get(tag, []))

    def tag_found(self, tag: str) -> bool:
        with self._lock:
            return len(self._matched.get(tag, [])) > 0

    def all_lines(self, source: Optional[str] = None) -> List[str]:
        with self._lock:
            if source:
                return [e["line"] for e in self._all_lines if e["source"] == source]
            return [e["line"] for e in self._all_lines]

    def search(self, pattern: str, case_sensitive: bool = False) -> List[str]:
        flags = 0 if case_sensitive else re.I
        compiled = re.compile(pattern, flags)
        with self._lock:
            return [e["line"] for e in self._all_lines if compiled.search(e["line"])]

    def tag_summary(self) -> Dict[str, int]:
        with self._lock:
            return {tag: len(lines) for tag, lines in self._matched.items()}

    def has_error(self) -> bool:
        return any(
            "[ERROR]" in e["line"] or "error" in e["line"].lower()
            for e in self._all_lines
        )

    def snapshot(self, max_lines: int = 500) -> List[Dict]:
        with self._lock:
            return list(self._all_lines[-max_lines:])

    def add_callback(self, cb: Callable[[str, str], None]) -> None:
        """Register a callback(source, line) called on each ingested line."""
        self._callbacks.append(cb)

    def clear(self) -> None:
        with self._lock:
            self._all_lines.clear()
            self._matched.clear()
