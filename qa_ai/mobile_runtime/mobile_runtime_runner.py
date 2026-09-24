"""
mobile_runtime_runner.py - Orchestrate mobile runtime planning and evidence flow.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from qa_ai.distributed_runtime.actor_engine import ActorEngine
from qa_ai.distributed_runtime.distributed_runtime_runner import DistributedRuntimeRunner
from qa_ai.live_execution.replay_engine import ReplayEngine
from qa_ai.mobile_runtime.android_emulator_manager import AndroidEmulatorManager
from qa_ai.mobile_runtime.appium_bridge import AppiumBridge
from qa_ai.mobile_runtime.device_log_collector import DeviceLogCollector
from qa_ai.mobile_runtime.device_registry import DeviceRegistry
from qa_ai.mobile_runtime.device_session_manager import DeviceSessionManager
from qa_ai.mobile_runtime.flutter_runner import FlutterRunner
from qa_ai.mobile_runtime.ios_simulator_manager import IOSSimulatorManager
from qa_ai.mobile_runtime.maestro_bridge import MaestroBridge
from qa_ai.mobile_runtime.mobile_evidence_collector import MobileEvidenceCollector
from qa_ai.mobile_runtime.mobile_network_controller import MobileNetworkController
from qa_ai.mobile_runtime.mobile_runtime_monitor import MobileRuntimeMonitor
from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.runtime_intelligence.runtime_risk_engine import RuntimeRiskEngine
from qa_ai.runtime_intelligence.scenario_engine import ScenarioEngine
from qa_ai.runtime_lab.environment_bootstrapper import EnvironmentBootstrapper


class MobileRuntimeRunner:
    """Run mobile runtime orchestration in safe planning mode by default."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        app_path: str,
        dry_run: bool = True,
        distributed: bool = False,
        actors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        app = str(Path(app_path).expanduser().resolve())

        registry = DeviceRegistry(self.store).run()
        android = AndroidEmulatorManager(self.store).run(dry_run=dry_run)
        ios = IOSSimulatorManager(self.store).run(dry_run=dry_run)
        flutter = FlutterRunner(self.store).run(app_path=app, dry_run=dry_run, allow_auto_install=False)
        appium = AppiumBridge(self.store).run(app_path=app, dry_run=dry_run)
        maestro = MaestroBridge(self.store).run(app_path=app, dry_run=dry_run)

        bootstrap = EnvironmentBootstrapper(self.store).prepare(
            app_path=app,
            dry_run=True,
            allow_auto_install=False,
            app_type="flutter_placeholder",
        )

        if distributed:
            distributed_report = DistributedRuntimeRunner(self.store).run(
                app_path=app,
                actors=actors,
                dry_run=True,
                mode="parallel",
            )
            actor_registry = self.store.load_artifact("actor_registry")
        else:
            actor_registry = ActorEngine(self.store).create_actors(roles=actors or ["customer", "background_sync"])
            distributed_report = {}

        sessions = DeviceSessionManager(self.store).run(
            actor_registry=actor_registry if isinstance(actor_registry, dict) else None,
            device_registry=registry,
            distributed=distributed,
            shared_state={"app_path": app},
        )
        network = MobileNetworkController(self.store).run(
            conditions=["offline_mode", "reconnect", "intermittent_connectivity"],
            apply_real_controls=False,
            explicit_permission=False,
        )
        logs = DeviceLogCollector(self.store).run(app_path=app, dry_run=dry_run, execute=False)
        monitor = MobileRuntimeMonitor(self.store).run(
            device_registry=registry,
            android_report=android,
            ios_report=ios,
            logs_index=logs,
            mobile_network_report=network,
        )

        scenario = ScenarioEngine(self.store).run(
            scenario_names=["offline_sync_flow", "duplicate_submission"],
            base_url=None,
        )
        replay = ReplayEngine(self.store).run(current_trace={"events": []})
        runtime_risk = RuntimeRiskEngine(self.store).run(
            static_risk_report={"findings": []},
            verified_findings={"verified_findings": []},
            exploit_results={"exploit_results": []},
            behavioral_analysis={"anomalies": []},
        )
        evidence = MobileEvidenceCollector(self.store).run()

        phases = {
            "device_registry": registry.get("summary", {}),
            "android_emulator": android.get("summary", {}),
            "ios_simulator": ios.get("summary", {}),
            "flutter_execution_plan": flutter.get("summary", {}),
            "appium_plan": appium.get("summary", {}),
            "maestro_plan": maestro.get("summary", {}),
            "bootstrap_plan": {"environment_ready": bootstrap.get("environment_ready", False)},
            "device_sessions": sessions.get("summary", {}),
            "mobile_network": network.get("summary", {}),
            "mobile_runtime_monitor": monitor.get("summary", {}),
            "mobile_logs_index": logs.get("summary", {}),
            "mobile_evidence_graph": evidence.get("summary", {}),
            "scenario_execution": scenario.get("summary", {}),
            "replay_analysis": replay.get("comparison", {}),
            "runtime_risk": {"risk_level": runtime_risk.get("risk_level")},
            "distributed_runtime": distributed_report.get("summary", {}) if isinstance(distributed_report, dict) else {},
        }
        report = {
            "app_path": app,
            "dry_run": bool(dry_run),
            "distributed": bool(distributed),
            "phases": phases,
            "summary": {
                "device_count": registry.get("summary", {}).get("android_device_count", 0)
                + registry.get("summary", {}).get("ios_simulator_count", 0),
                "session_count": sessions.get("summary", {}).get("session_count", 0),
                "critical_mobile_signals": monitor.get("summary", {}).get("critical_signals", 0),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        self.store.save_artifact("mobile_runtime_report", report, agent="MobileRuntimeRunner")
        return report
