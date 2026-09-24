"""
test_code_quality_audit.py - Tests for the Code Quality audit agent.
Validates large file/function/class detection, TODO/FIXME/HACK detection,
weak error handling, missing logging, and duplication detection.
"""

import pytest

from qa_ai.audit.code_quality_audit import CodeQualityAuditAgent
from qa_ai.schemas.audit_result_schema import AuditCheckStatus


class TestCodeQualityAuditAgent:
    def test_detects_large_file(self, artifact_store):
        content = "\n".join([f"x_{i} = {i}" for i in range(600)])
        file_contents = {"big.py": content}

        agent = CodeQualityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        size_checks = [c for c in result.checks if c.category == "file_size"]
        assert len(size_checks) > 0
        assert "600" in size_checks[0].description

    def test_ignores_small_file(self, artifact_store):
        content = "\n".join([f"x_{i} = {i}" for i in range(10)])
        file_contents = {"small.py": content}

        agent = CodeQualityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        size_checks = [c for c in result.checks if c.category == "file_size"]
        assert len(size_checks) == 0

    def test_detects_large_function(self, artifact_store):
        lines = ["def big_function():"]
        lines.extend(["    x = 1"] * 100)
        content = "\n".join(lines)
        file_contents = {"module.py": content}

        agent = CodeQualityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        func_checks = [c for c in result.checks if c.category == "function_size"]
        assert len(func_checks) > 0

    def test_detects_large_class(self, artifact_store):
        lines = ["class BigClass:"]
        lines.extend(["    def method(self): pass"] * 350)
        content = "\n".join(lines)
        file_contents = {"models.py": content}

        agent = CodeQualityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        class_checks = [c for c in result.checks if c.category == "class_size"]
        assert len(class_checks) > 0

    def test_detects_todo_comments(self, artifact_store):
        file_contents = {
            "app.py": "# TODO: fix this later\n# FIXME: broken\n# HACK: workaround",
        }
        agent = CodeQualityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        debt_checks = [c for c in result.checks if c.category == "technical_debt"]
        assert len(debt_checks) > 0
        assert "3" in debt_checks[0].description

    def test_detects_bare_except(self, artifact_store):
        file_contents = {
            "handler.py": "try:\n    x = 1\nexcept:\n    pass",
        }
        agent = CodeQualityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        error_checks = [c for c in result.checks if c.category == "error_handling"]
        assert len(error_checks) > 0

    def test_detects_empty_catch(self, artifact_store):
        file_contents = {
            "handler.py": "try:\n    x = 1\nexcept ValueError:\n    pass",
        }
        agent = CodeQualityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        error_checks = [c for c in result.checks if c.category == "error_handling"]
        assert len(error_checks) > 0

    def test_detects_missing_logging(self, artifact_store):
        file_contents = {
            "handler.py": "try:\n    x = 1\nexcept:\n    pass",
        }
        agent = CodeQualityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        log_checks = [c for c in result.checks if c.category == "observability"]
        assert len(log_checks) > 0

    def test_detects_duplicated_lines(self, artifact_store):
        line = "result = some_very_long_function_name_with_many_parameters(a, b, c, d, e, f)"
        content = f"{line}\nx = 1\n{line}\ny = 2\n{line}"
        file_contents = {"dup.py": content}

        agent = CodeQualityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        dup_checks = [c for c in result.checks if c.category == "duplication"]
        assert len(dup_checks) > 0

    def test_result_has_metadata(self, artifact_store, sample_app_map):
        agent = CodeQualityAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        assert result.metadata.audit_type == "code_quality_audit"
        assert result.metadata.generated_by == "CodeQualityAuditAgent"

    def test_artifacts_written(self, artifact_store, sample_app_map):
        agent = CodeQualityAuditAgent(artifact_store)
        agent.run(app_map=sample_app_map)

        assert artifact_store.artifact_exists("code_quality_results")

    def test_pass_rate_bounds(self, artifact_store, sample_app_map):
        agent = CodeQualityAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        assert 0.0 <= result.pass_rate <= 1.0

    def test_empty_input(self, artifact_store):
        agent = CodeQualityAuditAgent(artifact_store)
        result = agent.run(file_contents={})

        assert result.total_checks == 0
        assert result.metadata.audit_type == "code_quality_audit"

    def test_summary_has_expected_keys(self, artifact_store, sample_app_map):
        agent = CodeQualityAuditAgent(artifact_store)
        result = agent.run(app_map=sample_app_map)

        assert "total_checks" in result.summary
        assert "files_audited" in result.summary
        assert "by_category" in result.summary

    def test_multiple_issues_in_one_file(self, artifact_store):
        lines = ["def big_function():"]
        lines.extend(["    # TODO: fix this\n    x = 1"] * 100)
        content = "\n".join(lines)
        file_contents = {"messy.py": content}

        agent = CodeQualityAuditAgent(artifact_store)
        result = agent.run(file_contents=file_contents)

        categories = {c.category for c in result.checks}
        assert "function_size" in categories
        assert "technical_debt" in categories
