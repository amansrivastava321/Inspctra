from qa_ai.cicd.jenkins_pipeline_generator import JenkinsPipelineGenerator


def test_jenkins_pipeline_generator_dry_run_plan_only(tmp_dir):
    plan = JenkinsPipelineGenerator().plan(repo_path=str(tmp_dir), dry_run=True, explicit_approval=False)

    assert plan["provider"] == "jenkins"
    assert plan["approval_required_for_overwrite"] is True
    assert plan["file_plan"]["written"] is False

