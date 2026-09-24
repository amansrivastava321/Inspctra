from qa_ai.cicd_runtime.jenkins_pipeline_planner import JenkinsPipelinePlanner


def test_jenkins_pipeline_planner_generates_advisory_stage_plan(artifact_store, tmp_dir):
    result = JenkinsPipelinePlanner(artifact_store).run(repo_path=str(tmp_dir), dry_run=True)

    assert result["provider"] == "jenkins"
    assert result["advisory_only"] is True
    assert result["overwrite_allowed_automatically"] is False
    names = [row["name"] for row in result["stages"]]
    assert "Release Gate" in names
