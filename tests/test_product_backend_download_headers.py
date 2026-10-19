"""Download names come from users/uploads and must never break or escape the header."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qa_ai.product_backend.http_headers import attachment_disposition
from qa_ai.product_backend.server import create_product_app


@pytest.mark.parametrize(("name", "expected"), [
    ("report.pdf", 'attachment; filename="report.pdf"'),
    ('evil"name.png', 'attachment; filename="evil_name.png"'),
    ("a\r\nX-Injected: yes", 'attachment; filename="a__X-Injected: yes"'),
    ("../../etc/passwd", 'attachment; filename="passwd"'),
    ("C:\\Users\\me\\shot.png", 'attachment; filename="shot.png"'),
    ("", 'attachment; filename="download"'),
    ("..", 'attachment; filename="download"'),
    (None, 'attachment; filename="download"'),
])
def test_filename_is_reduced_to_a_safe_basename(name: str | None, expected: str) -> None:
    assert attachment_disposition(name) == expected


def test_non_ascii_names_get_an_rfc5987_filename() -> None:
    value = attachment_disposition("résumé 报告.pdf")

    assert value.startswith('attachment; filename="r_sum_ __.pdf"')
    assert "filename*=UTF-8''r%C3%A9sum%C3%A9%20%E6%8A%A5%E5%91%8A.pdf" in value


def test_custom_fallback_is_used_for_empty_names() -> None:
    assert attachment_disposition("  ", "evidence") == 'attachment; filename="evidence"'


def test_evidence_download_with_hostile_name_is_served_with_a_valid_header(tmp_path: Path) -> None:
    app = create_product_app(artifacts_dir=str(tmp_path / "artifacts"), db_path=str(tmp_path / "dl.db"))
    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "P"}).json()
        target = client.post("/api/apps", json={"name": "A", "app_type": "web", "project_id": project["id"]}).json()
        pack = client.post("/api/validation-packs", json={
            "project_id": project["id"], "name": "K",
            "steps": [{"description": "d", "action_type": "navigate", "target": "/"}],
        }).json()
        run_id = client.post(
            f"/api/validation-packs/{pack['id']}/run",
            json={"app_target_id": target["id"], "execution_mode": "manual"},
        ).json()["id"]
        step_id = client.get(f"/api/runs/{run_id}").json()["steps"][0]["step_id"]

        upload = client.post(
            f"/api/live-runs/{run_id}/manual-steps/{step_id}/evidence",
            data={"name": 'a"\r\nX-Injected: yes', "evidence_type": "log"},
            files={"file": ("x.txt", io.BytesIO(b"hello"), "text/plain")},
        )
        download = client.get(f"/api/evidence/{upload.json()['id']}/download")

    disposition = download.headers["content-disposition"]
    assert download.status_code == 200 and download.content == b"hello"
    assert "\r" not in disposition and "\n" not in disposition
    assert disposition == 'attachment; filename="a___X-Injected: yes"'
