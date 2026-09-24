"""
distributed_runtime_runner.py - Orchestrates distributed runtime simulation phases.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from qa_ai.distributed_runtime.actor_engine import ActorEngine
from qa_ai.distributed_runtime.chaos_engine import ChaosEngine
from qa_ai.distributed_runtime.concurrency_simulator import ConcurrencySimulator
from qa_ai.distributed_runtime.distributed_evidence_collector import DistributedEvidenceCollector
from qa_ai.distributed_runtime.multi_session_orchestrator import MultiSessionOrchestrator
from qa_ai.distributed_runtime.network_condition_engine import NetworkConditionEngine
from qa_ai.distributed_runtime.offline_runtime import OfflineRuntime
from qa_ai.distributed_runtime.sync_conflict_engine import SyncConflictEngine
from qa_ai.live_execution.network_capture import NetworkCapture
from qa_ai.live_execution.replay_engine import ReplayEngine
from qa_ai.live_execution.trace_recorder import TraceRecorder
from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.runtime_intelligence.runtime_risk_engine import RuntimeRiskEngine
from qa_ai.runtime_intelligence.scenario_engine import ScenarioEngine


class DistributedRuntimeRunner:
    """Runs multi-actor, concurrency, offline/sync, and chaos phases with artifact outputs."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        app_path: str,
        actors: Optional[List[str]] = None,
        dry_run: bool = True,
        mode: str = "parallel",
    ) -> Dict[str, Any]:
        actor_engine = ActorEngine(self.store)
        session_orchestrator = MultiSessionOrchestrator(self.store)
        concurrency = ConcurrencySimulator(self.store)
        network = NetworkConditionEngine(self.store)
        offline = OfflineRuntime(self.store)
        sync_conflicts = SyncConflictEngine(self.store)
        chaos = ChaosEngine(self.store)
        evidence = DistributedEvidenceCollector(self.store)

        actor_registry = actor_engine.create_actors(roles=actors)
        synthetic_actions = self._seed_actions(actor_registry)
        for actor_id, actions in synthetic_actions.items():
            for action in actions:
                actor_engine.queue_action(actor_id, action)
        action_timeline = actor_engine.execute_queued_actions()
        actor_actions = self._timeline_to_actions(action_timeline)

        multi_session = session_orchestrator.run(
            actor_registry=actor_registry,
            mode=mode,
            dry_run=dry_run,
            shared_state={"app_path": str(Path(app_path).resolve())},
        )

        concurrency_report = concurrency.run(actor_actions=actor_actions)
        network_report = network.run(dry_run=dry_run)
        offline_report = offline.run(offline_actions=actor_actions)
        sync_report = sync_conflicts.run(edits=actor_actions)
        chaos_report = chaos.run(dry_run=dry_run, explicit_permission=False)

        # Reuse existing runtime capture/analyze patterns.
        trace_recorder = TraceRecorder(self.store)
        trace_recorder.start()
        for action in actor_actions:
            trace_recorder.record_step(
                action=action.get("action_type", "action"),
                target=action.get("entity_id", ""),
                status="success",
            )
        execution_trace = trace_recorder.save_trace()

        network_capture = NetworkCapture(self.store)
        network_capture.start()
        for _action in actor_actions[:3]:
            network_capture.capture(method="POST", url="/sync", status_code=200, duration_ms=20.0)
        network_trace = network_capture.save_trace()

        scenario_results = ScenarioEngine(self.store).run(
            scenario_names=["offline_sync_flow", "duplicate_submission"],
            base_url=None,
        )
        replay_analysis = ReplayEngine(self.store).run(current_trace=execution_trace)
        runtime_risk = RuntimeRiskEngine(self.store).run(
            static_risk_report={"findings": []},
            verified_findings={"verified_findings": []},
            exploit_results={"exploit_results": []},
            behavioral_analysis={"anomalies": []},
        )
        evidence_graph = evidence.run()

        phases = {
            "actors": actor_registry.get("summary", {}),
            "sessions": multi_session.get("summary", {}),
            "concurrency": concurrency_report.get("summary", {}),
            "network": network_report.get("summary", {}),
            "offline": offline_report.get("summary", {}),
            "sync_conflicts": sync_report.get("summary", {}),
            "chaos": chaos_report.get("summary", {}),
            "evidence": evidence_graph.get("summary", {}),
            "scenario_execution": scenario_results.get("summary", {}),
            "replay_analysis": replay_analysis.get("comparison", {}),
            "runtime_risk": {
                "risk_level": runtime_risk.get("risk_level"),
                "overall_adjusted_risk_score": runtime_risk.get("overall_adjusted_risk_score"),
            },
            "trace": execution_trace.get("summary", {}),
            "network_trace": network_trace.get("summary", {}),
        }

        report = {
            "app_path": str(Path(app_path).resolve()),
            "dry_run": dry_run,
            "actors": actors or [],
            "phases": phases,
            "summary": {
                "distributed_mode": mode,
                "actor_count": actor_registry.get("summary", {}).get("total_actors", 0),
                "anomaly_count": concurrency_report.get("summary", {}).get("ordering_anomalies", 0)
                + concurrency_report.get("summary", {}).get("duplicate_entities", 0)
                + concurrency_report.get("summary", {}).get("state_divergence", 0)
                + sync_report.get("summary", {}).get("anomaly_count", 0),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("distributed_runtime_report", report, agent="DistributedRuntimeRunner")
        return report

    def _seed_actions(self, actor_registry: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        actions: Dict[str, List[Dict[str, Any]]] = {}
        actors = actor_registry.get("actors", []) if isinstance(actor_registry, dict) else []
        seq = 1
        for actor in actors:
            if not isinstance(actor, dict):
                continue
            actor_id = str(actor.get("actor_id", ""))
            role = str(actor.get("role", ""))
            if not actor_id:
                continue
            actions[actor_id] = [
                {
                    "action_id": f"{actor_id}-a1",
                    "actor_id": actor_id,
                    "role": role,
                    "action_type": "submit",
                    "permission": "create_order" if role in {"cashier", "waiter", "customer"} else "view_orders",
                    "entity_id": "order-1",
                    "sequence": seq,
                    "final_state": "submitted",
                    "local_version": 1,
                    "remote_version": 1 if role != "background_sync" else 2,
                },
                {
                    "action_id": f"{actor_id}-a2",
                    "actor_id": actor_id,
                    "role": role,
                    "action_type": "edit",
                    "permission": "edit_menu" if role in {"manager", "admin"} else "view_menu",
                    "entity_id": "menu-1",
                    "sequence": seq + 1,
                    "final_state": "edited_by_" + role,
                    "local_version": 1,
                    "remote_version": 2 if role == "background_sync" else 1,
                    "local_id": f"loc-{role}",
                    "remote_id": "rem-1",
                    "tombstone_propagated": True,
                },
            ]
            seq += 2
        return actions

    def _timeline_to_actions(self, timeline: Dict[str, Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        entries = timeline.get("timeline", []) if isinstance(timeline, dict) else []
        for row in entries:
            if not isinstance(row, dict):
                continue
            action = row.get("action", {})
            if not isinstance(action, dict):
                continue
            out.append(action)
        return out
