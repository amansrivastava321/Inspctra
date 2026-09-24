"""
test_multi_session_orchestrator.py - Tests for actor-session orchestration.
"""

from qa_ai.distributed_runtime.multi_session_orchestrator import MultiSessionOrchestrator


class TestMultiSessionOrchestrator:
    def test_actor_sessions_are_isolated_in_dry_run(self, artifact_store):
        orchestrator = MultiSessionOrchestrator(artifact_store)
        actor_registry = {
            "actors": [
                {"actor_id": "a1", "role": "cashier"},
                {"actor_id": "a2", "role": "manager"},
                {"actor_id": "a3", "role": "background_sync"},
            ]
        }
        report = orchestrator.run(actor_registry=actor_registry, mode="sequential", dry_run=True)

        assert report["mode"] == "sequential"
        assert len(report["actor_sessions"]) == 3
        assert all(item["isolated"] for item in report["actor_sessions"])
        assert artifact_store.artifact_exists("multi_session_report")

    def test_parallel_mode_plan_generated_safely(self, artifact_store):
        orchestrator = MultiSessionOrchestrator(artifact_store)
        actor_registry = {"actors": [{"actor_id": "a1", "role": "waiter"}]}
        report = orchestrator.run(actor_registry=actor_registry, mode="parallel", dry_run=True)
        assert report["mode"] == "parallel"
        assert report["summary"]["dry_run"] is True
