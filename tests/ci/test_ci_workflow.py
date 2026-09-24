"""Contract tests for the repository's GitHub Actions CI workflow."""

from __future__ import annotations

from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"


def _load_workflow() -> dict:
    assert WORKFLOW_PATH.is_file(), "The CI workflow must exist at .github/workflows/ci.yml"
    workflow = yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert isinstance(workflow, dict)
    return workflow


def _run_commands(job: dict) -> str:
    return "\n".join(
        step["run"]
        for step in job["steps"]
        if isinstance(step, dict) and "run" in step
    )


def test_ci_runs_for_every_push_and_pull_request_with_read_only_permissions() -> None:
    workflow = _load_workflow()

    assert set(workflow["on"]) == {"push", "pull_request"}
    assert workflow["permissions"] == {"contents": "read"}


def test_backend_and_frontend_jobs_are_independent_and_bounded() -> None:
    jobs = _load_workflow()["jobs"]

    assert set(jobs) == {"backend", "frontend"}
    for job in jobs.values():
        assert job["runs-on"] == "ubuntu-latest"
        assert 1 <= int(job["timeout-minutes"]) <= 30
        assert "needs" not in job
        assert "continue-on-error" not in job


def test_backend_job_uses_python_311_and_runs_all_required_checks() -> None:
    backend = _load_workflow()["jobs"]["backend"]
    setup = next(step for step in backend["steps"] if step.get("uses") == "actions/setup-python@v5")
    commands = _run_commands(backend)

    assert setup["with"]["python-version"] == "3.11"
    assert setup["with"]["cache"] == "pip"
    assert setup["with"]["cache-dependency-path"] == "requirements.txt"
    assert "python -m compileall qa_ai/" in commands
    assert "python -u -m pytest --collect-only tests/ -vv -s" in commands
    assert "python -m pytest tests/smoke/test_full_journey.py -v" in commands
    assert (
        "python -m pytest tests/ -v "
        "--ignore=tests/smoke/test_external_real_execution.py"
    ) in commands


def test_collection_is_scoped_bounded_and_emits_stacks_on_timeout() -> None:
    backend = _load_workflow()["jobs"]["backend"]
    collection = next(step for step in backend["steps"] if step.get("name") == "Collect tests")

    assert collection["timeout-minutes"] == "3"
    assert collection["env"]["PYTHONFAULTHANDLER"] == "1"
    assert "timeout --signal=ABRT --kill-after=10s 120s" in collection["run"]
    assert "--collect-only tests/ -vv -s" in collection["run"]
    assert "continue-on-error" not in collection
    assert "||" not in collection["run"]


def test_frontend_job_uses_frozen_dependencies_and_fails_on_lint_errors() -> None:
    frontend = _load_workflow()["jobs"]["frontend"]
    setup = next(step for step in frontend["steps"] if step.get("uses") == "actions/setup-node@v4")
    commands = _run_commands(frontend)

    assert setup["with"]["node-version"] == "18"
    assert setup["with"]["cache"] == "npm"
    assert setup["with"]["cache-dependency-path"] == "package-lock.json"
    assert "npm ci" in commands
    assert "npm run lint --workspace=inspectra-ui" in commands
    assert "npm test --workspace=inspectra-ui -- --watchAll=false" in commands
    assert "npm run build --workspace=inspectra-ui" in commands
    assert "npm install" not in commands
    assert "||" not in commands


def test_workflow_uses_only_expected_pinned_actions_and_has_no_deployment() -> None:
    workflow = _load_workflow()
    used_actions = {
        step["uses"]
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if "uses" in step
    }
    commands = "\n".join(_run_commands(job) for job in workflow["jobs"].values())

    assert used_actions == {
        "actions/checkout@v4",
        "actions/setup-python@v5",
        "actions/setup-node@v4",
    }
    assert "deploy" not in commands.lower()
    assert "publish" not in commands.lower()
