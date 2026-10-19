"""`qa_ai audit` must complete on a real app and report what is actually in its source."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qa_ai.cli.main import main

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
APP = REPOSITORY_ROOT / "sample_apps" / "vulnerable_fastapi_app"


@pytest.fixture(scope="module")
def audit_output(tmp_path_factory) -> Path:
    output = tmp_path_factory.mktemp("audit")
    exit_code = main(["audit", str(APP), "--profile", "api", "--output-dir", str(output)])
    assert exit_code == 0
    return output


def _load(output: Path, name: str) -> dict:
    return json.loads((output / f"{name}.json").read_text(encoding="utf-8"))


def test_workflow_completes(audit_output: Path) -> None:
    assert _load(audit_output, "workflow_result")["status"].lower() == "completed"


def test_static_audits_inspect_the_target_source(audit_output: Path) -> None:
    code_quality = _load(audit_output, "code_quality_results")
    dependencies = _load(audit_output, "dependency_audit_results")
    database = _load(audit_output, "database_audit_results")

    assert code_quality["summary"]["files_audited"] > 0
    assert any("todo" in json.dumps(check).lower() for check in code_quality["checks"])
    assert dependencies["summary"]["files_audited"] > 0
    assert any(check["check_id"] != "DB-MIG-002" for check in database["checks"])


def test_findings_come_from_the_source_not_from_an_unreachable_server(audit_output: Path) -> None:
    titles = [finding["title"] for finding in _load(audit_output, "correlated_findings")["findings"]]

    assert any("/users" in title for title in titles)  # public GET /users, seeded in app.py
    assert not any(title.startswith("Test failed") for title in titles)
    assert any("could not run" in issue for issue in _load(audit_output, "execution_results")["environment_issues"])
