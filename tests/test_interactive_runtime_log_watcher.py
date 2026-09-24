"""Tests for qa_ai.interactive_runtime.log_watcher.LogWatcher."""
import io
import threading
import time
from unittest.mock import MagicMock

import pytest

from qa_ai.interactive_runtime.log_watcher import LogWatcher, _redact


class TestLogWatcherIngestion:
    def test_ingest_single_line(self):
        watcher = LogWatcher()
        watcher.ingest_line("hello world")
        assert "hello world" in watcher.all_lines()

    def test_ingest_lines_batch(self):
        watcher = LogWatcher()
        watcher.ingest_lines(["line a", "line b", "line c"])
        lines = watcher.all_lines()
        assert "line a" in lines
        assert "line b" in lines
        assert "line c" in lines

    def test_source_filtering(self):
        watcher = LogWatcher()
        watcher.ingest_line("from app", source="app")
        watcher.ingest_line("from backend", source="backend")
        assert watcher.all_lines(source="app") == ["from app"]
        assert watcher.all_lines(source="backend") == ["from backend"]

    def test_all_lines_no_filter_returns_all(self):
        watcher = LogWatcher()
        watcher.ingest_line("x", source="a")
        watcher.ingest_line("y", source="b")
        assert len(watcher.all_lines()) == 2


class TestLogWatcherTagMatching:
    def test_expected_tag_found_in_line(self):
        watcher = LogWatcher(expected_tags=["[AI_CONFIG]"])
        watcher.ingest_line("[AI_CONFIG] model=gpt-4o selected")
        assert watcher.tag_found("[AI_CONFIG]") is True

    def test_tag_not_found_when_absent(self):
        watcher = LogWatcher(expected_tags=["[AI_CONFIG]"])
        watcher.ingest_line("something else")
        assert watcher.tag_found("[AI_CONFIG]") is False

    def test_get_matched_lines_returns_matching(self):
        watcher = LogWatcher(expected_tags=["[ERROR]"])
        watcher.ingest_line("[ERROR] something broke")
        watcher.ingest_line("normal log")
        matched = watcher.get_matched_lines("[ERROR]")
        assert len(matched) == 1
        assert "[ERROR]" in matched[0]

    def test_multiple_tags_tracked_independently(self):
        watcher = LogWatcher(expected_tags=["[STORY_GEN]", "[SCENE_GEN]", "[VIDEO_GEN]"])
        watcher.ingest_line("[STORY_GEN] story created")
        watcher.ingest_line("[VIDEO_GEN] video started")
        assert watcher.tag_found("[STORY_GEN]") is True
        assert watcher.tag_found("[SCENE_GEN]") is False
        assert watcher.tag_found("[VIDEO_GEN]") is True

    def test_tag_summary_counts(self):
        watcher = LogWatcher(expected_tags=["[AI_CONFIG]", "[ERROR]"])
        watcher.ingest_line("[AI_CONFIG] first")
        watcher.ingest_line("[AI_CONFIG] second")
        watcher.ingest_line("[ERROR] bad thing")
        summary = watcher.tag_summary()
        assert summary["[AI_CONFIG]"] == 2
        assert summary["[ERROR]"] == 1

    def test_line_with_multiple_tags_matches_each(self):
        watcher = LogWatcher(expected_tags=["[AI_CONFIG]", "[ERROR]"])
        watcher.ingest_line("[AI_CONFIG] [ERROR] dual tag line")
        assert watcher.tag_found("[AI_CONFIG]") is True
        assert watcher.tag_found("[ERROR]") is True


