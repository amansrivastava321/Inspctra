from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from PIL import Image

from qa_ai.product_backend.artifact_index import ArtifactIndex
from qa_ai.product_backend.models import (
    AppTarget,
    EvidenceFile,
    LiveRunRecord,
    Project,
    Provenance,
    ValidationPack,
)
from qa_ai.product_backend.report_exporters import ReportExportError, RunReportExporter, _css_string
from qa_ai.product_backend.storage import ProductStorage


RUN_ID = "run-export-123"
FORMATS = ["html", "pdf", "junit", "sarif"]


def test_css_page_margin_text_cannot_close_the_style_element() -> None:
    escaped = str(_css_string('Pack </style><script>alert("x")</script>'))

    assert "</style>" not in escaped
    assert "<script>" not in escaped
    assert "\\3C " in escaped


@pytest.fixture
def exporter_workspace(tmp_path: Path) -> tuple[RunReportExporter, ProductStorage, ArtifactIndex]:
    storage = ProductStorage(str(tmp_path / "reports.db"))
    index = ArtifactIndex(tmp_path / "artifacts")

    project = Project(
        id="project-export",
        name="Export project",
        provenance=Provenance.REAL_EXECUTION,
    )
    app = AppTarget(
        id="app-export",
        project_id=project.id,
        name="Smoke App",
        app_type="web",
        base_url="https://example.com",
        provenance=Provenance.REAL_EXECUTION,
    )
    pack = ValidationPack(
        id="pack-export",
        project_id=project.id,
        app_id=app.id,
        name="Homepage Checks",
        provenance=Provenance.REAL_EXECUTION,
    )
    storage.create_project(project.model_dump())
    storage.create_app_target(app.model_dump())
    storage.create_validation_pack(pack.model_dump())

    run = LiveRunRecord(
        id=RUN_ID,
        pack_id=pack.id,
        app_target_id=app.id,
        status="failed",
        started_at="2026-08-27T10:00:00Z",
        completed_at="2026-08-27T10:00:15Z",
        created_at="2026-08-27T09:59:59Z",
        provenance=Provenance.REAL_EXECUTION,
    )
    storage.create_run(run.model_dump())
    storage.replace_run_step_results(
        run.id,
        [
            {
                "step_id": "step-pass",
                "description": "Open <home>",
                "action_type": "navigate",
                "status": "passed",
                "duration_ms": 1200,
                "expected_result": "Dashboard",
                "actual_result": "Dashboard",
                "provenance": "REAL_EXECUTION",
            },
            {
                "step_id": "step-fail",
                "description": "Welcome heading",
                "action_type": "assert_text",
                "status": "failed",
                "duration_ms": 2000,
                "expected_result": "Welcome",
                "actual_result": "Login",
                "failure_reason": 'Expected <Welcome> & got "Login"',
                "provenance": "REAL_EXECUTION",
            },
            {
                "step_id": "step-error",
                "description": "Profile API",
                "action_type": "api_request",
                "status": "error",
                "duration_seconds": 3,
                "error": "Timeout while connecting",
                "provenance": "REAL_EXECUTION",
            },
        ],
        status="failed",
    )
    storage.update_run_status(
        run.id,
        "failed",
        started_at=run.started_at,
        completed_at=run.completed_at,
    )
    storage.update_run_provenance(run.id, Provenance.REAL_EXECUTION)

    image_buffer = BytesIO()
    Image.new("RGB", (80, 50), color=(65, 90, 170)).save(image_buffer, format="PNG")
    screenshot_bytes = image_buffer.getvalue()
    evidence_payloads = [
        (
            EvidenceFile(
                id="evidence-screenshot",
                run_id=run.id,
                step_id="step-fail",
                evidence_type="screenshot",
                name="Failure screenshot",
                relative_path=f"runs/{run.id}/failure.png",
                mime_type="image/png",
                size_bytes=len(screenshot_bytes),
                provenance=Provenance.REAL_EXECUTION,
            ),
            screenshot_bytes,
        ),
        (
            EvidenceFile(
                id="evidence-console",
                run_id=run.id,
                step_id="step-fail",
                evidence_type="console",
                name="Console warnings",
                relative_path=f"runs/{run.id}/console.json",
                mime_type="application/json",
                provenance=Provenance.REAL_EXECUTION,
            ),
            json.dumps([{"type": "error", "text": "Unsafe <console> & detail"}]).encode(),
        ),
        (
            EvidenceFile(
                id="evidence-request",
                run_id=run.id,
                step_id="step-error",
                evidence_type="api_request",
                name="API request",
                relative_path=f"runs/{run.id}/request.json",
                mime_type="application/json",
                provenance=Provenance.REAL_EXECUTION,
            ),
            json.dumps({"method": "GET", "url": "https://example.com/profile"}).encode(),
        ),
        (
            EvidenceFile(
                id="evidence-response",
                run_id=run.id,
                step_id="step-error",
                evidence_type="api_response",
                name="API response",
                relative_path=f"runs/{run.id}/response.json",
                mime_type="application/json",
                provenance=Provenance.REAL_EXECUTION,
            ),
            json.dumps({"status_code": 504, "body": {"error": "timeout"}}).encode(),
        ),
    ]
    for evidence, payload in evidence_payloads:
        index.write_file(evidence.relative_path, payload)
        evidence.size_bytes = len(payload)
        storage.create_evidence(evidence.model_dump())

    exporter = RunReportExporter(storage, index)
    try:
        yield exporter, storage, index
    finally:
        storage.close()


