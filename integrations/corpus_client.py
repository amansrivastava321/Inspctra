"""Authenticated/gated Corpus client wrapper for Inspectra."""

from __future__ import annotations

try:
    from corpus_sdk import CorpusClient
except ImportError:  # pragma: no cover - fallback for environments without corpus_sdk
    CorpusClient = None  # type: ignore[assignment]

from integrations.corpus_connection import CorpusConnectionManager


class InspectraCorpusClient:
    """Wrapper that blocks signal/checkpoint operations until approved."""

    def __init__(self, manager: CorpusConnectionManager) -> None:
        self.manager = manager
        if CorpusClient is None:
            raise RuntimeError("corpus_sdk is required for Corpus integration")
        self._client = CorpusClient(app_name="inspectra", product_version="1.0.0")

    def _require_connected(self) -> None:
        if not self.manager.get_status().connected:
            raise RuntimeError("Corpus connection is not approved")

    def send_interrupt(self, target: str, reason: str, severity: str = "CRITICAL", evidence: dict | None = None):
        self._require_connected()
        return self._client.interrupt(target=target, reason=reason, severity=severity, evidence=evidence or {})

    def receive_signals(self):
        self._require_connected()
        return self._client.get_pending_signals()

    def checkpoints(self):
        self._require_connected()
        return self._client.checkpoints()

    def heartbeat(self):
        self._require_connected()
        return self._client.heartbeat()
