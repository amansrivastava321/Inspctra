"""Connection status models for Corpus integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CorpusConnectionState(str, Enum):
    CONNECTED = "connected"
    PENDING_APPROVAL = "pending_approval"
    DENIED = "denied"
    DISCONNECTED = "disconnected"


@dataclass(frozen=True)
class CorpusStatus:
    state: CorpusConnectionState
    workspace_name: str | None = None
    trust_level: str | None = None
    permissions_granted: list[str] = field(default_factory=list)
    reason: str | None = None

    @property
    def connected(self) -> bool:
        return self.state == CorpusConnectionState.CONNECTED

    @property
    def pending_approval(self) -> bool:
        return self.state == CorpusConnectionState.PENDING_APPROVAL

    @property
    def denied(self) -> bool:
        return self.state == CorpusConnectionState.DENIED

    @property
    def disconnected(self) -> bool:
        return self.state == CorpusConnectionState.DISCONNECTED

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "connected": self.connected,
            "pending_approval": self.pending_approval,
            "denied": self.denied,
            "disconnected": self.disconnected,
            "workspace_name": self.workspace_name,
            "trust_level": self.trust_level,
            "permissions_granted": list(self.permissions_granted),
            "reason": self.reason,
        }
