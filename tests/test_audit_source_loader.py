"""The static audits only see what the workflow loads for them."""

from __future__ import annotations

import os
from pathlib import Path

from qa_ai.audit.source_loader import load_audit_inputs


def _write(root: Path, relative: str, text: str = "x = 1\n") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_loads_source_sql_and_dependency_manifests(tmp_path: Path) -> None:
    _write(tmp_path, "app.py", "# TODO: fix\n")
    _write(tmp_path, "db/schema.sql", "CREATE TABLE t (id INT);\n")
    _write(tmp_path, "requirements.txt", "fastapi==0.70.0\n")
    _write(tmp_path, "web/package.json", "{}")

    inputs = load_audit_inputs(tmp_path)

    assert set(inputs.file_contents) == {"app.py", "db/schema.sql"}
    assert set(inputs.dependency_files) == {"requirements.txt", "web/package.json"}
    assert {"app.py", "db/schema.sql", "requirements.txt", "web/package.json"} <= set(inputs.file_list)


def test_config_files_are_listed_by_name_even_when_not_read(tmp_path: Path) -> None:
    _write(tmp_path, ".env", "SECRET=1\n")
    _write(tmp_path, "README.md", "# hi\n")
    _write(tmp_path, ".github/workflows/ci.yml", "name: CI\n")

    inputs = load_audit_inputs(tmp_path)

    assert {".env", "README.md", ".github/workflows/ci.yml"} <= set(inputs.file_list)
    assert ".env" not in inputs.file_contents  # secrets are never copied into audit artifacts


def test_skips_vendored_directories_generated_files_and_lock_files(tmp_path: Path) -> None:
    _write(tmp_path, "node_modules/lib/index.js")
    _write(tmp_path, "build/out.js")
    _write(tmp_path, "static/app.min.js")
    _write(tmp_path, "package-lock.json", "{}")
    _write(tmp_path, "keep.py")

    inputs = load_audit_inputs(tmp_path)

    assert inputs.file_list == ["keep.py"]


def test_does_not_follow_symlinks_out_of_the_target(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    target = tmp_path / "target"
    _write(outside, "secret.py", "TOKEN = 'abc'\n")
    _write(target, "app.py")
    os.symlink(outside / "secret.py", target / "link.py")
    os.symlink(outside, target / "linked_dir")

    inputs = load_audit_inputs(target)

    assert inputs.file_list == ["app.py"]
    assert not any("secret" in text for text in inputs.file_contents.values())


def test_respects_size_and_count_limits(tmp_path: Path) -> None:
    _write(tmp_path, "huge.py", "x" * 2000)
    for index in range(5):
        _write(tmp_path, f"m{index}.py")

    inputs = load_audit_inputs(tmp_path, max_file_bytes=1000, max_content_files=3)

    assert "huge.py" in inputs.file_list and "huge.py" not in inputs.file_contents
    assert len(inputs.file_contents) == 3


def test_missing_directory_yields_nothing(tmp_path: Path) -> None:
    inputs = load_audit_inputs(tmp_path / "does-not-exist")

    assert inputs.file_contents == {} and inputs.file_list == []
