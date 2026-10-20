"""The graphify knowledge graph is optional: absent is fine, present-but-unusable is degraded."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qa_ai.cli.audit_command import AuditCommand
from qa_ai.cli.profile_manager import ProfileManager


def _command() -> AuditCommand:
    return AuditCommand(profile_manager=ProfileManager(Path(__file__).resolve().parents[1] / "qa_ai" / "config"))


def _write_graph(root: Path, graph: str | None = None, report: str | None = None) -> None:
    out = root / "graphify-out"
    out.mkdir(parents=True, exist_ok=True)
    if graph is not None:
        (out / "graph.json").write_text(graph, encoding="utf-8")
    if report is not None:
        (out / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")


GOOD_GRAPH = json.dumps({"nodes": [{"id": "a"}, {"id": "b"}], "edges": [{"source": "a", "target": "b"}]})


def test_a_missing_graph_is_fine_because_it_is_optional(tmp_path: Path) -> None:
    check = _command()._check_graphify_outputs(tmp_path)

    assert (check["ok"], check["state"], check["optional"]) == (True, "absent", True)


def test_a_complete_graph_is_ok_and_counted(tmp_path: Path) -> None:
    _write_graph(tmp_path, graph=GOOD_GRAPH, report="# report")

    check = _command()._check_graphify_outputs(tmp_path)

    assert (check["ok"], check["state"], check["nodes"], check["edges"]) == (True, "ok", 2, 1)


@pytest.mark.parametrize(
    ("graph", "report", "state"),
    [
        ("{not json", "# report", "corrupt"),
        ("[1, 2, 3]", "# report", "corrupt"),  # valid JSON, wrong shape: must not crash
        (GOOD_GRAPH, None, "incomplete"),
        (None, "# report", "incomplete"),
    ],
)
def test_an_unusable_graph_is_degraded(tmp_path: Path, graph: str | None, report: str | None, state: str) -> None:
    _write_graph(tmp_path, graph=graph, report=report)

    check = _command()._check_graphify_outputs(tmp_path)

    assert (check["ok"], check["state"]) == (False, state)


# ── what the doctor commands report ──────────────────────────────────────────

def test_doctor_does_not_blame_a_missing_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    report = _command().run_doctor(output_dir=str(tmp_path / "artifacts"))

    failing = [name for name, value in report["checks"].items() if isinstance(value, dict) and not value.get("ok", True)]
    assert "graphify_outputs" not in failing


def test_doctor_reports_degraded_for_a_corrupt_graph(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _write_graph(tmp_path, graph="{not json", report="# report")

    report = _command().run_doctor(output_dir=str(tmp_path / "artifacts"))

    assert report["status"] == "degraded"
    assert report["checks"]["graphify_outputs"]["state"] == "corrupt"


def test_runtime_lab_doctor_status_follows_the_graph_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert _command().run_runtime_lab_doctor(output_dir=str(tmp_path / "a1"))["status"] == "ok"

    _write_graph(tmp_path, graph="{not json", report="# report")
    assert _command().run_runtime_lab_doctor(output_dir=str(tmp_path / "a2"))["status"] == "degraded"
