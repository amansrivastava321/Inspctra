"""
test_artifact_contracts.py - Contract checks across artifact-driven subsystems.
"""

import json

from qa_ai.improvement.improvement_loop import ImprovementLoop
from qa_ai.live_execution.trace_recorder import TraceRecorder
from qa_ai.live_execution.network_capture import NetworkCapture
from qa_ai.live_execution.replay_engine import ReplayEngine
from qa_ai.orchestration.workflow_engine import WorkflowEngine
from qa_ai.runtime_intelligence.evidence_correlator import RuntimeEvidenceCorrelator


class TestArtifactContracts:
    def test_contract_metadata_persisted_for_major_artifacts(self, artifact_store):
        loop = ImprovementLoop(artifact_store)
        loop.run(
            findings={"findings": []},
            root_causes={"root_causes": []},
            risk_report={"overall_risk_score": 0, "risk_level": "low", "findings": []},
            test_plan={"test_suites": {"smoke": [{"id": "S1", "title": "Smoke", "type": "smoke"}]}},
            before_audit={"findings": [], "execution_results": {"failed": 0}},
            after_audit={"findings": [], "execution_results": {"failed": 0}},
        )

        recorder = TraceRecorder(artifact_store)
        recorder.start()
        recorder.record_step(action="navigate", target="/")
        recorder.save_trace()

        capture = NetworkCapture(artifact_store)
        capture.start()
        capture.capture(method="GET", url="/health", status_code=200, duration_ms=10.0)
        capture.save_trace()

        ReplayEngine(artifact_store).run(current_trace={"events": []})
        RuntimeEvidenceCorrelator(artifact_store).run(verified_findings={}, execution_results={}, app_map={})

        artifact_names = [
            "software_health_score",
            "improvement_backlog",
            "fix_plan",
            "remediation_plan",
            "retest_results",
            "quality_trend",
            "regression_guard_report",
            "learning_registry",
            "change_impact_analysis",
            "execution_trace",
            "network_trace",
            "replay_analysis",
            "evidence_graph",
        ]

        for artifact_name in artifact_names:
            artifact = artifact_store.load_artifact(artifact_name)
            assert isinstance(artifact, dict)
            assert "artifact_metadata" in artifact
            assert artifact["artifact_metadata"]["schema_version"] == "1.0"
            assert artifact["artifact_metadata"]["artifact_type"] == artifact_name
            assert "created_at" in artifact

    def test_workflow_safe_consumption_when_artifact_payload_is_malformed(self, artifact_store):
        malformed_path = artifact_store.base_dir / "fix_plan.json"
        malformed_path.write_text(json.dumps(["bad", "payload"]), encoding="utf-8")

        engine = WorkflowEngine(artifact_store=artifact_store)
        loaded = engine._load_validated_artifact("fix_plan", {})  # noqa: SLF001 - intentional safety-path test

        assert isinstance(loaded, dict)
        assert loaded["fixes"] == []
        assert loaded["metadata"]["validation_error"] == "artifact_payload_not_dict"
