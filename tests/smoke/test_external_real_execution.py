"""Opt-in external proof that the real browser and HTTP paths work."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qa_ai.product_backend.server import create_product_app


pytestmark = pytest.mark.skipif(
    os.getenv("INSPECTRA_EXTERNAL_SMOKE") != "1",
    reason="Set INSPECTRA_EXTERNAL_SMOKE=1 to allow external network execution.",
)


def _poll(client: TestClient, run_id: str) -> dict:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] not in {"pending", "running"}:
            return run
        time.sleep(0.1)
    pytest.fail(f"Run {run_id} did not finish within 60 seconds")


def test_example_web_and_httpbin_api_produce_real_evidence(tmp_path: Path) -> None:
    app = create_product_app(
        artifacts_dir=str(tmp_path / "artifacts"),
        db_path=str(tmp_path / "external-smoke.db"),
    )
    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "External Smoke"}).json()
        web_app = client.post(
            "/api/apps",
            json={
                "project_id": project["id"],
                "name": "Example Web",
                "app_type": "web",
                "base_url": "https://example.com",
            },
        ).json()
        web_pack = client.post(
            "/api/validation-packs",
            json={
                "project_id": project["id"],
                "name": "Example Web Pack",
                "steps": [
                    {
                        "description": "Open example.com",
                        "action_type": "navigate",
                        "target": "https://example.com",
                    },
                    {
                        "description": "Verify example.com title",
                        "action_type": "assert_title_contains",
                        "expected_result": "Example Domain",
                    },
                ],
            },
        ).json()
        web_started = client.post(
            f"/api/validation-packs/{web_pack['id']}/run",
            json={"app_target_id": web_app["id"]},
        ).json()
        web_run = _poll(client, web_started["id"])
        assert web_run["status"] == "completed"
        assert web_run["provenance"] == "REAL_EXECUTION"
        assert {step["provenance"] for step in web_run["step_results"]} == {"REAL_EXECUTION"}
        web_evidence = client.get(f"/api/evidence?run_id={web_run['id']}").json()
        screenshots = [item for item in web_evidence if item["evidence_type"] == "screenshot"]
        assert len(screenshots) == 2
        for item in screenshots:
            assert item["mime_type"] == "image/png"
            assert item["size_bytes"] > 100
            assert item["provenance"] == "REAL_EXECUTION"

        api_app = client.post(
            "/api/apps",
            json={
                "project_id": project["id"],
                "name": "HTTPBin API",
                "app_type": "api",
                "base_url": "https://httpbin.org",
            },
        ).json()
        api_pack = client.post(
            "/api/validation-packs",
            json={
                "project_id": project["id"],
                "name": "HTTPBin API Pack",
                "steps": [
                    {
                        "description": "GET httpbin",
                        "action_type": "api_request",
                        "method": "GET",
                        "url": "https://httpbin.org/get",
                        "expected_status": 200,
                    }
                ],
            },
        ).json()
        api_started = client.post(
            f"/api/validation-packs/{api_pack['id']}/run",
            json={"app_target_id": api_app["id"]},
        ).json()
        api_run = _poll(client, api_started["id"])
        assert api_run["status"] == "completed"
        assert api_run["provenance"] == "REAL_EXECUTION"
        api_evidence = client.get(f"/api/evidence?run_id={api_run['id']}").json()
        assert {item["evidence_type"] for item in api_evidence} >= {
            "api_request",
            "api_response",
            "api_assertion",
        }
        assert {item["provenance"] for item in api_evidence} == {"REAL_EXECUTION"}
