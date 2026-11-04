"""Helpers for the real-device tests: where to keep screenshots, and running a pack through the product API."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def enabled(platform: str) -> bool:
    """Real-device tests only run on the matching CI runner (INSPECTRA_NATIVE_E2E=<platform>)."""
    return os.environ.get("INSPECTRA_NATIVE_E2E") == platform


def save_artifact(name: str, data: bytes) -> Path:
    folder = Path(os.environ.get("INSPECTRA_E2E_ARTIFACTS", "native-e2e-artifacts"))
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(data)
    return path


def run_pack_on_device(tmp_path: Path, app: Dict[str, Any], steps: List[Dict[str, Any]], timeout: float = 600) -> Dict[str, Any]:
    """Create an app target and pack through the API, allow the platform, run the pack, return the finished run."""
    os.environ.setdefault("INSPECTRA_ALLOWED_HOSTS", "testserver")
    from fastapi.testclient import TestClient

    from qa_ai.product_backend.server import create_product_app

    product = create_product_app(artifacts_dir=str(tmp_path / "artifacts"), db_path=str(tmp_path / "e2e.db"))
    with TestClient(product) as client:
        project = client.post("/api/projects", json={"name": "E2E", "description": ""}).json()
        target = client.post("/api/apps", json={**app, "name": "Device app", "project_id": project["id"]}).json()
        pack = client.post("/api/validation-packs", json={
            "project_id": project["id"], "app_id": target["id"], "name": "Device check", "description": "",
        }).json()
        case = client.post(f"/api/validation-packs/{pack['id']}/test-cases",
                           json={"title": "Device flow", "enabled": True, "steps": []}).json()
        for step in steps:
            created = client.post(f"/api/test-cases/{case['test_case_id']}/steps", json=step)
            assert created.status_code == 201, created.text

        refused = client.post(f"/api/validation-packs/{pack['id']}/run", json={"app_target_id": target["id"]})
        assert refused.status_code == 409, "a run must be refused before the user allows the platform"

        platform = app["app_type"]
        scopes = [s["id"] for s in client.get(f"/api/native/{platform}/readiness").json()["consent_scopes"]]
        assert client.put(f"/api/native/{platform}/consent", json={"scopes": scopes}).status_code == 200

        run = client.post(f"/api/validation-packs/{pack['id']}/run", json={"app_target_id": target["id"]}).json()
        deadline = time.time() + timeout
        while time.time() < deadline:
            row = client.get(f"/api/runs/{run['id']}").json()
            if row["status"] in ("completed", "failed", "cancelled"):
                return row
            time.sleep(1)
        raise AssertionError("the run did not finish")