class TestLogWatcherSecretRedaction:
    def test_api_key_redacted(self):
        watcher = LogWatcher(redact_secrets=True)
        watcher.ingest_line("api_key=supersecret123456")
        lines = watcher.all_lines()
        assert "supersecret123456" not in lines[0]
        assert "[REDACTED]" in lines[0]

    def test_bearer_token_redacted(self):
        watcher = LogWatcher(redact_secrets=True)
        watcher.ingest_line("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxx")
        lines = watcher.all_lines()
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in lines[0]
        assert "[REDACTED]" in lines[0]

    def test_password_redacted(self):
        watcher = LogWatcher(redact_secrets=True)
        watcher.ingest_line("password: my$ecretP@ss")
        lines = watcher.all_lines()
        assert "my$ecretP@ss" not in lines[0]
        assert "[REDACTED]" in lines[0]

    def test_secret_field_redacted(self):
        watcher = LogWatcher(redact_secrets=True)
        watcher.ingest_line("secret=abc123xyz987")
        lines = watcher.all_lines()
        assert "abc123xyz987" not in lines[0]

    def test_no_redaction_when_disabled(self):
        watcher = LogWatcher(redact_secrets=False)
        watcher.ingest_line("api_key=should_stay_visible")
        lines = watcher.all_lines()
        assert "should_stay_visible" in lines[0]

    def test_redact_function_directly(self):
        line = "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.somedata"
        redacted = _redact(line)
        assert "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted
        assert "[REDACTED]" in redacted

    def test_normal_log_not_affected_by_redaction(self):
        watcher = LogWatcher(redact_secrets=True)
        watcher.ingest_line("[AI_CONFIG] model=gpt-4o route=openrouter")
        lines = watcher.all_lines()
        assert "[AI_CONFIG]" in lines[0]
        assert "gpt-4o" in lines[0]


class TestLogWatcherSearch:
    def test_search_finds_matching_lines(self):
        watcher = LogWatcher()
        watcher.ingest_line("database connected")
        watcher.ingest_line("user logged in")
        watcher.ingest_line("database query failed")
        results = watcher.search("database")
        assert len(results) == 2

    def test_search_case_insensitive_by_default(self):
        watcher = LogWatcher()
        watcher.ingest_line("DATABASE connected")
        results = watcher.search("database")
        assert len(results) == 1

    def test_search_case_sensitive_option(self):
        watcher = LogWatcher()
        watcher.ingest_line("DATABASE connected")
        watcher.ingest_line("database started")
        results = watcher.search("database", case_sensitive=True)
        assert len(results) == 1
        assert "database started" in results


class TestLogWatcherHasError:
    def test_has_error_when_error_tag_present(self):
        watcher = LogWatcher()
        watcher.ingest_line("[ERROR] something went wrong")
        assert watcher.has_error() is True

    def test_no_error_in_clean_logs(self):
        watcher = LogWatcher()
        watcher.ingest_line("[AI_CONFIG] model selected")
        watcher.ingest_line("[DB_WRITE] row inserted")
        assert watcher.has_error() is False


class TestLogWatcherClearAndCallbacks:
    def test_clear_removes_all_lines(self):
        watcher = LogWatcher(expected_tags=["[TAG]"])
        watcher.ingest_line("[TAG] something")
        watcher.clear()
        assert len(watcher.all_lines()) == 0
        assert watcher.tag_found("[TAG]") is False

    def test_callback_called_on_ingest(self):
        received = []
        watcher = LogWatcher()
        watcher.add_callback(lambda src, line: received.append((src, line)))
        watcher.ingest_line("test message", source="app")
        assert received == [("app", "test message")]

    def test_snapshot_limited_to_max_lines(self):
        watcher = LogWatcher()
        for i in range(600):
            watcher.ingest_line(f"line {i}")
        snap = watcher.snapshot(max_lines=500)
        assert len(snap) == 500


class TestLogWatcherProcessThread:
    def test_watch_process_stdout_reads_lines(self):
        watcher = LogWatcher(expected_tags=["[AI_CONFIG]", "[DB_WRITE]"])
        buf = io.StringIO("[AI_CONFIG] ready\n[DB_WRITE] stored\n")
        proc = MagicMock()
        proc.stdout = buf
        t = watcher.watch_process_stdout(proc, source="test")
        t.join(timeout=2)
        assert watcher.tag_found("[AI_CONFIG]") is True
        assert watcher.tag_found("[DB_WRITE]") is True
