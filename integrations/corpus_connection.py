"""Permission-based Corpus connection manager with local session persistence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:
    from corpus_sdk import CorpusClient, CorpusConnectionError
except ImportError:  # pragma: no cover - fallback for environments without corpus_sdk
    CorpusClient = None  # type: ignore[assignment]

    class CorpusConnectionError(Exception):
        pass

from integrations.corpus_runtime import CorpusRuntime
from integrations.corpus_status import CorpusConnectionState, CorpusStatus

DEFAULT_SESSION_PATH = Path(__file__).with_name("corpus_session.json")


@dataclass
class CorpusSession:
    app_name: str
    app_id: str
    workspace_name: str
    workspace_id: str | None = None
    request_id: str | None = None
    token: str | None = None
    token_expires_at: str | None = None
    token_scopes: list[str] = field(default_factory=list)
    trust_level: str | None = None
    permissions_granted: list[str] = field(default_factory=list)
    state: str = CorpusConnectionState.DISCONNECTED.value
    reason: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_dict(cls, payload: dict) -> "CorpusSession":
        return cls(
            app_name=payload["app_name"],
            app_id=payload["app_id"],
            workspace_name=payload["workspace_name"],
            workspace_id=payload.get("workspace_id"),
            request_id=payload.get("request_id"),
            token=payload.get("token"),
            token_expires_at=payload.get("token_expires_at"),
            token_scopes=list(payload.get("token_scopes") or []),
            trust_level=payload.get("trust_level"),
            permissions_granted=list(payload.get("permissions_granted") or []),
            state=payload.get("state", CorpusConnectionState.DISCONNECTED.value),
            reason=payload.get("reason"),
            updated_at=payload.get("updated_at"),
        )

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        return payload


class CorpusConnectionManager:
    def __init__(
        self,
        app_name: str,
        app_version: str,
        workspace_name: str,
        capabilities: list[str],
        permissions: list[str],
        session_path: Path = DEFAULT_SESSION_PATH,
        base_url: str = "http://localhost:8000",
    ) -> None:
        self.app_name = app_name
        self.workspace_name = workspace_name
        self.capabilities = capabilities
        self.permissions = permissions
        self.session_path = session_path
        self.runtime = CorpusRuntime()

        if CorpusClient is None:
            raise RuntimeError(
                "corpus_sdk is required for Corpus integration. Install corpus_sdk to enable connection flow."
            )

        self.client = CorpusClient(
            app_name=app_name,
            product_version=app_version,
            capabilities=capabilities,
            base_url=base_url,
        )
        self._session = self._load_session() or CorpusSession(
            app_name=app_name,
            app_id=self._derive_app_id(app_name),
            workspace_name=workspace_name,
        )

    def detect_runtime(self, allow_launch: bool = False) -> dict:
        return self.runtime.detect_local_runtime(allow_launch=allow_launch).to_dict()

    def request_connection(self) -> dict:
        request = self.client.request_connection(
            workspace=self.workspace_name,
            capabilities=self.capabilities,
            permissions=self.permissions,
            trust_level_requested="STANDARD",
            auto_start_runtime=False,
        )
        self._session.app_id = request.app_id
        self._session.workspace_id = request.workspace_id
        self._session.request_id = request.request_id
        self._session.state = CorpusConnectionState.PENDING_APPROVAL.value
        self._session.reason = None
        self._save_session()
        return {
            "request_id": request.request_id,
            "app_id": request.app_id,
            "workspace_id": request.workspace_id,
            "workspace_name": request.workspace_name,
            "status": request.status,
        }

    def get_status(self) -> CorpusStatus:
        try:
            data = self.client.get_connection_status(workspace_id=self._session.workspace_id)
        except (CorpusConnectionError, Exception):
            return CorpusStatus(
                state=CorpusConnectionState.DISCONNECTED,
                workspace_name=self.workspace_name,
                reason="Corpus runtime unavailable",
            )

        if data.get("connected"):
            apps = list(data.get("apps") or [])
            app = apps[0] if apps else {}
            granted = list(app.get("granted_permissions") or [])
            self._session.state = CorpusConnectionState.CONNECTED.value
            self._session.permissions_granted = granted
            self._session.trust_level = app.get("trust_level")
            self._session.workspace_id = app.get("workspace_id", self._session.workspace_id)
            self._session.reason = None
            self._save_session()
            return CorpusStatus(
                state=CorpusConnectionState.CONNECTED,
                workspace_name=self.workspace_name,
                trust_level=self._session.trust_level,
                permissions_granted=granted,
            )

        requests = list(data.get("requests") or [])
        if requests:
            latest = requests[0]
            req_status = str(latest.get("status", "")).upper()
            self._session.request_id = latest.get("request_id", self._session.request_id)
            self._session.workspace_id = latest.get("workspace_id", self._session.workspace_id)
            if req_status == "PENDING":
                self._session.state = CorpusConnectionState.PENDING_APPROVAL.value
                self._session.reason = None
                self._save_session()
                return CorpusStatus(
                    state=CorpusConnectionState.PENDING_APPROVAL,
                    workspace_name=self.workspace_name,
                )
            if req_status == "DENIED":
                reason = latest.get("reason") or "Denied by workspace authority"
                self._session.state = CorpusConnectionState.DENIED.value
                self._session.reason = reason
                self._save_session()
                return CorpusStatus(
                    state=CorpusConnectionState.DENIED,
                    workspace_name=self.workspace_name,
                    reason=reason,
                )

        if self._session.state == CorpusConnectionState.PENDING_APPROVAL.value:
            return CorpusStatus(
                state=CorpusConnectionState.PENDING_APPROVAL,
                workspace_name=self.workspace_name,
            )

        self._session.state = CorpusConnectionState.DISCONNECTED.value
        self._save_session()
        return CorpusStatus(
            state=CorpusConnectionState.DISCONNECTED,
            workspace_name=self.workspace_name,
        )

    def reconnect_with_saved_token(self) -> bool:
        token = self._session.token
        workspace_id = self._session.workspace_id
        if not token or not workspace_id:
            return False

        try:
            self.client._transport.post(  # noqa: SLF001
                "/connections/tokens/validate",
                json={
                    "token": token,
                    "workspace_id": workspace_id,
                    "required_scopes": self.permissions,
                },
            )
        except Exception:
            self._session.token = None
            self._session.token_expires_at = None
            self._session.token_scopes = []
            self._session.state = CorpusConnectionState.DISCONNECTED.value
            self._session.reason = "Saved token is invalid or revoked"
            self._save_session()
            return False

        self._session.state = CorpusConnectionState.CONNECTED.value
        self._save_session()
        return True

    def store_approved_token(
        self,
        token_value: str,
        expires_at: str | None,
        scopes: list[str],
        workspace_id: str,
    ) -> None:
        self._session.token = token_value
        self._session.token_expires_at = expires_at
        self._session.token_scopes = scopes
        self._session.workspace_id = workspace_id
        self._session.state = CorpusConnectionState.CONNECTED.value
        self._save_session()

    def disconnect(self) -> bool:
        workspace_id = self._session.workspace_id
        if not workspace_id:
            self._session.state = CorpusConnectionState.DISCONNECTED.value
            self._save_session()
            return False

        try:
            response = self.client._transport.post(  # noqa: SLF001
                f"/connections/{self._session.app_id}/disconnect",
                json={"workspace_id": workspace_id},
            )
        except Exception:
            return False

        disconnected = bool(response.get("disconnected")) if isinstance(response, dict) else False
        self._session.state = CorpusConnectionState.DISCONNECTED.value
        self._session.reason = None
        self._session.token = None
        self._session.token_expires_at = None
        self._session.token_scopes = []
        self._session.permissions_granted = []
        self._save_session()
        return disconnected

    def _load_session(self) -> CorpusSession | None:
        if not self.session_path.exists():
            return None
        try:
            return CorpusSession.from_dict(json.loads(self.session_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError, KeyError):
            return None

    def _save_session(self) -> None:
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_path.write_text(json.dumps(self._session.to_dict(), indent=2), encoding="utf-8")

    @staticmethod
    def _derive_app_id(name: str) -> str:
        return "-".join(name.strip().lower().split())
