"""
test_retest_orchestrator.py - Tests for targeted retest selection.
"""

from qa_ai.improvement.retest_orchestrator import RetestOrchestrator


class TestRetestOrchestrator:
    def test_selects_targeted_retests_for_affected_endpoint_and_fallback_smoke(self, artifact_store):
        orchestrator = RetestOrchestrator(artifact_store)

        result = orchestrator.run(
            fix_plan={
                "fixes": [
                    {
                        "fix_id": "FIX-001",
                        "affected_files": ["qa_ai/audit/api_audit.py"],
                        "affected_apis": ["GET /users"],
                        "recommended_tests": ["TEST-SEC"],
                    }
                ]
            },
            test_plan={
                "test_suites": {
                    "smoke": [{"id": "TEST-SMOKE", "title": "App loads", "type": "smoke"}],
                    "security": [{"id": "TEST-SEC", "title": "GET /users requires auth", "type": "security"}],
                    "functional": [{"id": "TEST-OTHER", "title": "POST /orders works", "type": "functional"}],
                }
            },
        )

        selected_ids = [test["id"] for test in result["selected_tests"]]
        assert selected_ids == ["TEST-SEC", "TEST-SMOKE"]
        assert result["summary"]["targeted_tests"] == 2
        assert artifact_store.artifact_exists("retest_results")

    def test_does_not_run_commands_when_execute_false(self, artifact_store):
        orchestrator = RetestOrchestrator(artifact_store)
        calls = {"count": 0}

        def fake_runner(command):
            calls["count"] += 1
            return {"status": "passed", "returncode": 0}

        result = orchestrator.run(
            fix_plan={"fixes": [{"recommended_tests": ["TEST-CMD"]}]},
            test_plan={"test_suites": {"smoke": [{"id": "TEST-CMD", "type": "smoke", "command": "echo run"}]}},
            execute=False,
            command_runner=fake_runner,
        )

        assert calls["count"] == 0
        assert result["results"][0]["status"] == "selected_not_run"

    def test_runs_command_runner_only_when_execute_true(self, artifact_store):
        orchestrator = RetestOrchestrator(artifact_store)
        calls = {"count": 0}

        def fake_runner(command):
            calls["count"] += 1
            return {"status": "passed", "returncode": 0}

        result = orchestrator.run(
            fix_plan={"fixes": [{"recommended_tests": ["TEST-CMD"]}]},
            test_plan={"test_suites": {"smoke": [{"id": "TEST-CMD", "type": "smoke", "command": "echo run"}]}},
            execute=True,
            command_runner=fake_runner,
        )

        assert calls["count"] == 1
        assert result["results"][0]["status"] == "passed"

    def test_handles_malformed_inputs_as_empty(self, artifact_store):
        orchestrator = RetestOrchestrator(artifact_store)

        result = orchestrator.run(
            fix_plan=["bad"],  # type: ignore[arg-type]
            test_plan="bad",  # type: ignore[arg-type]
        )

        assert result["summary"]["targeted_tests"] == 0
        assert result["results"] == []
