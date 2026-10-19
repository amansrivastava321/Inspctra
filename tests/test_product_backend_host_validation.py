"""The product API only answers to loopback Host headers (DNS-rebinding defence)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qa_ai.product_backend.server import create_product_app


def _client(tmp_path: Path, base_url: str) -> TestClient:
    app = create_product_app(artifacts_dir=str(tmp_path / "artifacts"), db_path=str(tmp_path / "host.db"))
    return TestClient(app, base_url=base_url)


@pytest.mark.parametrize("base_url", [
    "http://localhost:8765", "http://127.0.0.1:8765", "http://127.0.0.1:5173", "http://localhost",
])
def test_loopback_hosts_are_served(tmp_path: Path, base_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INSPECTRA_ALLOWED_HOSTS", raising=False)
    with _client(tmp_path, base_url) as client:
        assert client.get("/api/health").status_code == 200


@pytest.mark.parametrize("base_url", [
    "http://evil.example.com", "http://evil.example.com:8765", "http://127.0.0.1.evil.example.com",
    "http://localhost.evil.example.com",
])
def test_other_hosts_are_rejected_on_every_route(tmp_path: Path, base_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INSPECTRA_ALLOWED_HOSTS", raising=False)
    with _client(tmp_path, base_url) as client:
        assert client.get("/api/health").status_code == 400
        assert client.get("/api/projects").status_code == 400
        assert client.post("/api/local-folder-search", json={"folder_name": "x", "confirm_search": True}).status_code == 400


def test_additional_hosts_can_be_allowed_explicitly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INSPECTRA_ALLOWED_HOSTS", "qa.internal, other.internal")
    with _client(tmp_path, "http://qa.internal:8765") as client:
        assert client.get("/api/health").status_code == 200
    with _client(tmp_path, "http://evil.example.com") as client:
        assert client.get("/api/health").status_code == 400