def test_summary_uses_one_terminal_run_context(exporter_workspace) -> None:
    exporter, _, _ = exporter_workspace

    summary = exporter.summary(RUN_ID)

    assert summary == {
        "run_id": RUN_ID,
        "pack_name": "Homepage Checks",
        "app_name": "Smoke App",
        "status": "failed",
        "started_at": "2026-08-27T10:00:00Z",
        "completed_at": "2026-08-27T10:00:15Z",
        "duration_seconds": 15.0,
        "steps_total": 3,
        "steps_passed": 1,
        "steps_failed": 1,
        "steps_error": 1,
        "failure_reasons": ['Expected <Welcome> & got "Login"', "Timeout while connecting"],
        "provenance": "REAL_EXECUTION",
        "formats_available": FORMATS,
    }


def test_html_is_standalone_escaped_and_embeds_screenshot(exporter_workspace) -> None:
    exporter, _, _ = exporter_workspace

    html = exporter.export_html(RUN_ID)

    assert html.startswith("<!doctype html>")
    assert "<style>" in html
    assert "prefers-color-scheme: light" in html
    assert "data:image/" in html
    assert "Open &lt;home&gt;" in html
    assert "Unsafe &lt;console&gt; &amp; detail" in html
    assert "REAL_EXECUTION" in html
    assert '<table class="detail-grid">' in html
    assert 'class="badge provenance"' in html
    assert 'aria-label="Overall provenance: REAL_EXECUTION"' in html
    assert "Generated by Inspectra" in html
    assert "https://cdn" not in html
    assert "<script" not in html


def test_junit_is_parseable_with_failure_error_and_console_output(exporter_workspace) -> None:
    exporter, _, _ = exporter_workspace

    root = ET.fromstring(exporter.export_junit(RUN_ID))

    assert root.tag == "testsuite"
    assert root.attrib["name"] == "Homepage Checks"
    assert root.attrib["tests"] == "3"
    assert root.attrib["failures"] == "1"
    assert root.attrib["errors"] == "1"
    assert root.attrib["time"] == "15.000"
    cases = root.findall("testcase")
    assert len(cases) == 3
    assert cases[1].find("failure").attrib["message"] == 'Expected <Welcome> & got "Login"'
    assert "Unsafe <console> & detail" in (cases[1].findtext("system-out") or "")
    assert cases[2].find("error").attrib["message"] == "Timeout while connecting"


def test_sarif_is_21_with_stable_rules_results_and_app_location(exporter_workspace) -> None:
    exporter, _, _ = exporter_workspace

    sarif = exporter.export_sarif(RUN_ID)

    assert sarif["version"] == "2.1.0"
    assert sarif["$schema"].endswith("sarif-schema-2.1.0.json")
    sarif_run = sarif["runs"][0]
    assert sarif_run["tool"]["driver"]["name"] == "Inspectra"
    assert {rule["id"] for rule in sarif_run["tool"]["driver"]["rules"]} == {
        "assert-text",
        "api-request",
    }
    assert [result["level"] for result in sarif_run["results"]] == ["error", "error"]
    assert sarif_run["results"][0]["message"]["text"] == 'Expected <Welcome> & got "Login"'
    assert sarif_run["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "https://example.com"


def test_pdf_uses_shared_print_html_and_stays_below_typical_size_limit(exporter_workspace) -> None:
    exporter, _, _ = exporter_workspace

    html = exporter.export_html(RUN_ID)
    pdf = exporter.export_pdf(RUN_ID)

    assert "@top-center { content:" in html
    assert ".step { break-before:page;" in html
    assert "details pre { color:#202533; }" in html
    assert "@bottom-left { content:" in html
    assert 'counter(page) " of " counter(pages)' in html
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) < 10 * 1024 * 1024


@pytest.mark.parametrize("status", ["pending", "running", "blocked"])
def test_non_terminal_run_is_rejected(exporter_workspace, status: str) -> None:
    exporter, storage, _ = exporter_workspace
    storage.update_run_status(RUN_ID, status)

    with pytest.raises(ReportExportError, match="Report not available — run is still in progress") as exc:
        exporter.summary(RUN_ID)

    assert exc.value.status_code == 409


def test_missing_run_is_rejected(exporter_workspace) -> None:
    exporter, _, _ = exporter_workspace

    with pytest.raises(ReportExportError, match="Run not found") as exc:
        exporter.export_html("missing-run")

    assert exc.value.status_code == 404
