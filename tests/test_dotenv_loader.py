"""Optional project .env: narrow, never overrides the real environment, never touches other directories."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from qa_ai.config import dotenv_loader
from qa_ai.config.dotenv_loader import DISABLE_VARIABLE, PROJECT_ROOT, load_project_dotenv
from qa_ai.config.settings import Settings

MANAGED = (
    "QA_AI_GEMINI_API_KEY", "QA_AI_GROQ_API_KEY", "QA_AI_ALLOW_CLOUD_MODELS", "GROQ_API_KEY",
    "INSPECTRA_SOMETHING", "SOME_OTHER_VARIABLE", "PATH_LIKE_VARIABLE",
)


@pytest.fixture(autouse=True)
def _enabled_and_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DISABLE_VARIABLE, raising=False)
    for name in MANAGED:
        # set-then-delete so monkeypatch removes whatever the loader writes after the test
        monkeypatch.setenv(name, "placeholder")
        monkeypatch.delenv(name)


def _write_env(root: Path, text: str) -> None:
    (root / ".env").write_text(text, encoding="utf-8")


def test_values_are_loaded_into_the_environment_and_settings(tmp_path: Path) -> None:
    _write_env(tmp_path, "QA_AI_GEMINI_API_KEY=file-gemini\nQA_AI_ALLOW_CLOUD_MODELS=true\n")

    applied = load_project_dotenv(tmp_path)

    assert applied == {"QA_AI_GEMINI_API_KEY": True, "QA_AI_ALLOW_CLOUD_MODELS": True}
    settings = Settings()
    assert settings.gemini_api_key == "file-gemini" and settings.allow_cloud_models is True


def test_real_environment_wins_over_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QA_AI_GROQ_API_KEY", "from-shell")
    _write_env(tmp_path, "QA_AI_GROQ_API_KEY=from-file\n")

    applied = load_project_dotenv(tmp_path)

    assert applied == {"QA_AI_GROQ_API_KEY": False}
    assert Settings().groq_api_key == "from-shell"


def test_only_known_names_are_accepted(tmp_path: Path) -> None:
    _write_env(
        tmp_path,
        "SOME_OTHER_VARIABLE=x\nPATH_LIKE_VARIABLE=/evil\nINSPECTRA_SOMETHING=ok\nGROQ_API_KEY=gk\n",
    )

    applied = load_project_dotenv(tmp_path)

    assert applied == {"INSPECTRA_SOMETHING": True, "GROQ_API_KEY": True}
    assert "SOME_OTHER_VARIABLE" not in __import__("os").environ


def test_blank_entries_from_the_template_are_ignored(tmp_path: Path) -> None:
    _write_env(tmp_path, "QA_AI_GEMINI_API_KEY=\nQA_AI_GROQ_API_KEY=\n")

    assert load_project_dotenv(tmp_path) == {}
    assert Settings().gemini_api_key == ""


def test_missing_file_loads_nothing(tmp_path: Path) -> None:
    assert load_project_dotenv(tmp_path) == {}


def test_can_be_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_env(tmp_path, "QA_AI_GEMINI_API_KEY=file-gemini\n")
    monkeypatch.setenv(DISABLE_VARIABLE, "1")

    assert load_project_dotenv(tmp_path) == {}
    assert Settings().gemini_api_key == ""


def test_missing_python_dotenv_is_not_fatal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_env(tmp_path, "QA_AI_GEMINI_API_KEY=file-gemini\n")
    monkeypatch.setitem(__import__("sys").modules, "dotenv", None)

    assert load_project_dotenv(tmp_path) == {}


def test_the_current_directory_is_never_searched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Auditing another app must not pick up that app's .env."""
    other_app = tmp_path / "other_app"
    other_app.mkdir()
    _write_env(other_app, "QA_AI_ALLOW_CLOUD_MODELS=true\nQA_AI_GEMINI_API_KEY=target-app-key\n")
    monkeypatch.chdir(other_app)
    monkeypatch.setattr(dotenv_loader, "PROJECT_ROOT", tmp_path / "empty_root")

    assert load_project_dotenv() == {}
    assert Settings().allow_cloud_models is False


def test_values_are_never_logged(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    _write_env(tmp_path, "QA_AI_GEMINI_API_KEY=super-secret-value\n")

    with caplog.at_level("DEBUG"):
        load_project_dotenv(tmp_path)

    assert "QA_AI_GEMINI_API_KEY" in caplog.text and "super-secret-value" not in caplog.text


# ── the committed template ───────────────────────────────────────────────────

def test_example_template_is_committable_but_real_env_is_not() -> None:
    def ignored(name: str) -> bool:
        return subprocess.run(
            ["git", "check-ignore", "-q", name], cwd=PROJECT_ROOT, check=False
        ).returncode == 0

    assert not ignored(".env.example")
    assert ignored(".env")


def test_example_template_has_no_secret_values() -> None:
    text = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    entries = dict(
        line.split("=", 1) for line in text.splitlines() if "=" in line and not line.lstrip().startswith("#")
    )

    for key_name in ("QA_AI_GEMINI_API_KEY", "QA_AI_GROQ_API_KEY", "QA_AI_OPENROUTER_API_KEY"):
        assert entries[key_name] == "", f"{key_name} must be blank in the template"
    assert entries["QA_AI_ALLOW_CLOUD_MODELS"] == "false"
    assert entries["QA_AI_MODEL_ROUTING_MODE"] == "local_first"
