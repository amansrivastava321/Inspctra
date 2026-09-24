from qa_ai.cicd.ci_provider_detector import CIProviderDetector
from qa_ai.cicd_runtime.ci_provider_detector import CIProviderDetector as RuntimeCIProviderDetector
import pytest


@pytest.fixture(autouse=True)
def isolated_ci_environment(monkeypatch):
    for key in ("GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL", "TF_BUILD",
                "AZURE_HTTP_USER_AGENT", "SYSTEM_COLLECTIONURI", "CI"):
        monkeypatch.delenv(key, raising=False)


def test_ci_provider_detector_detects_github_from_repo_layout(artifact_store, tmp_dir):
    (tmp_dir / ".github" / "workflows").mkdir(parents=True)

    result = CIProviderDetector(artifact_store).run(repo_path=str(tmp_dir))

    assert result["provider"] == "github"
    assert result["known_provider"] is True
    assert artifact_store.load_artifact("cicd_provider_report")["provider"] == "github"


def test_cicd_runtime_provider_detector_supports_azure_marker(artifact_store, tmp_dir):
    (tmp_dir / "azure-pipelines.yml").write_text("trigger: [main]", encoding="utf-8")

    result = RuntimeCIProviderDetector(artifact_store).run(repo_path=str(tmp_dir))

    assert result["provider"] == "azure"
    assert result["known_provider"] is True
    assert result["advisory_only"] is True


def test_runtime_environment_marker_takes_precedence(artifact_store, tmp_dir, monkeypatch):
    (tmp_dir / "azure-pipelines.yml").write_text("trigger: [main]", encoding="utf-8")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    result = RuntimeCIProviderDetector(artifact_store).run(repo_path=str(tmp_dir))
    assert result["provider"] == "github"
    assert result["evidence"][0]["type"] == "environment"
