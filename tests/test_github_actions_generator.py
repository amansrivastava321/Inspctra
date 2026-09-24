from qa_ai.cicd.github_actions_generator import GitHubActionsGenerator


def test_github_actions_generator_dry_run_and_no_overwrite_without_approval(tmp_dir):
    workflow = tmp_dir / ".github" / "workflows" / "qa_ai_audit.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("existing", encoding="utf-8")

    plan = GitHubActionsGenerator().plan(repo_path=str(tmp_dir), dry_run=True, explicit_approval=False)

    assert plan["dry_run"] is True
    assert plan["file_plan"]["action"] == "skip_existing_requires_approval"
    assert workflow.read_text(encoding="utf-8") == "existing"

