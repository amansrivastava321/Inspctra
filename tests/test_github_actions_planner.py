from qa_ai.cicd_runtime.github_actions_planner import GitHubActionsPlanner


def test_github_actions_planner_is_advisory_and_non_overwriting(artifact_store, tmp_dir):
    existing = tmp_dir / ".github" / "workflows" / "qa_ai_audit.yml"
    existing.parent.mkdir(parents=True)
    existing.write_text("name: existing", encoding="utf-8")

    result = GitHubActionsPlanner(artifact_store).run(repo_path=str(tmp_dir), dry_run=True)

    assert result["advisory_only"] is True
    assert result["apply_by_default"] is False
    assert result["permission_required_for_write"] is True
    assert any(row["exists"] for row in result["workflow_plans"])
    assert existing.read_text(encoding="utf-8") == "name: existing"
