"""
test_webapp_server.py - Integration tests for the FastAPI dashboard server.

Uses the TestClient (no real HTTP) so the dashboard server doesn't need to be
running. All routes are exercised against an in-memory artifact store.
"""
import json
import pytest
from pathlib import Path

from fastapi.testclient import TestClient

from qa_ai.webapp.server import create_app


@pytest.fixture
def client(tmp_path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    (artifacts_dir / "audit_summary.json").write_text(
        json.dumps({
            "status": "completed",
            "target_path": "/app",
            "profile": "api",
            "phases_executed": ["discovery", "analysis"],
        })
    )
    (artifacts_dir / "findings.json").write_text(
        json.dumps({
            "findings": [
                {"id": "F001", "title": "XSS", "severity": "high", "category": "security"},
            ]
        })
    )
    (artifacts_dir / "risk_report.json").write_text(
        json.dumps({"overall_score": 6.0, "risk_level": "medium"})
    )

    app = create_app(str(artifacts_dir))
    return TestClient(app)


class TestHealthRoute:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_includes_artifact_count(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "artifact_count" in data


class TestDashboardRoute:
    def test_root_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "<html" in resp.text.lower()

    def test_dashboard_contains_inspectra_brand(self, client):
        resp = client.get("/")
        assert "Inspectra" in resp.text


class TestFindingsRoute:
    def test_findings_returns_list(self, client):
        resp = client.get("/api/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data[0]["id"] == "F001"

    def test_findings_empty_when_no_data(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        app = create_app(str(empty_dir))
        tc = TestClient(app)
        resp = tc.get("/api/findings")
        assert resp.status_code == 200
        assert resp.json() == []


class TestSummaryRoute:
    def test_summary_returns_dict(self, client):
        resp = client.get("/api/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"


class TestRiskRoute:
    def test_risk_returns_dict(self, client):
        resp = client.get("/api/risk")
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_level"] == "medium"

    def test_risk_empty_when_no_data(self, tmp_path):
        empty_dir = tmp_path / "empty2"
        empty_dir.mkdir()
        app = create_app(str(empty_dir))
        tc = TestClient(app)
        resp = tc.get("/api/risk")
        assert resp.status_code == 200
        assert resp.json() == {}


class TestArtifactsRoute:
    def test_list_artifacts_returns_list(self, client):
        resp = client.get("/api/artifacts")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_artifact_by_name(self, client):
        resp = client.get("/api/artifacts/risk_report.json")
        assert resp.status_code == 200
        assert resp.json()["risk_level"] == "medium"

    def test_get_missing_artifact_returns_404(self, client):
        resp = client.get("/api/artifacts/does_not_exist.json")
        assert resp.status_code == 404


class TestOptionalRoutes:
    def test_remediation_route_exists(self, client):
        resp = client.get("/api/remediation")
        assert resp.status_code == 200

    def test_benchmarks_route_exists(self, client):
        resp = client.get("/api/benchmarks")
        assert resp.status_code == 200

    def test_cicd_route_exists(self, client):
        resp = client.get("/api/cicd")
        assert resp.status_code == 200

    def test_self_optimization_route_exists(self, client):
        resp = client.get("/api/self-optimization")
        assert resp.status_code == 200


class _FakeCorpusManager:
    def detect_runtime(self, allow_launch=False):
        return {"detected": True, "healthy": True, "base_url": "http://127.0.0.1:8000", "source": "scan"}

    def get_status(self):
        class _Status:
            def to_dict(self):
                return {
                    "state": "pending_approval",
                    "connected": False,
                    "pending_approval": True,
                    "denied": False,
                    "disconnected": False,
                    "workspace_name": "AI Engineering Workspace",
                    "trust_level": None,
                    "permissions_granted": [],
                    "reason": None,
                }

        return _Status()

    def request_connection(self):
        return {
            "request_id": "req-123",
            "app_id": "inspectra",
            "workspace_id": "ws-1",
            "workspace_name": "AI Engineering Workspace",
            "status": "PENDING",
        }

    def reconnect_with_saved_token(self):
        return True

    def disconnect(self):
        return True


class TestCorpusRoutes:
    def test_corpus_runtime_status(self, client, monkeypatch):
        import qa_ai.webapp.routes as routes

        monkeypatch.setattr(routes, "_get_corpus_manager", lambda: _FakeCorpusManager())
        resp = client.get("/api/corpus/runtime")

        assert resp.status_code == 200
        assert resp.json()["detected"] is True

    def test_corpus_status_pending(self, client, monkeypatch):
        import qa_ai.webapp.routes as routes

        monkeypatch.setattr(routes, "_get_corpus_manager", lambda: _FakeCorpusManager())
        resp = client.get("/api/corpus/status")

        assert resp.status_code == 200
        assert resp.json()["state"] == "pending_approval"

    def test_corpus_request_connection(self, client, monkeypatch):
        import qa_ai.webapp.routes as routes

        monkeypatch.setattr(routes, "_get_corpus_manager", lambda: _FakeCorpusManager())
        resp = client.post("/api/corpus/request")

        assert resp.status_code == 200
        assert resp.json()["status"] == "PENDING"

    def test_corpus_disconnect(self, client, monkeypatch):
        import qa_ai.webapp.routes as routes

        monkeypatch.setattr(routes, "_get_corpus_manager", lambda: _FakeCorpusManager())
        resp = client.post("/api/corpus/disconnect")

        assert resp.status_code == 200
        assert resp.json()["disconnected"] is True
