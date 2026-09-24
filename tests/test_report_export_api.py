from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from qa_ai.product_backend.models import AppTarget, LiveRunRecord, Project, Provenance, ValidationPack
from qa_ai.product_backend.server import create_product_app


RUN_ID = "run-api-export"


@pytest.fixture
def report_client(tmp_path: Path) -> TestClient:
    app = create_product_app(
        db_path=str(tmp_path / "report-api.db"),
        artifacts_dir=str(tmp_path / "artifacts"),
    )
    with TestClient(app) as client:
        storage = client.app.state.storage
        project = Project(id="project-api-export", name="Export project")
        target = AppTarget(
            id="app-api-export",
            project_id=project.id,
            name="Export app",
            app_type="web",
            base_url="https://example.com",
        )
        pack = ValidationPack(
            id="pack-api-export",
            project_id=project.id,
            app_id=target.id,
            name="Export pack",
        )
        storage.create_project(project.model_dump())
        storage.create_app_target(target.model_dump())
        storage.create_validation_pack(pack.model_dump())
        run = LiveRunRecord(
            id=RUN_ID,
            pack_id=pack.id,
            app_target_id=target.id,
            status="failed",
            started_at="2026-08-27T10:00:00Z",
            completed_at="2026-08-27T10:00:05Z",
            provenance=Provenance.REAL_EXECUTION,
        )
        storage.create_run(run.model_dump())
        storage.replace_run_step_results(
            run.id,
            [{
                "step_id": "step-api-export",
                "description": "Homepage title",
                "action_type": "assert_title_contains",
                "status": "failed",
                "failure_reason": "Expected Inspectra, got Login",
                "duration_ms": 1250,
                "provenance": "REAL_EXECUTION",
            }],
            status="failed",
        )
        storage.update_run_status(
            run.id,
            "failed",
            started_at=run.started_at,
            completed_at=run.completed_at,
        )
        yield client


@pytest.mark.parametrize(
    ("report_format", "media_type", "extension"),
    [
        ("html", "text/html", "html"),
        ("pdf", "application/pdf", "pdf"),
        ("junit", "application/xml", "junit.xml"),
        ("sarif", "application/json", "sarif.json"),
    ],
)
def test_terminal_run_downloads_have_expected_content_and_filename(
    report_client: TestClient,
    report_format: str,
    media_type: str,
    extension: str,
) -> None:
    response = report_client.get(f"/api/runs/{RUN_ID}/report?format={report_format}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(media_type)
    assert response.headers["content-disposition"] == (
        f'attachment; filename="inspectra-run-{RUN_ID}.{extension}"'
    )
    assert response.headers["x-content-type-options"] == "nosniff"
    if report_format == "html":
        assert response.text.startswith("<!doctype html>")
    elif report_format == "pdf":
        assert response.content.startswith(b"%PDF-")
    elif report_format == "junit":
        assert ET.fromstring(response.content).tag == "testsuite"
    else:
        assert response.json()["version"] == "2.1.0"


def test_report_summary_is_available_for_terminal_run(report_client: TestClient) -> None:
    response = report_client.get(f"/api/runs/{RUN_ID}/report/summary")

    assert response.status_code == 200
    assert response.json() == {
        "run_id": RUN_ID,
        "pack_name": "Export pack",
        "app_name": "Export app",
        "status": "failed",
        "started_at": "2026-08-27T10:00:00Z",
        "completed_at": "2026-08-27T10:00:05Z",
        "duration_seconds": 5.0,
        "steps_total": 1,
        "steps_passed": 0,
        "steps_failed": 1,
        "steps_error": 0,
        "failure_reasons": ["Expected Inspectra, got Login"],
        "provenance": "REAL_EXECUTION",
        "formats_available": ["html", "pdf", "junit", "sarif"],
    }


@pytest.mark.parametrize("status", ["pending", "running"])
def test_nonterminal_run_returns_exact_conflict(
    report_client: TestClient,
    status: str,
) -> None:
    report_client.app.state.storage.update_run_status(RUN_ID, status)

    response = report_client.get(f"/api/runs/{RUN_ID}/report?format=html")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Report not available — run is still in progress."
    }


def test_missing_run_and_unknown_format_are_rejected(report_client: TestClient) -> None:
    missing = report_client.get("/api/runs/not-a-run/report?format=html")
    unsupported = report_client.get(f"/api/runs/{RUN_ID}/report?format=json")

    assert missing.status_code == 404
    assert unsupported.status_code == 422
