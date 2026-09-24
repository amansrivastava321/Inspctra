"""
tests/test_json_io.py - Focused tests for qa_ai/utils/json_io.py.
"""
import logging
import pytest
from pathlib import Path
from unittest.mock import patch

from qa_ai.utils.json_io import read_json, write_json, update_json


class TestReadJson:
    def test_returns_none_for_missing_file(self, tmp_path):
        result = read_json(tmp_path / "nonexistent.json")
        assert result is None

    def test_malformed_json_returns_none_and_logs(self, tmp_path, caplog):
        bad = tmp_path / "bad.json"
        bad.write_text("{not: valid json}", encoding="utf-8")
        with caplog.at_level(logging.ERROR, logger="qa_ai.utils.json_io"):
            result = read_json(bad)
        assert result is None
        assert any("Invalid JSON" in r.message or "bad.json" in r.message for r in caplog.records)

    def test_valid_json_returns_data(self, tmp_path):
        good = tmp_path / "good.json"
        good.write_text('{"key": 42}', encoding="utf-8")
        result = read_json(good)
        assert result == {"key": 42}

    def test_read_failure_logs_and_returns_none(self, tmp_path, caplog):
        path = tmp_path / "unreadable.json"
        path.write_text('{"ok": true}', encoding="utf-8")
        with patch("builtins.open", side_effect=OSError("permission denied")):
            with caplog.at_level(logging.ERROR, logger="qa_ai.utils.json_io"):
                result = read_json(path)
        assert result is None
        assert any("permission denied" in r.message for r in caplog.records)


class TestWriteJson:
    def test_writes_and_reads_back(self, tmp_path):
        p = tmp_path / "out.json"
        ok = write_json(p, {"a": 1})
        assert ok is True
        assert p.exists()
        import json
        assert json.loads(p.read_text()) == {"a": 1}

    def test_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "nested" / "deep" / "out.json"
        ok = write_json(p, [1, 2, 3])
        assert ok is True
        assert p.exists()

    def test_write_failure_returns_false_and_logs(self, tmp_path, caplog):
        p = tmp_path / "out.json"
        with patch("json.dump", side_effect=TypeError("not serializable")):
            with caplog.at_level(logging.DEBUG, logger="qa_ai.utils.json_io"):
                result = write_json(p, {"bad": object()})
        assert result is False
        # The debug log from the cleanup handler should be present
        assert any(
            "Write failed" in r.message or "not serializable" in r.message
            for r in caplog.records
        )

    def test_temp_file_cleaned_up_on_failure(self, tmp_path):
        p = tmp_path / "out.json"
        with patch("json.dump", side_effect=IOError("disk full")):
            write_json(p, {"x": 1})
        # No .tmp files should remain
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == []


class TestUpdateJson:
    def test_merges_into_existing(self, tmp_path):
        p = tmp_path / "data.json"
        write_json(p, {"a": 1, "b": 2})
        ok = update_json(p, {"b": 99, "c": 3})
        assert ok is True
        import json
        result = json.loads(p.read_text())
        assert result == {"a": 1, "b": 99, "c": 3}

    def test_creates_new_file_if_missing(self, tmp_path):
        p = tmp_path / "new.json"
        ok = update_json(p, {"x": 10})
        assert ok is True
        import json
        assert json.loads(p.read_text()) == {"x": 10}
