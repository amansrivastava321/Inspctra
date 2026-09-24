from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations.corpus_runtime import CorpusRuntime, CorpusRuntimeStatus
from integrations.corpus_status import CorpusConnectionState


@dataclass
class _Req:
    request_id: str = "req-1"
    app_id: str = "inspectra"
    workspace_id: str = "ws-1"
    workspace_name: str = "AI Engineering Workspace"
    status: str = "PENDING"


class _FakeTransport:
    def __init__(self, token_valid: bool = True, disconnected: bool = True):
        self.token_valid = token_valid
        self.disconnected = disconnected

    def post(self, path: str, json: dict | None = None):
        if path == "/connections/tokens/validate":
            if not self.token_valid:
                raise RuntimeError("token revoked")
            return {"valid": True}
        if path.endswith("/disconnect"):
            return {"disconnected": self.disconnected}
        raise RuntimeError(f"unexpected path: {path}")


class _FakeCorpusClient:
    def __init__(self, *_, **__):
        self._transport = _FakeTransport()
        self._status_payload = {"connected": False, "requests": []}

    def request_connection(self, **_kwargs):
        return _Req()

    def get_connection_status(self, workspace_id=None):
        return self._status_payload


class _FakeSignalClient:
    def __init__(self, *_, **__):
        pass

    def interrupt(self, **kwargs):
        return {"signal": "INTERRUPT", **kwargs}

    def get_pending_signals(self):
        return []

    def checkpoints(self):
        return {"ok": True}

    def heartbeat(self):
        return {"status": "ok"}


def _mk_manager(monkeypatch, tmp_path):
    import integrations.corpus_connection as cc

    monkeypatch.setattr(cc, "CorpusClient", _FakeCorpusClient)

    return cc.CorpusConnectionManager(
        app_name="inspectra",
        app_version="1.0.0",
        workspace_name="AI Engineering Workspace",
        capabilities=["EMIT_SIGNALS", "RECEIVE_SIGNALS", "RESPOND_CHECKPOINT"],
        permissions=["EMIT_SIGNALS", "RECEIVE_SIGNALS", "RESPOND_CHECKPOINT"],
        session_path=tmp_path / "corpus_session.json",
    )


def test_runtime_detection_detected(monkeypatch):
    runtime = CorpusRuntime()

    class _Discovery:
        def find_or_start_runtime(self, **_kwargs):
            class _Found:
                base_url = "http://127.0.0.1:8000"
                source = "scan"

            return _Found()

    monkeypatch.setattr(runtime, "_discovery", _Discovery())
    monkeypatch.setattr(CorpusRuntime, "validate_runtime_health", staticmethod(lambda _url: True))

    status = runtime.detect_local_runtime(allow_launch=False)

    assert isinstance(status, CorpusRuntimeStatus)
    assert status.detected is True
    assert status.healthy is True


def test_request_connection_sets_pending(monkeypatch, tmp_path):
    manager = _mk_manager(monkeypatch, tmp_path)

    payload = manager.request_connection()

    assert payload["request_id"] == "req-1"
    assert manager.get_status().state == CorpusConnectionState.PENDING_APPROVAL


def test_status_approved(monkeypatch, tmp_path):
    manager = _mk_manager(monkeypatch, tmp_path)
    manager.client._status_payload = {
        "connected": True,
        "apps": [
            {
                "workspace_id": "ws-1",
                "trust_level": "STANDARD",
                "granted_permissions": ["EMIT_SIGNALS", "RECEIVE_SIGNALS", "RESPOND_CHECKPOINT"],
            }
        ],
    }

    status = manager.get_status()

    assert status.connected is True
    assert status.permissions_granted == ["EMIT_SIGNALS", "RECEIVE_SIGNALS", "RESPOND_CHECKPOINT"]


def test_status_denied(monkeypatch, tmp_path):
    manager = _mk_manager(monkeypatch, tmp_path)
    manager.client._status_payload = {
        "connected": False,
        "requests": [
            {
                "request_id": "req-1",
                "status": "DENIED",
                "reason": "Denied by workspace authority",
            }
        ],
    }

    status = manager.get_status()

    assert status.denied is True
    assert "Denied" in (status.reason or "")


def test_reconnect_with_token_valid(monkeypatch, tmp_path):
    manager = _mk_manager(monkeypatch, tmp_path)
    manager.store_approved_token("tok", "2099-01-01T00:00:00Z", ["EMIT_SIGNALS"], "ws-1")
    manager.client._transport = _FakeTransport(token_valid=True)

    assert manager.reconnect_with_saved_token() is True


def test_reconnect_with_token_revoked(monkeypatch, tmp_path):
    manager = _mk_manager(monkeypatch, tmp_path)
    manager.store_approved_token("tok", "2099-01-01T00:00:00Z", ["EMIT_SIGNALS"], "ws-1")
    manager.client._transport = _FakeTransport(token_valid=False)

    assert manager.reconnect_with_saved_token() is False
    assert manager.get_status().disconnected is True


def test_signal_blocked_before_approval(monkeypatch, tmp_path):
    manager = _mk_manager(monkeypatch, tmp_path)

    import integrations.corpus_client as cc

    monkeypatch.setattr(cc, "CorpusClient", _FakeSignalClient)
    wrapper = cc.InspectraCorpusClient(manager)

    with pytest.raises(RuntimeError):
        wrapper.send_interrupt("anvil", "risk")


def test_signal_send_after_approval(monkeypatch, tmp_path):
    manager = _mk_manager(monkeypatch, tmp_path)
    manager.client._status_payload = {
        "connected": True,
        "apps": [{"workspace_id": "ws-1", "trust_level": "STANDARD", "granted_permissions": ["EMIT_SIGNALS"]}],
    }

    import integrations.corpus_client as cc

    monkeypatch.setattr(cc, "CorpusClient", _FakeSignalClient)
    wrapper = cc.InspectraCorpusClient(manager)

    signal = wrapper.send_interrupt("anvil", "Critical validation bug", evidence={"file": "auth.py"})

    assert signal["signal"] == "INTERRUPT"


def test_graceful_unavailable_runtime(monkeypatch, tmp_path):
    manager = _mk_manager(monkeypatch, tmp_path)

    def _fail(*_, **__):
        raise RuntimeError("down")

    monkeypatch.setattr(manager.client, "get_connection_status", _fail)

    status = manager.get_status()

    assert status.disconnected is True
    assert "unavailable" in (status.reason or "")
