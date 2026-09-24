import json
from fastapi.testclient import TestClient

from qa_ai.webapp.server import create_app


class _Status:
    def to_dict(self):
        return {"state": "disconnected"}


class _CorpusManager:
    def get_status(self):
        return _Status()

    def request_connection(self):
        return {"state": "pending_approval"}


def test_corpus_settings_page_and_status_route(tmp_path, monkeypatch):
    import qa_ai.webapp.routes as routes

    monkeypatch.setattr(routes, "_get_corpus_manager", lambda: _CorpusManager())
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    (artifacts_dir / "audit_summary.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")

    app = create_app(str(artifacts_dir))
    client = TestClient(app)

    page = client.get("/settings/integrations/corpus")
    assert page.status_code == 200
    assert "Connect to Corpus" in page.text or "Pending Approval" in page.text or "Connected" in page.text

    status = client.get("/api/integrations/corpus/status")
    assert status.status_code == 200
    assert "state" in status.json()

    request_conn = client.post("/api/integrations/corpus/request-connection")
    assert request_conn.status_code == 200
    assert "state" in request_conn.json()

    poll = client.post("/api/integrations/corpus/check-approval")
    assert poll.status_code == 200
    assert "state" in poll.json()
