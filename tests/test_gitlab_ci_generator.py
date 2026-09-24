from qa_ai.cicd.gitlab_ci_generator import GitLabCIGenerator


def test_gitlab_ci_generator_dry_run_plan_only(tmp_dir):
    plan = GitLabCIGenerator().plan(repo_path=str(tmp_dir), dry_run=True, explicit_approval=False)

    assert plan["provider"] == "gitlab"
    assert plan["apply_by_default"] is False
    assert plan["file_plan"]["written"] is False

