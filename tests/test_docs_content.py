from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").lower()


def test_key_concepts_present_in_docs() -> None:
    architecture_text = _read("docs/architecture/overview.md") + "\n" + _read("docs/architecture/artifact_contracts.md")
    safety_text = _read("docs/safety/permission_model.md") + "\n" + _read("docs/safety/dry_run_policy.md")
    ai_text = _read("docs/ai_reasoning/deterministic_first_principle.md") + "\n" + _read("docs/ai_reasoning/evidence_linked_reasoning.md")
    graphify_text = _read("docs/architecture/graphify_usage.md")
    orchestration_text = _read("docs/architecture/orchestration_model.md")

    assert "artifactstore" in architecture_text
    assert "artifactvalidator" in architecture_text
    assert "workflowengine" in orchestration_text
    assert "graphify" in graphify_text
    assert "dry-run" in safety_text
    assert "permission-gated" in safety_text
    assert "deterministic-first" in ai_text
    assert "evidence-linked" in ai_text


def test_roadmap_mentions_next_phases() -> None:
    text = _read("docs/roadmap/next_phases.md")
    assert "phase 15 autonomous remediation + controlled change engine" in text
    assert "phase 16 ci/cd continuous audit runtime" in text
    assert "phase 17 scalability/performance hardening" in text
    assert "phase 18 enterprise multi-tenant layer" in text
