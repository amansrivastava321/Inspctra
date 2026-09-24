"""
test_actor_engine.py - Tests for actor registry and permission-bound queues.
"""

from qa_ai.distributed_runtime.actor_engine import ActorEngine


class TestActorEngine:
    def test_actors_created_with_roles_permissions_and_state(self, artifact_store):
        engine = ActorEngine(artifact_store)
        registry = engine.create_actors(["cashier", "manager", "background_sync"])
        assert registry["summary"]["total_actors"] == 3
        assert artifact_store.artifact_exists("actor_registry")

        actors = registry["actors"]
        cashier = next(item for item in actors if item["role"] == "cashier")
        manager = next(item for item in actors if item["role"] == "manager")
        assert cashier["state"] == {}
        assert manager["state"] == {}
        assert "create_order" in cashier["permissions"]
        assert "approve_discount" in manager["permissions"]

    def test_permission_boundary_actions_blocked_unless_explicit_test(self, artifact_store):
        engine = ActorEngine(artifact_store)
        registry = engine.create_actors(["anonymous_user"])
        actor_id = registry["actors"][0]["actor_id"]

        blocked = engine.queue_action(
            actor_id,
            {"permission": "manage_system", "action_type": "admin_change"},
        )
        assert blocked["accepted"] is False
        assert blocked["reason"] == "permission_denied"

        allowed_boundary = engine.queue_action(
            actor_id,
            {
                "permission": "manage_system",
                "action_type": "admin_change",
                "permission_boundary_test": True,
            },
        )
        assert allowed_boundary["accepted"] is True
