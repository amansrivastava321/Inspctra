"""Corpus runtime detection and health helpers."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

try:
    from corpus_sdk.runtime_discovery import RuntimeDiscovery
except ImportError:  # pragma: no cover - fallback for environments without corpus_sdk
    RuntimeDiscovery = None  # type: ignore[assignment]


@dataclass(frozen=True)
class CorpusRuntimeStatus:
    detected: bool
    healthy: bool
    base_url: str | None = None
    source: str | None = None

    def to_dict(self) -> dict:
        return {
            "detected": self.detected,
            "healthy": self.healthy,
            "base_url": self.base_url,
            "source": self.source,
        }


class CorpusRuntime:
    def __init__(self, candidate_ports: list[int] | None = None) -> None:
        self._discovery = RuntimeDiscovery() if RuntimeDiscovery is not None else None
        self._candidate_ports = candidate_ports or [8000, 8765, 9000, 10000]

    def detect_local_runtime(self, allow_launch: bool = False) -> CorpusRuntimeStatus:
        if self._discovery is None:
            return CorpusRuntimeStatus(detected=False, healthy=False)

        found = self._discovery.find_or_start_runtime(
            start_if_missing=allow_launch,
            candidate_ports=self._candidate_ports,
        )
        if not found:
            return CorpusRuntimeStatus(detected=False, healthy=False)
        healthy = self.validate_runtime_health(found.base_url)
        return CorpusRuntimeStatus(
            detected=True,
            healthy=healthy,
            base_url=found.base_url,
            source=found.source,
        )

    @staticmethod
    def validate_runtime_health(base_url: str) -> bool:
        try:
            response = httpx.get(f"{base_url.rstrip('/')}/health", timeout=0.7)
            if response.status_code != 200:
                return False
            payload = response.json()
            return payload.get("status") == "ok"
        except Exception:
            return False
