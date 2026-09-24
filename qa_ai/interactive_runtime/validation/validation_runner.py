"""
validation_runner.py - Runs ValidationTarget entries through dry-run and live paths.

Security rules enforced:
- Never launches app in dry-run mode.
- Asks before real launch (unless allow_real_launch=="always").
- Blocks if platform doesn't match expected_platform.
- No shell=True.
- No destructive actions without approval.
- Secrets are redacted before logging.
"""
from __future__ import annotations

import logging
import platform
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from qa_ai.interactive_runtime.validation.validation_target import ValidationTarget
from qa_ai.interactive_runtime.validation.validation_result import (
    TargetValidationStatus,
    ValidationResult,
)

logger = logging.getLogger(__name__)


class ValidationRunner:
    """
    Runs one or more ValidationTarget entries.

    Dry-run: loads config + driver capabilities. Never launches app.
    Live: gates on platform match and explicit permission.
    """

    def __init__(
        self,
        output_dir: str = "artifacts",
        interactive: bool = True,
    ):
        self._out = Path(output_dir)
        self._out.mkdir(parents=True, exist_ok=True)
        self._interactive = interactive

    # ── public ────────────────────────────────────────────────────────────────

    def run_dry(self, target: ValidationTarget) -> ValidationResult:
        """Load config and inspect driver capabilities. No app launch."""
        t0 = time.monotonic()
        result = ValidationResult(
            target_id=target.target_id,
            app_name=target.app_name,
            app_type=target.app_type,
            platform=platform.system().lower(),
        )

        # Platform gate
        if not self._platform_matches(target):
            result.status = TargetValidationStatus.BLOCKED_PLATFORM
            result.notes = (
                f"Target expects platform '{target.expected_platform}' "
                f"but running on '{platform.system().lower()}'."
            )
            result.duration_seconds = time.monotonic() - t0
            return result

        # Load config
        try:
            cfg = self._load_config(target.config_path)
        except Exception as exc:
            result.status = TargetValidationStatus.ERROR
            result.error = f"Config load failed: {exc}"
            result.duration_seconds = time.monotonic() - t0
            return result

        # Inspect driver
        try:
            caps = self._inspect_driver(cfg)
            result.driver_backend = caps.get("backend", "")
            result.driver_status = caps.get("status", "")
            result.dry_run_caps = caps
            result.capability_gaps = caps.get("capability_gaps", [])
            result.setup_instructions = caps.get("setup_instructions", [])
            result.missing_deps = caps.get("missing_dependencies", [])
        except Exception as exc:
            result.status = TargetValidationStatus.ERROR
            result.error = f"Driver inspection failed: {exc}"
            result.duration_seconds = time.monotonic() - t0
            return result

        # Check expected capabilities
        missing_caps = self._check_expected_capabilities(target, caps)
        if missing_caps:
            result.capability_gaps.extend(missing_caps)
            result.status = TargetValidationStatus.BLOCKED_CAPABILITY
            result.notes = f"Missing expected capabilities: {missing_caps}"
            result.duration_seconds = time.monotonic() - t0
            return result

        # Connector dry-run: check connector requirements without launching
        connector_dry_results = self._run_connectors_dry(cfg, target)
        if connector_dry_results:
            result.dry_run_caps["connector_dry_results"] = connector_dry_results

        result.status = TargetValidationStatus.DRY_RUN_ONLY
        result.duration_seconds = time.monotonic() - t0
        return result

    def run_live(
        self,
        target: ValidationTarget,
        live_guided: bool = False,
        ai_guided: bool = False,
        max_actions: Optional[int] = None,
    ) -> ValidationResult:
        """
        Run a live interactive test for the target.

        Security:
        - Checks platform match first.
        - Asks for permission if allow_real_launch == "ask" and interactive mode.
        - Never uses shell=True.
        """
        t0 = time.monotonic()
        result = ValidationResult(
            target_id=target.target_id,
            app_name=target.app_name,
            app_type=target.app_type,
            platform=platform.system().lower(),
        )

        # Platform gate
        if not self._platform_matches(target):
            result.status = TargetValidationStatus.BLOCKED_PLATFORM
            result.notes = (
                f"Platform mismatch: expected '{target.expected_platform}', "
                f"got '{platform.system().lower()}'."
            )
            result.duration_seconds = time.monotonic() - t0
            return result

        # Permission gate for real launch
        if not self._approve_launch(target):
            result.status = TargetValidationStatus.BLOCKED_PERMISSION
            result.notes = "Real launch denied by user or policy."
            result.duration_seconds = time.monotonic() - t0
            return result

        # Load config
        try:
            cfg = self._load_config(target.config_path)
        except Exception as exc:
            result.status = TargetValidationStatus.ERROR
            result.error = f"Config load failed: {exc}"
            result.duration_seconds = time.monotonic() - t0
            return result

        # Apply overrides
        if max_actions is not None:
            cfg.max_actions = max_actions
        if target.allow_database_checks is False:
            cfg.database_verification_enabled = False

        # Run via executor
        try:
            live_result = self._execute_live(
                cfg, target, live_guided=live_guided, ai_guided=ai_guided
            )
            result.live_verdict = live_result.get("verdict")
            result.live_pass_count = live_result.get("pass_count", 0)
            result.live_fail_count = live_result.get("fail_count", 0)
            result.live_unclear_count = live_result.get("unclear_count", 0)
            result.live_blocked_count = live_result.get("blocked_count", 0)
            result.coverage_pct = live_result.get("coverage_pct", 0.0)
            result.capability_gaps = live_result.get("capability_gaps", [])
            result.artifacts = live_result.get("artifacts", [])

            verdict = result.live_verdict or "unclear"
            if verdict == "passed":
                result.status = TargetValidationStatus.LIVE_PASSED
            elif verdict == "failed":
                result.status = TargetValidationStatus.LIVE_FAILED
            elif verdict in ("blocked",):
                result.status = TargetValidationStatus.LIVE_BLOCKED
            else:
                result.status = TargetValidationStatus.LIVE_UNCLEAR

        except Exception as exc:
            result.status = TargetValidationStatus.ERROR
            result.error = str(exc)

        result.duration_seconds = time.monotonic() - t0
        return result

    def run_pack_dry(self, targets: List[ValidationTarget]) -> List[ValidationResult]:
        return [self.run_dry(t) for t in targets]

    # ── internals ─────────────────────────────────────────────────────────────

    def _platform_matches(self, target: ValidationTarget) -> bool:
        if target.expected_platform is None:
            return True
        return platform.system().lower() == target.expected_platform.lower()

    def _approve_launch(self, target: ValidationTarget) -> bool:
        if target.allow_real_launch == "always":
            return True
        if target.allow_real_launch == "never":
            return False
        # "ask"
        if not self._interactive:
            logger.info(
                "Non-interactive mode: skipping live launch for '%s'", target.target_id
            )
            return False
        try:
            answer = input(
                f"\n[PERMISSION] Launch '{target.app_name}' ({target.app_type})? [y/N] "
            ).strip().lower()
            return answer in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    def _load_config(self, config_path: str) -> Any:
        from qa_ai.interactive_runtime.config_loader import load_config
        return load_config(config_path)

    def _inspect_driver(self, cfg: Any) -> Dict[str, Any]:
        from qa_ai.interactive_runtime.drivers.driver_factory import DriverFactory
        from qa_ai.interactive_runtime.drivers.capability_detector import CapabilityDetector

        driver = DriverFactory.create(cfg.app_type.value if hasattr(cfg.app_type, "value") else str(cfg.app_type), cfg)
        caps = driver.capabilities()
        data = caps.model_dump()
        data["platform"] = CapabilityDetector.current_platform()

        # collect gaps from screen observer
        from qa_ai.interactive_runtime.screen_observer import ScreenObserver
        obs = ScreenObserver(cfg.app_type)
        data["capability_gaps"] = [str(g) for g in obs.capability_gaps]
        return data

    def _check_expected_capabilities(
        self, target: ValidationTarget, caps: Dict[str, Any]
    ) -> List[str]:
        missing = []
        for cap in target.expected_capabilities:
            if not caps.get(cap, False):
                missing.append(cap)
        return missing

    def _run_connectors_dry(
        self, cfg: Any, target: "ValidationTarget"
    ) -> List[Dict[str, Any]]:
        """Run connector dry-run and return summary list. Never raises."""
        connectors_cfg = getattr(cfg, "runtime_connectors", None)
        if connectors_cfg is None:
            return []
        try:
            from qa_ai.interactive_runtime.connectors import RuntimeConnectorManager
            from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorsConfig
            if not isinstance(connectors_cfg, RuntimeConnectorsConfig):
                if isinstance(connectors_cfg, dict):
                    connectors_cfg = RuntimeConnectorsConfig(**connectors_cfg)
                else:
                    return []
            manager = RuntimeConnectorManager(
                output_dir=str(self._out / target.target_id),
                interactive=self._interactive,
            )
            ctx = manager.run(connectors_cfg, dry_run=True)
            return [
                {
                    "connector_id": r.connector_id,
                    "type": r.connector_type.value,
                    "status": r.status.value,
                    "gaps": [g.gap_id for g in r.capability_gaps],
                }
                for r in ctx.connector_results.values()
            ]
        except Exception as exc:
            logger.debug("connector dry-run error: %s", exc)
            return []

    def _execute_live(
        self,
        cfg: Any,
        target: ValidationTarget,
        live_guided: bool = False,
        ai_guided: bool = False,
    ) -> Dict[str, Any]:
        """
        Run live interactive test inline (no subprocess).
        Returns summary dict with verdict + counts.
        """
        import uuid as _uuid
        from qa_ai.interactive_runtime.permission_gate import PermissionGate
        from qa_ai.interactive_runtime.app_launcher import AppLauncher
        from qa_ai.interactive_runtime.runtime_session import RuntimeSession
        from qa_ai.interactive_runtime.screen_observer import ScreenObserver
        from qa_ai.interactive_runtime.ui_action_planner import UIActionPlanner
        from qa_ai.interactive_runtime.ui_controller import UIController
        from qa_ai.interactive_runtime.human_approval_gate import HumanApprovalGate
        from qa_ai.interactive_runtime.result_verifier import ResultVerifier
        from qa_ai.interactive_runtime.runtime_evidence_builder import RuntimeEvidenceBuilder
        from qa_ai.interactive_runtime.function_coverage_tracker import FunctionCoverageTracker
        from qa_ai.interactive_runtime.screenshot_collector import ScreenshotCollector
        from qa_ai.interactive_runtime.log_watcher import LogWatcher
        from qa_ai.interactive_runtime.interaction_executor import InteractionExecutor
        from qa_ai.interactive_runtime.interactive_reporter import InteractiveReporter
        from qa_ai.interactive_runtime.schemas import RiskLevel, PermissionDecision

        out_dir = str(self._out / target.target_id)
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        session_id = str(_uuid.uuid4())[:12]

        # ── Live Runtime Connectors ──────────────────────────────────────────
        runtime_context = None
        connector_manager = None
        connectors_cfg = getattr(cfg, "runtime_connectors", None)
        if connectors_cfg is not None:
            try:
                from qa_ai.interactive_runtime.connectors import RuntimeConnectorManager
                from qa_ai.interactive_runtime.connectors.connector_models import RuntimeConnectorsConfig
                if not isinstance(connectors_cfg, RuntimeConnectorsConfig):
                    connectors_cfg = RuntimeConnectorsConfig(**connectors_cfg) if isinstance(connectors_cfg, dict) else None
                if connectors_cfg:
                    connector_manager = RuntimeConnectorManager(
                        output_dir=out_dir, interactive=self._interactive
                    )
                    runtime_context = connector_manager.run(connectors_cfg, dry_run=False)
                    if not runtime_context.connectors_ready:
                        blocked = runtime_context.blocked_connector_ids
                        return {
                            "verdict": "blocked",
                            "pass_count": 0, "fail_count": 0,
                            "unclear_count": 0, "blocked_count": len(blocked),
                            "coverage_pct": 0.0,
                            "capability_gaps": [
                                f"connector_blocked:{cid}" for cid in blocked
                            ],
                            "artifacts": [],
                            "runtime_context": runtime_context.model_dump() if runtime_context else {},
                        }
                    # Push backend_base_url from context into cfg if not already set
                    if runtime_context.backend_base_url and not cfg.backend_base_url:
                        cfg.backend_base_url = runtime_context.backend_base_url
            except Exception as exc:
                logger.warning("RuntimeConnectorManager error: %s", exc)

        pgate = PermissionGate(cfg)
        if cfg.permission_required:
            decision = pgate.request(
                "launch_app",
                f"Launch '{cfg.app_name}': {cfg.launch_command}",
                RiskLevel.MEDIUM,
                command=cfg.launch_command,
                interactive=self._interactive,
            )
            if decision == PermissionDecision.DENIED:
                return {"verdict": "blocked", "pass_count": 0, "fail_count": 0,
                        "unclear_count": 0, "blocked_count": 1, "coverage_pct": 0.0,
                        "capability_gaps": [], "artifacts": []}

        launcher = AppLauncher()
        launch_result = launcher.launch(
            app_name=cfg.app_name,
            launch_command=cfg.launch_command,
            working_dir=cfg.working_dir,
            readiness_url=cfg.readiness_url,
            readiness_timeout=cfg.readiness_timeout_seconds,
        )
        if launch_result.status == "failed":
            return {"verdict": "blocked", "pass_count": 0, "fail_count": 0,
                    "unclear_count": 0, "blocked_count": 1, "coverage_pct": 0.0,
                    "capability_gaps": [f"launch_failed: {launch_result.failure_reason}"],
                    "artifacts": []}

        session = RuntimeSession(
            app_name=cfg.app_name,
            app_type=cfg.app_type,
            target_path=cfg.working_dir,
            launch_command=cfg.launch_command,
            session_id=session_id,
        )
        session.start()

        screenshots = ScreenshotCollector(out_dir, session_id)
        log_watcher = LogWatcher(expected_tags=cfg.logs.expected_tags, redact_secrets=True)
        if launch_result.process and launch_result.process.stdout:
            log_watcher.watch_process_stdout(launch_result.process, source="app")

        observer = ScreenObserver(cfg.app_type)
        controller = UIController(cfg.app_type, observer, screenshots)
        planner = UIActionPlanner(cfg.test_objectives)
        approval_gate = HumanApprovalGate()
        verifier = ResultVerifier(log_watcher=log_watcher)
        evidence_builder = RuntimeEvidenceBuilder()
        coverage = FunctionCoverageTracker(out_dir)

        # AI runtime (optional)
        ai_kw: Dict[str, Any] = {}
        _live_guided = False
        _ai_guided = False
        ai_cfg = cfg.ai_runtime
        if ai_cfg:
            _live_guided = live_guided and ai_cfg.live_guided.enabled
            _ai_guided = ai_guided and ai_cfg.ai_guidance.enabled
            from qa_ai.interactive_runtime.ai_runtime.safety_filter import SafetyFilter
            from qa_ai.interactive_runtime.ai_runtime.intent_inference import IntentInferenceEngine
            from qa_ai.interactive_runtime.ai_runtime.evidence_grounder import EvidenceGrounder
            ai_kw["ai_safety_filter"] = SafetyFilter()
            ai_kw["ai_intent_engine"] = IntentInferenceEngine()
            ai_kw["ai_evidence_grounder"] = EvidenceGrounder(config=ai_cfg.evidence_grounding)
            if _ai_guided:
                from qa_ai.interactive_runtime.ai_runtime.vision_screen_analyzer import VisionScreenAnalyzer
                from qa_ai.interactive_runtime.ai_runtime.ai_action_decider import AIActionDecider
                from qa_ai.interactive_runtime.ai_runtime.curiosity_engine import CuriosityEngine
                from qa_ai.interactive_runtime.ai_runtime.ai_oracle import AIOracle
                ai_kw["ai_vision_analyzer"] = VisionScreenAnalyzer(config=ai_cfg.vision_analysis)
                ai_kw["ai_action_decider"] = AIActionDecider(
                    safety_filter=ai_kw["ai_safety_filter"],
                    intent_engine=ai_kw["ai_intent_engine"],
                    curiosity_config=ai_cfg.curiosity,
                    vision_config=ai_cfg.vision_analysis,
                )
                ai_kw["ai_curiosity_engine"] = CuriosityEngine(
                    config=ai_cfg.curiosity, intent_engine=ai_kw["ai_intent_engine"]
                )
                ai_kw["ai_oracle"] = AIOracle(config=ai_cfg.ai_guidance)
            if _live_guided:
                from qa_ai.interactive_runtime.ai_runtime.step_narrator import StepNarrator
                from qa_ai.interactive_runtime.ai_runtime.guided_trace_writer import GuidedTraceWriter
                ai_kw["ai_narrator"] = StepNarrator(silent=not ai_cfg.live_guided.print_steps)
                ai_kw["ai_trace_writer"] = GuidedTraceWriter(
                    output_dir=out_dir,
                    write_markdown=ai_cfg.live_guided.write_markdown_trace,
                    write_json=ai_cfg.live_guided.write_json_trace,
                )

        executor = InteractionExecutor(
            config=cfg,
            session=session,
            controller=controller,
            observer=observer,
            planner=planner,
            permission_gate=pgate,
            approval_gate=approval_gate,
            verifier=verifier,
            evidence_builder=evidence_builder,
            coverage=coverage,
            screenshots=screenshots,
            log_watcher=log_watcher,
            interactive=self._interactive,
            live_guided=_live_guided,
            ai_guided=_ai_guided,
            **ai_kw,
        )

        try:
            executor.run()
        finally:
            launcher.stop()
            # Stop connectors if manager was used
            if connector_manager and connectors_cfg:
                try:
                    connector_manager.stop_all(connectors_cfg)
                except Exception as exc:
                    logger.warning("stop_all connectors error: %s", exc)

        session.save(out_dir)
        reporter = InteractiveReporter(out_dir)
        report = reporter.generate(session, coverage, approval_gate.audit_trail, executor=executor)

        artifacts = [
            str(p) for p in Path(out_dir).glob("*.json")
        ] + [str(p) for p in Path(out_dir).glob("*.html")]

        gaps = [str(g) for g in observer.capability_gaps]

        return {
            "verdict": report.final_verdict,
            "pass_count": report.total_passed,
            "fail_count": report.total_failed,
            "unclear_count": getattr(report, "total_unclear", 0),
            "blocked_count": getattr(report, "total_blocked", 0),
            "coverage_pct": report.coverage_pct,
            "capability_gaps": gaps,
            "artifacts": artifacts,
        }
