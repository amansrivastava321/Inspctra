"""
interaction_executor.py - Orchestrate the live interaction loop.

Two execution paths:
  1. Deterministic (default):
     observe screen → plan → approve → execute → verify → evidence → coverage

  2. AI-guided (--ai-guided):
     observe → screenshot_before → vision → curiosity → decide →
     safety_filter → approve → execute → screenshot_after →
     logs → deterministic_verify → oracle_suggest → ground_verdict →
     narrate → trace → coverage

Safeguards:
  - max_actions limit
  - max_duration limit
  - loop detection (repeated identical screen title)
  - stuck loading detection
  - crash detection
  - safety filter blocks destructive actions
  - AI-only PASS blocked by EvidenceGrounder
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from qa_ai.interactive_runtime.schemas import (
    ActionStatus,
    AIVerdict,
    GuidedStep,
    InteractiveRuntimeConfig,
    PermissionDecision,
    VerificationStatus,
)
from qa_ai.interactive_runtime.runtime_session import RuntimeSession
from qa_ai.interactive_runtime.screen_observer import ScreenObserver
from qa_ai.interactive_runtime.ui_action_planner import UIActionPlanner
from qa_ai.interactive_runtime.ui_controller import UIController
from qa_ai.interactive_runtime.permission_gate import PermissionGate
from qa_ai.interactive_runtime.human_approval_gate import HumanApprovalGate
from qa_ai.interactive_runtime.result_verifier import ResultVerifier
from qa_ai.interactive_runtime.runtime_evidence_builder import RuntimeEvidenceBuilder
from qa_ai.interactive_runtime.function_coverage_tracker import FunctionCoverageTracker
from qa_ai.interactive_runtime.screenshot_collector import ScreenshotCollector
from qa_ai.interactive_runtime.log_watcher import LogWatcher
from qa_ai.interactive_runtime.drivers.capability_detector import CapabilityDetector
from qa_ai.interactive_runtime.runtime_context.context_adapter import ContextAdapter
from qa_ai.interactive_runtime.runtime_context.context_capability_mapper import ContextCapabilityMapper
from qa_ai.interactive_runtime.runtime_context.context_verification_planner import ContextVerificationPlanner
from qa_ai.interactive_runtime.runtime_context.context_evidence_collector import ContextEvidenceCollector
from qa_ai.interactive_runtime.runtime_context.context_safety_policy import ContextSafetyPolicy, ContextSafetyDecision
from qa_ai.interactive_runtime.runtime_context.context_reporter import ContextReporter
from qa_ai.interactive_runtime.runtime_context.context_models import (
    ContextEvidenceBundle,
    RuntimeCapabilityPlan,
    RuntimeTestContext,
)

if TYPE_CHECKING:
    from qa_ai.interactive_runtime.ai_runtime.vision_screen_analyzer import VisionScreenAnalyzer
    from qa_ai.interactive_runtime.ai_runtime.ai_action_decider import AIActionDecider
    from qa_ai.interactive_runtime.ai_runtime.curiosity_engine import CuriosityEngine
    from qa_ai.interactive_runtime.ai_runtime.ai_oracle import AIOracle
    from qa_ai.interactive_runtime.ai_runtime.evidence_grounder import EvidenceGrounder
    from qa_ai.interactive_runtime.ai_runtime.step_narrator import StepNarrator
    from qa_ai.interactive_runtime.ai_runtime.guided_trace_writer import GuidedTraceWriter
    from qa_ai.interactive_runtime.ai_runtime.safety_filter import SafetyFilter
    from qa_ai.interactive_runtime.ai_runtime.intent_inference import IntentInferenceEngine

logger = logging.getLogger(__name__)

_STUCK_LOADING_THRESHOLD = 3    # consecutive loading-detected observations
_LOOP_DETECTION_THRESHOLD = 5   # same screen title this many times → stop


class InteractionExecutor:
    """
    Run the complete interactive testing loop for one RuntimeSession.

    Pass ai_* params to enable AI-guided mode.
    Without them, runs the deterministic loop unchanged.
    """

    def __init__(
        self,
        config: InteractiveRuntimeConfig,
        session: RuntimeSession,
        controller: UIController,
        observer: ScreenObserver,
        planner: UIActionPlanner,
        permission_gate: PermissionGate,
        approval_gate: HumanApprovalGate,
        verifier: ResultVerifier,
        evidence_builder: RuntimeEvidenceBuilder,
        coverage: FunctionCoverageTracker,
        screenshots: ScreenshotCollector,
        log_watcher: Optional[LogWatcher] = None,
        interactive: bool = True,
        # AI runtime modules (all optional — None = deterministic mode)
        ai_vision_analyzer: Optional["VisionScreenAnalyzer"] = None,
        ai_action_decider: Optional["AIActionDecider"] = None,
        ai_curiosity_engine: Optional["CuriosityEngine"] = None,
        ai_oracle: Optional["AIOracle"] = None,
        ai_evidence_grounder: Optional["EvidenceGrounder"] = None,
        ai_narrator: Optional["StepNarrator"] = None,
        ai_trace_writer: Optional["GuidedTraceWriter"] = None,
        ai_safety_filter: Optional["SafetyFilter"] = None,
        ai_intent_engine: Optional["IntentInferenceEngine"] = None,
        live_guided: bool = False,
        ai_guided: bool = False,
        # Live Runtime Connector context (optional — None = legacy behavior)
        runtime_context: Optional[Any] = None,
    ):
        self._config = config
        self._runtime_context = runtime_context  # RuntimeContext or None
        self._session = session
        self._controller = controller
        self._observer = observer
        self._planner = planner
        self._pgate = permission_gate
        self._agate = approval_gate
        self._verifier = verifier
        self._evidence = evidence_builder
        self._coverage = coverage
        self._screenshots = screenshots
        self._logs = log_watcher
        self._interactive = interactive

        # AI runtime modules
        self._ai_vision = ai_vision_analyzer
        self._ai_decider = ai_action_decider
        self._ai_curiosity = ai_curiosity_engine
        self._ai_oracle = ai_oracle
        self._ai_grounder = ai_evidence_grounder
        self._ai_narrator = ai_narrator
        self._ai_trace = ai_trace_writer
        self._ai_safety = ai_safety_filter
        self._ai_intent = ai_intent_engine
        self._live_guided = live_guided
        self._ai_guided = ai_guided

        self._tested_labels: Set[str] = set()
        self._screen_visit_counts: Dict[str, int] = {}
        self._consecutive_loading = 0
        self._action_count = 0
        self._start_time: float = 0.0

        # AI-guided tracking
        self._guided_steps: List[GuidedStep] = []
        self._ai_pass_count = 0
        self._ai_fail_count = 0
        self._ai_unclear_count = 0

        # RuntimeContext-derived objects (populated in _init_runtime_context)
        self._test_context: Optional[RuntimeTestContext] = None
        self._capability_plan: Optional[RuntimeCapabilityPlan] = None
        self._safety_policy: ContextSafetyPolicy = ContextSafetyPolicy(None)
        self._evidence_collector: Optional[ContextEvidenceCollector] = None
        self._verification_planner: Optional[ContextVerificationPlanner] = None
        self._context_reporter: Optional[ContextReporter] = None
        self._context_evidence_bundles: List[ContextEvidenceBundle] = []
        self._context_safety_decisions: List[Dict[str, Any]] = []

    def _init_runtime_context(self) -> None:
        """
        Initialize context-derived objects from self._runtime_context.

        Runs ContextAdapter → ContextCapabilityMapper → creates safety policy,
        evidence collector, verification planner, reporter.
        No-op if runtime_context is None (legacy mode).
        """
        if self._runtime_context is None:
            return

        # Adapt raw RuntimeContext → normalized RuntimeTestContext
        self._test_context = ContextAdapter.adapt(self._runtime_context)
        if self._test_context is None:
            return

        # Map context → capability plan
        self._capability_plan = ContextCapabilityMapper.map(self._test_context)

        # Safety policy (context-level, applied after PermissionGate)
        self._safety_policy = ContextSafetyPolicy(self._test_context)

        # Evidence collector (wired with verifier's backend/db/log deps via public properties)
        self._evidence_collector = ContextEvidenceCollector(
            ctx=self._test_context,
            backend_checker=getattr(self._verifier, "backend_checker", None),
            db_verifier=getattr(self._verifier, "db_verifier", None),
            log_watcher=self._logs,
        )

        # Verification planner
        self._verification_planner = ContextVerificationPlanner(
            ctx=self._test_context,
            plan=self._capability_plan,
        )

        # Reporter (writes to same artifacts dir as InteractiveReporter)
        output_dir = getattr(self._config, "artifacts_dir", "artifacts")
        self._context_reporter = ContextReporter(output_dir=output_dir)

        # Write initial artifacts
        self._context_reporter.write_context(self._test_context)
        self._context_reporter.write_capability_plan(self._capability_plan)

        logger.info(
            "RuntimeContext wired: ui=%s backend=%s db=%s third_party=%s gaps=%d",
            self._test_context.ui_method.value,
            self._test_context.backend_available,
            self._test_context.database_available,
            self._test_context.is_third_party_mode,
            len(self._test_context.blocked_connector_ids),
        )

    def _apply_context_safety(
        self,
        action_type: str,
        action_description: str,
        target_url: Optional[str] = None,
    ) -> ContextSafetyDecision:
        """
        Run context-level safety check for a proposed action.
        Records the decision for later reporting.
        """
        decision = self._safety_policy.check_action(
            action_type, action_description, target_url=target_url
        )
        self._context_safety_decisions.append({
            "action_type": action_type,
            "description": action_description[:120],
            "allowed": decision.allowed,
            "reason": decision.reason,
        })
        return decision

    def _collect_context_evidence(
        self,
        step_id: str,
        screenshots: Optional[List[str]] = None,
    ) -> Optional[ContextEvidenceBundle]:
        """Collect per-step evidence from all runtime sources."""
        if not self._evidence_collector:
            return None
        bundle = self._evidence_collector.collect(step_id, screenshots=screenshots)
        self._context_evidence_bundles.append(bundle)
        return bundle

    def record_backend_info(self) -> None:
        """Populate session fields with automation backend and platform details."""
        try:
            caps = self._controller._driver.capabilities()
            self._session.automation_backend = caps.backend.value
            self._session.driver_capabilities = {
                "can_observe_screen": caps.can_observe_screen,
                "can_click": caps.can_click,
                "can_type": caps.can_type,
                "can_screenshot": caps.can_screenshot,
                "status": caps.status.value,
            }
            self._session.platform_info = CapabilityDetector.current_platform()
            self._session.accessibility_permission_status = (
                CapabilityDetector.macos_accessibility_permission()
            )
        except Exception as exc:
            logger.warning("record_backend_info failed: %s", exc)

    def run(self) -> RuntimeSession:
        """Execute the interaction loop. Returns the completed session."""
        self._start_time = time.time()

        # Initialize RuntimeContext-derived objects before the loop
        self._init_runtime_context()

        self.record_backend_info()

        for gap in self._controller.capability_gaps:
            self._session.add_capability_gap(gap)

        # Start guided trace writer if live-guided
        if self._live_guided and self._ai_trace:
            objectives = " | ".join(self._config.test_objectives or ["(none)"])
            self._ai_trace.start(
                app_name=self._config.app_name,
                test_objective=objectives,
                session_id=self._session.session_id,
            )

        try:
            if self._ai_guided and (self._ai_decider or self._ai_curiosity):
                self._run_ai_guided_loop()
            else:
                self._loop()
        except KeyboardInterrupt:
            logger.info("Interaction loop stopped by user.")
            self._session.end("stopped", "User interrupted the session.")
        except Exception as exc:
            logger.error("Interaction loop crashed: %s", exc, exc_info=True)
            self._session.end("error", str(exc))
        else:
            self._session.end()

        # Finish guided trace
        if self._live_guided and self._ai_trace:
            self._ai_trace.finish(
                total_pass=self._ai_pass_count,
                total_fail=self._ai_fail_count,
                total_unclear=self._ai_unclear_count,
            )

        self._coverage.save()

        # Write final context report artifacts
        if self._context_reporter:
            self._context_reporter.write_evidence_bundles(self._context_evidence_bundles)
            self._context_reporter.write_safety_summary(self._context_safety_decisions)

        return self._session

    # ── deterministic loop (unchanged) ────────────────────────────────────────

    def _loop(self) -> None:
        while True:
            elapsed = time.time() - self._start_time

            if self._action_count >= self._config.max_actions:
                logger.info("Max actions reached (%d)", self._config.max_actions)
                break
            if elapsed >= self._config.max_duration_seconds:
                logger.info("Max duration reached (%.0fs)", elapsed)
                break

            step_id = f"step-{self._action_count + 1:04d}"
            screen = self._observer.observe(step_id)
            self._session.set_screen(screen.title)

            count = self._screen_visit_counts.get(screen.title, 0) + 1
            self._screen_visit_counts[screen.title] = count
            if count >= _LOOP_DETECTION_THRESHOLD:
                logger.info("Loop detected on screen '%s' — stopping.", screen.title)
                break

            if screen.has_loading_indicator:
                self._consecutive_loading += 1
                if self._consecutive_loading >= _STUCK_LOADING_THRESHOLD:
                    logger.warning("Stuck loading indicator on '%s' — stopping.", screen.title)
                    break
                time.sleep(2)
                continue
            else:
                self._consecutive_loading = 0

            new_items = self._planner.coverage_items_from_screen(screen)
            self._coverage.discover_many(new_items)

            actions = self._planner.plan(screen, self._tested_labels, max_actions=10)
            if not actions:
                logger.info("No more actions planned for screen '%s'.", screen.title)
                break

            for action in actions:
                if self._action_count >= self._config.max_actions:
                    break

                # Context-level safety check (after PermissionGate, before execute)
                ctx_decision = self._apply_context_safety(
                    action.action_type,
                    action.description,
                )
                if not ctx_decision.allowed:
                    logger.info(
                        "Context safety blocked action '%s': %s",
                        action.action_type,
                        ctx_decision.reason,
                    )
                    continue

                decision = self._agate.check(action, self._interactive)
                if decision == PermissionDecision.DENIED:
                    cov_item = self._coverage.find_by_label(
                        screen.title,
                        action.target_element.label if action.target_element else "",
                    )
                    if cov_item:
                        self._coverage.mark_blocked(cov_item.item_id, "User denied approval")
                    continue

                self._action_count += 1
                self._session.set_screen(screen.title)
                result = self._controller.execute(action, step_id=step_id)
                self._session.record_action(result)

                label = action.target_element.label if action.target_element else action.action_type
                self._tested_labels.add(label)

                cov_item = self._coverage.find_by_label(screen.title, label)
                if cov_item:
                    self._coverage.mark_attempted(cov_item.item_id, action.action_type)

                vr = self._verifier.verify(
                    step_id=step_id,
                    action_result=result,
                    expected_log_tags=self._config.logs.expected_tags if self._config.log_capture_enabled else None,
                )
                self._session.record_verification(step_id, vr)

                if cov_item:
                    self._coverage.mark_by_verification(
                        cov_item.item_id,
                        vr.overall_status,
                        actual_result=f"{vr.passed_count}/{len(vr.checks)} checks",
                    )
                    self._session.record_coverage(cov_item)

                log_excerpts = []
                if self._logs:
                    log_excerpts = self._logs.all_lines()[-20:]

                # Collect context evidence (backend health, logs, etc.)
                self._collect_context_evidence(step_id)

                ev = self._evidence.build(
                    step_id=step_id,
                    action_description=action.description,
                    action_result=result,
                    verification_result=vr,
                    log_excerpts=log_excerpts,
                )
                self._session.record_evidence(ev)

                step_id = f"step-{self._action_count + 1:04d}"
                time.sleep(0.5)

    # ── AI-guided loop ─────────────────────────────────────────────────────────

    def _run_ai_guided_loop(self) -> None:
        """
        AI-guided interactive loop.

        Uses CuriosityEngine/AIActionDecider to choose actions.
        Uses EvidenceGrounder for final verdict (not AI oracle alone).
        Uses StepNarrator and GuidedTraceWriter for live output.
        """
        ai_cfg = self._config.ai_runtime
        live_cfg = ai_cfg.live_guided if ai_cfg else None
        evidence_cfg = ai_cfg.evidence_grounding if ai_cfg else None

        pause_on_fail = getattr(live_cfg, "pause_on_fail", False)
        pause_on_unclear = getattr(live_cfg, "pause_on_unclear", False)

        objectives = " | ".join(self._config.test_objectives or ["(none)"])

        while True:
            elapsed = time.time() - self._start_time

            # Stop conditions
            if self._action_count >= self._config.max_actions:
                logger.info("[AI-GUIDED] Max actions reached (%d).", self._config.max_actions)
                break
            if elapsed >= self._config.max_duration_seconds:
                logger.info("[AI-GUIDED] Max duration reached (%.0fs).", elapsed)
                break

            step_num = self._action_count + 1
            step_id = f"step-{step_num:04d}"

            # ── observe screen ──────────────────────────────────────────────

            # Capture before screenshot
            screenshot_before: Optional[str] = None
            if self._config.screenshot_enabled:
                p = self._screenshots.capture_from_driver(
                    self._controller._driver, step_id=step_id, label="before"
                )
                screenshot_before = str(p) if p else None

            screen = self._observer.observe(step_id, screenshot_path=screenshot_before)
            self._session.set_screen(screen.title)

            # Loop detection
            visit_count = self._screen_visit_counts.get(screen.title, 0) + 1
            self._screen_visit_counts[screen.title] = visit_count
            if visit_count >= _LOOP_DETECTION_THRESHOLD:
                logger.info("[AI-GUIDED] Loop on screen '%s' — stopping.", screen.title)
                break

            # Stuck loading
            if screen.has_loading_indicator:
                self._consecutive_loading += 1
                if self._consecutive_loading >= _STUCK_LOADING_THRESHOLD:
                    logger.warning("[AI-GUIDED] Stuck loading on '%s' — stopping.", screen.title)
                    break
                time.sleep(2)
                continue
            else:
                self._consecutive_loading = 0

            # Discover coverage items
            new_items = self._planner.coverage_items_from_screen(screen)
            self._coverage.discover_many(new_items)

            # ── vision analysis ─────────────────────────────────────────────

            vision_analysis = None
            if self._ai_vision:
                try:
                    vision_analysis = self._ai_vision.analyze(
                        screen=screen, screenshot_path=screenshot_before
                    )
                except Exception as exc:
                    logger.warning("[AI-GUIDED] Vision analysis failed: %s", exc)

            # ── curiosity / action decision ─────────────────────────────────

            # Use CuriosityEngine if available, else fall back to AIActionDecider directly
            proposed_action = None
            proposal_reason = ""
            expected_outcome = ""
            action_risk = None

            if self._ai_curiosity:
                curiosity_target = self._ai_curiosity.choose_next(
                    screen=screen,
                    tested_labels=self._tested_labels,
                    test_objective=objectives,
                    coverage_items=self._coverage.all_items(),
                )
                if curiosity_target.stop_condition_met:
                    logger.info(
                        "[AI-GUIDED] Curiosity engine stop: %s", curiosity_target.stop_reason
                    )
                    break

                # Build action from curiosity target
                if curiosity_target.target_element and self._ai_decider:
                    proposal = self._ai_decider.decide(
                        screen=screen,
                        vision=vision_analysis,
                        test_objective=objectives,
                        previously_tested=self._tested_labels,
                    )
                    if proposal.blocked:
                        logger.info(
                            "[AI-GUIDED] Safety blocked proposed action: %s",
                            proposal.block_reason,
                        )
                        self._tested_labels.add(curiosity_target.target_label)
                        continue
                    if proposal.ask_user and not self._interactive:
                        logger.info(
                            "[AI-GUIDED] Non-interactive — skipping action needing approval."
                        )
                        self._tested_labels.add(curiosity_target.target_label)
                        continue
                    proposed_action = proposal.proposed_action
                    proposal_reason = proposal.reason
                    expected_outcome = proposal.expected_outcome
                    action_risk = proposal.risk_level
                elif curiosity_target.target_element:
                    # Build action directly from curiosity target without decider
                    from qa_ai.interactive_runtime.schemas import UIAction
                    proposed_action = UIAction(
                        action_type="click",
                        target_element=curiosity_target.target_element,
                        description=f"click '{curiosity_target.target_label}'",
                        risk_level=curiosity_target.target_element.risk_level,
                    )
                    proposal_reason = curiosity_target.exploration_reason
                    expected_outcome = f"Interaction with '{curiosity_target.target_label}' produces visible change."

            elif self._ai_decider:
                proposal = self._ai_decider.decide(
                    screen=screen,
                    vision=vision_analysis,
                    test_objective=objectives,
                    previously_tested=self._tested_labels,
                )
                if proposal.blocked:
                    logger.info("[AI-GUIDED] Safety blocked: %s", proposal.block_reason)
                    break
                if proposal.ask_user and not self._interactive:
                    break
                proposed_action = proposal.proposed_action
                proposal_reason = proposal.reason
                expected_outcome = proposal.expected_outcome

            # Fallback: use deterministic planner if no AI action
            if proposed_action is None:
                det_actions = self._planner.plan(screen, self._tested_labels, max_actions=1)
                if not det_actions:
                    logger.info("[AI-GUIDED] No action available — stopping.")
                    break
                proposed_action = det_actions[0]
                proposal_reason = "Deterministic planner fallback (no AI action available)."
                expected_outcome = proposed_action.description

            # ── context-level safety check ──────────────────────────────────
            # Applied before AI safety filter and approval gate

            ctx_decision = self._apply_context_safety(
                proposed_action.action_type if proposed_action else "",
                proposed_action.description if proposed_action else "",
            )
            if not ctx_decision.allowed:
                logger.info(
                    "[AI-GUIDED] Context safety blocked '%s': %s",
                    proposed_action.action_type if proposed_action else "?",
                    ctx_decision.reason,
                )
                if proposed_action and proposed_action.target_element:
                    self._tested_labels.add(proposed_action.target_element.label)
                continue

            # ── safety filter ───────────────────────────────────────────────

            permission_needed = ""
            if self._ai_safety:
                safety_decision = self._ai_safety.evaluate(proposed_action)
                if safety_decision.blocked:
                    logger.info("[AI-GUIDED] Safety filter hard-blocked: %s", safety_decision.block_reason)
                    label = (
                        proposed_action.target_element.label
                        if proposed_action.target_element else ""
                    )
                    if label:
                        self._tested_labels.add(label)
                    continue
                if safety_decision.requires_approval:
                    permission_needed = safety_decision.risk_category
                    proposed_action = proposed_action.model_copy(
                        update={"requires_approval": True}
                    )

            # ── approval gate ───────────────────────────────────────────────

            gate_decision = self._agate.check(proposed_action, self._interactive)
            if gate_decision == PermissionDecision.DENIED:
                label = (
                    proposed_action.target_element.label
                    if proposed_action.target_element else ""
                )
                cov_item = self._coverage.find_by_label(screen.title, label)
                if cov_item:
                    self._coverage.mark_blocked(cov_item.item_id, "User denied approval")

                # Write blocked step to trace
                if self._live_guided:
                    blocked_step = GuidedStep(
                        step_number=step_num,
                        step_id=step_id,
                        screen_title=screen.title,
                        plan=f"Blocked: {proposed_action.description}",
                        why=proposal_reason,
                        permission_needed=permission_needed,
                        action_taken="BLOCKED — approval denied",
                        screenshot_before=screenshot_before,
                        final_verdict=AIVerdict.UNCLEAR,
                        confidence_pct=0.0,
                    )
                    self._record_guided_step(blocked_step)
                continue

            # ── execute action ──────────────────────────────────────────────

            self._action_count += 1
            self._session.set_screen(screen.title)

            result = self._controller.execute(proposed_action, step_id=step_id)
            self._session.record_action(result)

            label = (
                proposed_action.target_element.label
                if proposed_action.target_element
                else proposed_action.action_type
            )
            self._tested_labels.add(label)

            cov_item = self._coverage.find_by_label(screen.title, label)
            if cov_item:
                self._coverage.mark_attempted(cov_item.item_id, proposed_action.action_type)

            # ── capture after screenshot ────────────────────────────────────

            screenshot_after: Optional[str] = None
            if self._config.screenshot_enabled:
                p = self._screenshots.capture_from_driver(
                    self._controller._driver, step_id=step_id, label="after"
                )
                screenshot_after = str(p) if p else None
            if result.screenshot_after:
                screenshot_after = result.screenshot_after

            # ── collect logs ────────────────────────────────────────────────

            log_excerpts: List[str] = []
            log_matches: List[str] = []
            if self._logs:
                log_excerpts = self._logs.all_lines()[-30:]
                expected_tags = self._config.logs.expected_tags or []

                # Also check generic_expected_signals from ai_runtime config
                if ai_cfg and ai_cfg.generic_expected_signals:
                    expected_tags = list(set(expected_tags + ai_cfg.generic_expected_signals.logs))

                for tag in expected_tags:
                    matched = self._logs.get_matched_lines(tag)
                    if matched:
                        log_matches.extend(matched[:2])

            # ── deterministic verification ──────────────────────────────────

            det_log_tags = self._config.logs.expected_tags if self._config.log_capture_enabled else None
            vr = self._verifier.verify(
                step_id=step_id,
                action_result=result,
                expected_log_tags=det_log_tags,
            )
            self._session.record_verification(step_id, vr)

            # ── AI oracle suggestion ────────────────────────────────────────

            oracle_suggestion = None
            screen_after_state = result.screen_after
            if self._ai_oracle:
                screen_before_summary = f"title='{screen.title}' elements={len(screen.elements)}"
                screen_after_summary = (
                    f"title='{screen_after_state.title}' elements={len(screen_after_state.elements)}"
                    if screen_after_state else "unavailable"
                )
                try:
                    oracle_suggestion = self._ai_oracle.suggest(
                        step_id=step_id,
                        action_description=proposed_action.description,
                        expected_outcome=expected_outcome,
                        screen_before_summary=screen_before_summary,
                        screen_after_summary=screen_after_summary,
                        log_snippets=log_excerpts[-10:] if log_excerpts else None,
                        deterministic_result=vr,
                    )
                except Exception as exc:
                    logger.warning("[AI-GUIDED] Oracle failed: %s", exc)

            # ── evidence grounding (final verdict) ──────────────────────────

            grounded = None
            final_ai_verdict = AIVerdict.UNCLEAR
            confidence_pct = 0.0

            # Collect context evidence for this step
            step_screenshots = [s for s in [screenshot_before, screenshot_after] if s]
            ctx_evidence = self._collect_context_evidence(step_id, step_screenshots)

            if self._ai_grounder:
                used_coord_click = (
                    proposed_action.target_element is not None
                    and proposed_action.target_element.selector is None
                    and proposed_action.target_element.bounding_box is not None
                )
                # Wire context evidence into grounding (extension points)
                db_check_result = None
                backend_check_result = None
                if ctx_evidence:
                    if ctx_evidence.backend_health:
                        backend_check_result = ctx_evidence.backend_health.get("status")

                grounded = self._ai_grounder.ground(
                    step_id=step_id,
                    oracle_suggestion=oracle_suggestion,
                    deterministic_result=vr,
                    screen_after=screen_after_state,
                    log_matches=log_matches or None,
                    db_check_result=db_check_result,
                    backend_check_result=backend_check_result,
                    screenshot_after=screenshot_after,
                    used_coordinate_click=used_coord_click,
                )
                final_ai_verdict = grounded.final_status
                confidence_pct = grounded.confidence * 100
            else:
                # Fallback mapping from deterministic status
                final_ai_verdict = _verification_to_ai_verdict(vr.overall_status)
                confidence_pct = 70.0 if vr.overall_status == VerificationStatus.PASSED else 40.0

            # Track counts
            if final_ai_verdict == AIVerdict.PASS:
                self._ai_pass_count += 1
            elif final_ai_verdict == AIVerdict.FAIL:
                self._ai_fail_count += 1
            else:
                self._ai_unclear_count += 1

            # ── update coverage ─────────────────────────────────────────────

            coverage_verification_status = _ai_verdict_to_verification_status(final_ai_verdict)
            if cov_item:
                self._coverage.mark_by_verification(
                    cov_item.item_id,
                    coverage_verification_status,
                    actual_result=f"verdict={final_ai_verdict.value} conf={confidence_pct:.0f}%",
                )
                self._session.record_coverage(cov_item)

            # ── build evidence ──────────────────────────────────────────────

            ev = self._evidence.build(
                step_id=step_id,
                action_description=proposed_action.description,
                action_result=result,
                verification_result=vr,
                log_excerpts=log_excerpts,
            )
            self._session.record_evidence(ev)

            # ── build guided step ───────────────────────────────────────────

            if self._live_guided:
                evidence_checked = ["screenshot before/after"]
                if det_log_tags:
                    evidence_checked += [f"log tag: {t}" for t in det_log_tags[:3]]
                if screen_after_state:
                    evidence_checked.append("UI state after action")

                evidence_found: List[str] = []
                if vr.passed_count > 0:
                    evidence_found.append(f"{vr.passed_count} deterministic checks passed")
                if log_matches:
                    evidence_found.append(f"{len(log_matches)} log tag(s) matched")
                if screenshot_after:
                    evidence_found.append("screenshot captured")

                what_sees = (
                    f"{len(screen.elements)} elements, "
                    f"{'loading' if screen.has_loading_indicator else 'stable'}"
                )

                guided_step = GuidedStep(
                    step_number=step_num,
                    step_id=step_id,
                    screen_title=screen.title,
                    screen_url=screen.url,
                    what_inspectra_sees=what_sees,
                    plan=f"{proposed_action.action_type} '{label}'",
                    why=proposal_reason[:200],
                    permission_needed=permission_needed,
                    action_taken=(
                        f"{proposed_action.action_type} '{label}' — "
                        f"status: {result.status.value}"
                    ),
                    evidence_checked=evidence_checked,
                    evidence_found=evidence_found,
                    screenshot_before=screenshot_before,
                    screenshot_after=screenshot_after,
                    log_matches=log_matches[:10],
                    oracle_suggestion=oracle_suggestion,
                    grounded_verdict=grounded,
                    final_verdict=final_ai_verdict,
                    confidence_pct=confidence_pct,
                )

                self._record_guided_step(guided_step)

            # ── pause conditions ────────────────────────────────────────────

            if pause_on_fail and final_ai_verdict == AIVerdict.FAIL:
                logger.warning("[AI-GUIDED] Pausing on FAIL for step %s.", step_id)
                if self._interactive:
                    try:
                        input("  [AI-GUIDED] FAIL detected. Press Enter to continue or Ctrl+C to stop: ")
                    except (EOFError, KeyboardInterrupt):
                        break

            if pause_on_unclear and final_ai_verdict == AIVerdict.UNCLEAR:
                logger.info("[AI-GUIDED] UNCLEAR verdict for step %s.", step_id)

            # Brief pause
            time.sleep(0.5)

    # ── guided step helpers ────────────────────────────────────────────────────

    def _record_guided_step(self, step: GuidedStep) -> None:
        """Narrate + write a guided step."""
        self._guided_steps.append(step)
        if self._ai_narrator:
            try:
                self._ai_narrator.narrate(step)
            except Exception as exc:
                logger.warning("[AI-GUIDED] Narrator failed: %s", exc)
        if self._ai_trace:
            try:
                self._ai_trace.add_step(step)
            except Exception as exc:
                logger.warning("[AI-GUIDED] Trace writer failed: %s", exc)

    @property
    def guided_steps(self) -> List[GuidedStep]:
        return list(self._guided_steps)


# ── verdict mapping helpers ────────────────────────────────────────────────────

def _ai_verdict_to_verification_status(verdict: AIVerdict) -> VerificationStatus:
    return {
        AIVerdict.PASS: VerificationStatus.PASSED,
        AIVerdict.FAIL: VerificationStatus.FAILED,
        AIVerdict.UNCLEAR: VerificationStatus.INCONCLUSIVE,
    }.get(verdict, VerificationStatus.INCONCLUSIVE)


def _verification_to_ai_verdict(status: VerificationStatus) -> AIVerdict:
    return {
        VerificationStatus.PASSED: AIVerdict.PASS,
        VerificationStatus.FAILED: AIVerdict.FAIL,
        VerificationStatus.INCONCLUSIVE: AIVerdict.UNCLEAR,
        VerificationStatus.BLOCKED: AIVerdict.UNCLEAR,
        VerificationStatus.SKIPPED: AIVerdict.UNCLEAR,
    }.get(status, AIVerdict.UNCLEAR)
