"""
test_mobile_network_controller.py - Tests for safe offline/reconnect simulation planning.
"""

from qa_ai.mobile_runtime.mobile_network_controller import MobileNetworkController


class TestMobileNetworkController:
    def test_offline_reconnect_simulation_plan(self, artifact_store):
        report = MobileNetworkController(artifact_store).run(
            conditions=["offline_mode", "reconnect"],
            apply_real_controls=True,
            explicit_permission=False,
        )
        assert report["simulation_mode"] is True
        assert report["summary"]["blocked_count"] == 2
        assert artifact_store.artifact_exists("mobile_network_report")
