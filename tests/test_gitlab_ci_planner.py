from qa_ai.cicd_runtime.gitlab_ci_planner import GitLabCIPlanner


def test_gitlab_ci_planner_generates_advisory_stages_only(artifact_store, tmp_dir):
    result = GitLabCIPlanner(artifact_store).run(repo_path=str(tmp_dir), dry_run=True)

    assert result["provider"] == "gitlab"
    assert result["advisory_only"] is True
    assert result["overwrite_allowed_automatically"] is False
    assert len(result["stages"]) >= 3
