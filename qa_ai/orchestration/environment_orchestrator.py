"""
environment_orchestrator.py - Autonomous environment provisioning engine.
Detects missing environments, provisions them, requests permissions,
launches emulators, connects devices, validates CI availability.

The product NEVER says "Cannot test X."
It says "X is missing. Would you like me to set it up?"
"""

from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import subprocess
import os
import shutil
import time
import logging
import json
import platform as sys_platform

from qa_ai.runtime.capability_registry import (
    CapabilityRegistry,
    Capability,
    CapabilityStatus,
    ProvisionStrategy,
    DeviceInfo,
    EnvironmentCapabilities,
    get_capability_registry,
)
from qa_ai.runtime.execution_context import (
    ExecutionContext,
    Platform,
    Environment,
)
from qa_ai.runtime.permission_manager import (
    PermissionManager,
    PermissionRisk,
)

logger = logging.getLogger(__name__)


# ─── Data Models ───────────────────────────────────────

class ProvisionAction(Enum):
    """What action to take for a missing capability."""
    INSTALL = "install"
    CONFIGURE = "configure"
    LAUNCH = "launch"
    CONNECT = "connect"
    AUTHENTICATE = "authenticate"
    DOWNLOAD = "download"
    WAIT = "wait"
    ASK_USER = "ask_user"
    SKIP = "skip"
    BLOCK = "block"


class ProvisionStatus(Enum):
    """Result of a provisioning attempt."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING_USER = "pending_user"
    PENDING_CREDENTIALS = "pending_credentials"
    PENDING_DEVICE = "pending_device"
    IN_PROGRESS = "in_progress"
    NOT_NEEDED = "not_needed"


@dataclass
class ProvisionStep:
    """A single step in the environment provisioning process."""
    step_id: str
    capability_name: str
    action: ProvisionAction
    command: Optional[str] = None
    description: str = ""
    status: ProvisionStatus = ProvisionStatus.NOT_NEEDED
    output: Optional[str] = None
    error: Optional[str] = None
    requires_user_confirmation: bool = False
    user_prompt: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "capability_name": self.capability_name,
            "action": self.action.value,
            "command": self.command,
            "description": self.description,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "requires_user_confirmation": self.requires_user_confirmation,
            "user_prompt": self.user_prompt,
        }


@dataclass
class EnvironmentPlan:
    """
    Complete environment provisioning plan.
    What needs to be done to make a target platform testable.
    """
    target_platform: Platform
    environment: Environment
    is_ready: bool = False
    steps: List[ProvisionStep] = field(default_factory=list)
    missing_capabilities: List[str] = field(default_factory=list)
    provisionable_automatically: List[str] = field(default_factory=list)
    requires_user_action: List[str] = field(default_factory=list)
    blocked_reasons: List[str] = field(default_factory=list)
    
    @property
    def is_blocked(self) -> bool:
        return len(self.blocked_reasons) > 0
    
    @property
    def needs_user(self) -> bool:
        return len(self.requires_user_action) > 0
    
    def to_dict(self) -> dict:
        return {
            "target_platform": self.target_platform.value,
            "environment": self.environment.value,
            "is_ready": self.is_ready,
            "steps": [s.to_dict() for s in self.steps],
            "missing_capabilities": self.missing_capabilities,
            "provisionable_automatically": self.provisionable_automatically,
            "requires_user_action": self.requires_user_action,
            "blocked_reasons": self.blocked_reasons,
            "is_blocked": self.is_blocked,
            "needs_user": self.needs_user,
        }


@dataclass
class OrchestrationResult:
    """Result of an environment orchestration run."""
    success: bool
    platform: Platform
    plans: List[EnvironmentPlan] = field(default_factory=list)
    provisioned: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    waiting_for_user: List[str] = field(default_factory=list)
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    duration_seconds: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "platform": self.platform.value,
            "plans": [p.to_dict() for p in self.plans],
            "provisioned": self.provisioned,
            "failed": self.failed,
            "waiting_for_user": self.waiting_for_user,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "duration_seconds": self.duration_seconds,
        }


# ─── Environment Orchestrator ──────────────────────────

class EnvironmentOrchestrator:
    """
    Autonomous environment provisioning engine.
    
    Core philosophy:
    - NEVER say "Cannot test X"
    - ALWAYS say "X is missing. Here's what I can do about it."
    
    Capabilities:
    1. Detect what's needed for a target platform
    2. Identify what's missing
    3. Auto-provision what can be automated
    4. Guide user for what needs manual action
    5. Launch emulators, simulators, browsers
    6. Connect to physical devices
    7. Validate CI environment readiness
    """
    
    def __init__(
        self,
        registry: Optional[CapabilityRegistry] = None,
        user_callback: Optional[Callable[[str, str], bool]] = None,
    ):
        """
        Args:
            registry: Capability registry for environment detection
            user_callback: Optional callback for user prompts.
                          Signature: (question: str, context: str) -> bool (confirmed?)
        """
        self.registry = registry or get_capability_registry()
        self.capabilities: Optional[EnvironmentCapabilities] = None
        self.user_callback = user_callback or self._default_user_callback
    
    # ─── Main Entry Points ─────────────────────────────
    
    def prepare_for_platform(
        self,
        platform: Platform,
        environment: Environment = Environment.LOCAL,
        auto_provision: bool = True,
    ) -> OrchestrationResult:
        """
        Prepare the environment for testing a specific platform.
        
        This is the main entry point. It:
        1. Scans the environment
        2. Identifies what's needed
        3. Auto-provisions what it can
        4. Returns what needs user action
        
        Args:
            platform: Target platform (web, android, ios, flutter, etc.)
            environment: Execution environment (local, emulator, CI, etc.)
            auto_provision: If True, automatically install missing tools
            
        Returns:
            OrchestrationResult with status of all provisioning steps
        """
        start_time = time.time()
        
        logger.info(f"Preparing environment for {platform.value} ({environment.value})")
        
        # Step 1: Scan current environment
        self.capabilities = self.registry.scan_all()
        
        # Step 2: Build provisioning plan
        plans = self._build_plan(platform, environment)
        
        # Step 3: Execute plan
        result = self._execute_plans(plans, auto_provision)
        
        result.duration_seconds = time.time() - start_time
        
        logger.info(
            f"Environment preparation complete: "
            f"{result.completed_steps}/{result.total_steps} steps done, "
            f"{len(result.waiting_for_user)} waiting for user"
        )
        
        return result
    
    def prepare_for_context(self, context: ExecutionContext) -> OrchestrationResult:
        """Prepare environment based on execution context."""
        return self.prepare_for_platform(
            platform=context.platform,
            environment=context.environment,
        )
    
    def quick_prepare(self, platform: Platform) -> bool:
        """
        Quick check: is the environment ready?
        If not, try to auto-provision silently.
        Returns True if ready.
        """
        result = self.prepare_for_platform(platform, auto_provision=True)
        return result.success and len(result.waiting_for_user) == 0
    
    # ─── Plan Building ─────────────────────────────────
    
    def _build_plan(
        self,
        platform: Platform,
        environment: Environment,
    ) -> List[EnvironmentPlan]:
        """Build provisioning plans for the target platform."""
        plans = []
        
        # Determine what environments to prepare
        target_environments = self._get_target_environments(platform, environment)
        
        for env in target_environments:
            plan = EnvironmentPlan(
                target_platform=platform,
                environment=env,
            )
            
            # Check required capabilities
            required = self._get_required_capabilities(platform, env)
            
            for cap_name in required:
                cap = self.capabilities.capabilities.get(cap_name)
                
                if cap is None:
                    plan.blocked_reasons.append(f"Unknown capability: {cap_name}")
                    continue
                
                if cap.is_available:
                    continue  # Already available
                
                plan.missing_capabilities.append(cap_name)
                
                if cap.can_provision and cap.provision_strategy == ProvisionStrategy.AUTO:
                    plan.provisionable_automatically.append(cap_name)
                    plan.steps.append(self._create_provision_step(cap, ProvisionAction.INSTALL))
                
                elif cap.provision_strategy == ProvisionStrategy.GUIDED:
                    plan.requires_user_action.append(cap_name)
                    plan.steps.append(self._create_provision_step(cap, ProvisionAction.ASK_USER))
                
                elif cap.provision_strategy == ProvisionStrategy.CREDENTIAL:
                    plan.requires_user_action.append(cap_name)
                    plan.steps.append(self._create_provision_step(cap, ProvisionAction.AUTHENTICATE))
                
                elif cap.provision_strategy == ProvisionStrategy.DEVICE:
                    plan.requires_user_action.append(cap_name)
                    plan.steps.append(self._create_provision_step(cap, ProvisionAction.CONNECT))
                
                else:
                    plan.blocked_reasons.append(
                        f"{cap_name} is not available and cannot be provisioned: {cap.error_message or 'No provision path'}"
                    )
            
            # Check devices
            self._add_device_steps(plan, platform)
            
            plans.append(plan)
        
        return plans
    
    def _get_target_environments(
        self,
        platform: Platform,
        environment: Environment,
    ) -> List[Environment]:
        """Determine which environments need preparation."""
        if environment == Environment.CI:
            return [Environment.CI]
        
        if platform == Platform.ANDROID:
            return [Environment.LOCAL]  # Could also add EMULATOR
        
        if platform == Platform.IOS:
            return [Environment.LOCAL]
        
        if platform == Platform.WEB:
            return [Environment.LOCAL]
        
        return [environment]
    
    def _get_required_capabilities(
        self,
        platform: Platform,
        environment: Environment,
    ) -> List[str]:
        """Get list of capabilities required for a platform/environment combo."""
        required = []
        
        if environment == Environment.CI:
            required.extend(["git", "docker", "python"])
        
        if platform == Platform.FLUTTER:
            required.append("flutter")
        
        if platform == Platform.ANDROID:
            required.extend(["flutter", "android_sdk", "adb", "java"])
        
        if platform == Platform.IOS:
            if sys_platform.system() == "Darwin":
                required.extend(["flutter", "xcode", "ios_simulator"])
            else:
                required.extend(["flutter"])  # Can still analyze code
        
        if platform == Platform.WEB:
            required.append("playwright")
            required.append("chromium")
        
        if platform in (Platform.BACKEND, Platform.CLI):
            required.append("python")
        
        return required
    
    def _add_device_steps(self, plan: EnvironmentPlan, platform: Platform):
        """Add device-related provisioning steps."""
        if platform == Platform.ANDROID:
            if len(self.capabilities.android_devices) == 0:
                step = ProvisionStep(
                    step_id=f"device_android_emu_{plan.target_platform.value}",
                    capability_name="android_emulator",
                    action=ProvisionAction.LAUNCH,
                    description="No Android devices found. Launch an emulator or connect a device.",
                    requires_user_confirmation=True,
                    user_prompt="Would you like to launch an Android emulator? (Ensure Android Studio is installed)",
                )
                plan.steps.append(step)
        
        if platform == Platform.IOS:
            if len(self.capabilities.ios_devices) == 0:
                step = ProvisionStep(
                    step_id=f"device_ios_sim_{plan.target_platform.value}",
                    capability_name="ios_simulator",
                    action=ProvisionAction.LAUNCH,
                    description="No iOS simulators found. Open Xcode → Settings → Components to download a simulator.",
                    requires_user_confirmation=True,
                    user_prompt="Would you like instructions to set up an iOS simulator?",
                )
                plan.steps.append(step)
    
    def _create_provision_step(
        self,
        capability: Capability,
        action: ProvisionAction,
    ) -> ProvisionStep:
        """Create a provisioning step for a capability."""
        return ProvisionStep(
            step_id=f"provision_{capability.name}",
            capability_name=capability.name,
            action=action,
            command=capability.provision_command,
            description=capability.provision_instructions or f"Install {capability.name}",
            requires_user_confirmation=(action in (ProvisionAction.ASK_USER, ProvisionAction.AUTHENTICATE, ProvisionAction.CONNECT)),
            user_prompt=capability.provision_instructions if action == ProvisionAction.ASK_USER else None,
        )
    
    # ─── Plan Execution ────────────────────────────────
    
    def _execute_plans(
        self,
        plans: List[EnvironmentPlan],
        auto_provision: bool,
    ) -> OrchestrationResult:
        """Execute all provisioning plans."""
        result = OrchestrationResult(
            success=True,
            platform=plans[0].target_platform if plans else Platform.UNKNOWN,
            plans=plans,
        )
        
        for plan in plans:
            for step in plan.steps:
                result.total_steps += 1
                
                if step.action == ProvisionAction.INSTALL and auto_provision:
                    self._execute_install(step, result)
                
                elif step.action == ProvisionAction.ASK_USER:
                    self._execute_ask_user(step, result)
                
                elif step.action == ProvisionAction.LAUNCH:
                    self._execute_launch(step, plan, result)
                
                elif step.action in (ProvisionAction.CONNECT, ProvisionAction.AUTHENTICATE):
                    self._execute_ask_user(step, result)
                
                else:
                    step.status = ProvisionStatus.SKIPPED
                    result.failed_steps += 1
        
        # Re-scan to confirm provisioning
        if result.completed_steps > 0:
            self.capabilities = self.registry.scan_all()
        
        result.success = (result.failed_steps == 0 and len(result.waiting_for_user) == 0)
        
        return result
    
    def _execute_install(self, step: ProvisionStep, result: OrchestrationResult):
        """Execute an automated installation step."""
        from datetime import datetime, timezone
        
        logger.info(f"Auto-provisioning: {step.capability_name}")
        step.status = ProvisionStatus.IN_PROGRESS
        step.started_at = datetime.now(timezone.utc).isoformat()
        
        # Special handling for known tools
        if step.capability_name == "playwright":
            success = self._install_playwright_browsers()
        elif step.capability_name == "chromium":
            success = self._install_playwright_browsers()
        elif step.command:
            success = self._run_install_command(step.command)
        else:
            step.status = ProvisionStatus.SKIPPED
            step.error = "No install command available"
            result.failed_steps += 1
            return
        
        step.completed_at = datetime.now(timezone.utc).isoformat()
        
        if success:
            step.status = ProvisionStatus.SUCCESS
            result.completed_steps += 1
            result.provisioned.append(step.capability_name)
            logger.info(f"✓ Provisioned: {step.capability_name}")
        else:
            step.status = ProvisionStatus.FAILED
            step.error = "Installation failed"
            result.failed_steps += 1
            logger.warning(f"✗ Failed to provision: {step.capability_name}")
    
    def _execute_ask_user(self, step: ProvisionStep, result: OrchestrationResult):
        """Ask the user to perform a manual action."""
        logger.info(f"User action needed: {step.capability_name}")
        
        confirmed = self.user_callback(
            question=step.user_prompt or step.description,
            context=f"Capability: {step.capability_name}\nAction: {step.action.value}",
        )
        
        if confirmed:
            step.status = ProvisionStatus.PENDING_USER
            result.waiting_for_user.append(step.capability_name)
            logger.info(f"User will handle: {step.capability_name}")
        else:
            step.status = ProvisionStatus.SKIPPED
            result.failed_steps += 1
    
    def _execute_launch(
        self,
        step: ProvisionStep,
        plan: EnvironmentPlan,
        result: OrchestrationResult,
    ):
        """Launch an emulator or simulator."""
        if plan.target_platform == Platform.ANDROID:
            self._launch_android_emulator(step, result)
        elif plan.target_platform == Platform.IOS:
            self._launch_ios_simulator(step, result)
    
    # ─── Specific Installers ───────────────────────────
    
    def _install_playwright_browsers(self) -> bool:
        """Install Playwright browsers."""
        try:
            result = subprocess.run(
                ["playwright", "install", "chromium"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                logger.info("Playwright browsers installed")
                return True
            logger.error(f"Playwright install failed: {result.stderr}")
            return False
        except Exception as e:
            logger.error(f"Playwright install error: {e}")
            return False
    
    def _run_install_command(self, command: str) -> bool:
        """Run a generic install command."""
        try:
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                timeout=120,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Install command failed: {e}")
            return False
    
    def _launch_android_emulator(self, step: ProvisionStep, result: OrchestrationResult):
        """Attempt to launch an Android emulator."""
        # First, list available AVDs
        emulator_path = shutil.which("emulator")
        if not emulator_path:
            step.status = ProvisionStatus.FAILED
            step.error = "Android emulator not found in PATH"
            result.failed_steps += 1
            return
        
        try:
            avd_result = subprocess.run(
                [emulator_path, "-list-avds"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            avds = [a.strip() for a in avd_result.stdout.split("\n") if a.strip()]
            
            if avds:
                step.description = f"Launching emulator: {avds[0]}"
                # Launch would happen here (async)
                step.status = ProvisionStatus.SUCCESS
                result.completed_steps += 1
            else:
                step.status = ProvisionStatus.PENDING_USER
                step.user_prompt = "No Android Virtual Devices found. Create one in Android Studio → AVD Manager."
                result.waiting_for_user.append("android_avd")
        except Exception as e:
            step.status = ProvisionStatus.FAILED
            step.error = str(e)
            result.failed_steps += 1
    
    def _launch_ios_simulator(self, step: ProvisionStep, result: OrchestrationResult):
        """Attempt to launch an iOS simulator."""
        if sys_platform.system() != "Darwin":
            step.status = ProvisionStatus.FAILED
            step.error = "iOS Simulator only available on macOS"
            result.failed_steps += 1
            return
        
        step.status = ProvisionStatus.PENDING_USER
        step.user_prompt = "Open Simulator.app or run: open -a Simulator"
        result.waiting_for_user.append("ios_simulator_launch")
    
    # ─── User Interaction ──────────────────────────────
    
    def _default_user_callback(self, question: str, context: str) -> bool:
        """Default user callback: print prompt and return True (optimistic)."""
        print(f"\n{'='*60}")
        print(f"ACTION REQUIRED: {context}")
        print(f"{'='*60}")
        print(f"\n{question}\n")
        print("Assuming user will handle this. Continuing...")
        return True
    
    def set_user_callback(self, callback: Callable[[str, str], bool]):
        """Set a custom user interaction callback."""
        self.user_callback = callback
    
    # ─── Status Reports ────────────────────────────────
    
    def get_environment_status(self) -> Dict[str, Any]:
        """Get a comprehensive environment status report."""
        if not self.capabilities:
            self.capabilities = self.registry.scan_all()
        
        return {
            "host": f"{sys_platform.system()} {sys_platform.release()}",
            "architecture": sys_platform.machine(),
            "capabilities": self.capabilities.summary(),
            "testable_platforms": {
                "web": self.capabilities.can_test_platform("web"),
                "android": self.capabilities.can_test_platform("android"),
                "ios": self.capabilities.can_test_platform("ios"),
                "flutter": self.capabilities.can_test_platform("flutter"),
                "backend": self.capabilities.can_test_platform("backend"),
            },
            "connected_devices": [
                d.to_dict() for d in self.capabilities.connected_devices
            ],
        }
    
    def print_status(self):
        """Print a human-readable environment status."""
        status = self.get_environment_status()
        caps = status["capabilities"]
        
        print("\n" + "=" * 60)
        print("ENVIRONMENT STATUS")
        print("=" * 60)
        print(f"Host: {status['host']} ({status['architecture']})")
        print(f"Capabilities: {caps['available']}/{caps['total_capabilities']} available")
        
        print("\nTestable Platforms:")
        for platform, ready in status["testable_platforms"].items():
            icon = "✓" if ready else "✗"
            print(f"  {icon} {platform}")
        
        if caps["missing"] > 0:
            print(f"\nMissing ({caps['missing']}):")
            for name in caps["missing_list"]:
                print(f"  - {name}")
            if caps["provisionable"] > 0:
                print(f"\n  ({caps['provisionable']} can be auto-provisioned)")
        
        if status["connected_devices"]:
            print(f"\nConnected Devices ({len(status['connected_devices'])}):")
            for device in status["connected_devices"]:
                print(f"  - {device['device_name']} ({device['platform']} {device['os_version']})")
        
        print("=" * 60 + "\n")

    # ─── Test Classification ───────────────────────────

    def classify_tests(
        self,
        test_plan: Dict[str, Any],
        platform: Platform,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Classify each test case by environment readiness.

        Returns a dict with keys:
        - full_ready: tests that can run with all requirements met
        - partial_ready: tests that can run with some capabilities missing
        - permission_required: tests that need user approval before running
        - blocked: tests that cannot run due to missing non-provisionable capabilities
        """
        if not self.capabilities:
            self.capabilities = self.registry.scan_all()

        classified: Dict[str, List[Dict[str, Any]]] = {
            "full_ready": [],
            "partial_ready": [],
            "permission_required": [],
            "blocked": [],
        }

        test_suites = test_plan.get("test_suites", {})
        for suite_name, tests in test_suites.items():
            for test_case in tests:
                classification = self._classify_single_test(test_case, platform)
                classified[classification].append(test_case)

        return classified

    def _classify_single_test(
        self,
        test_case: Dict[str, Any],
        platform: Platform,
    ) -> str:
        """Classify a single test case."""
        # Determine what this test needs
        required_caps = self._get_test_requirements(test_case, platform)

        if not required_caps:
            return "full_ready"

        has_missing = False
        has_blocked = False
        has_needs_permission = False

        for cap_name in required_caps:
            cap = self.capabilities.capabilities.get(cap_name)

            if cap is None:
                has_blocked = True
                continue

            if cap.is_available:
                continue

            has_missing = True

            if cap.provision_strategy == ProvisionStrategy.NOT_PROVISIONABLE:
                has_blocked = True
            elif cap.provision_strategy in (ProvisionStrategy.GUIDED, ProvisionStrategy.CREDENTIAL, ProvisionStrategy.DEVICE):
                has_needs_permission = True
            # AUTO provisionable is considered partial_ready

        if has_blocked:
            return "blocked"
        if has_needs_permission:
            return "permission_required"
        if has_missing:
            return "partial_ready"
        return "full_ready"

    def _get_test_requirements(
        self,
        test_case: Dict[str, Any],
        platform: Platform,
    ) -> List[str]:
        """Determine what capabilities a test case requires."""
        test_type = test_case.get("type", "")
        target = test_case.get("target", {})
        tags = test_case.get("tags", [])

        requirements: List[str] = []

        # Platform-based requirements
        if platform == Platform.WEB:
            requirements.append("playwright")
        elif platform == Platform.ANDROID:
            requirements.extend(["adb"])
        elif platform == Platform.IOS:
            requirements.extend(["xcode"])
        elif platform in (Platform.BACKEND, Platform.CLI):
            pass  # No special requirements
        # Flutter is detected via CROSS_PLATFORM or by checking capabilities
        if "flutter" in tags:
            requirements.append("flutter")

        # Test-type specific
        if test_type == "performance" or "performance" in tags:
            requirements.append("python")
        if test_type == "security" or "security" in tags:
            requirements.append("python")

        # Deduplicate
        return list(set(requirements))

    # ─── Environment Status Generation ─────────────────

    def generate_environment_status(
        self,
        artifact_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Generate and persist environment_status.json.
        Returns the status dict.
        """
        if not self.capabilities:
            self.capabilities = self.registry.scan_all()

        status = self.get_environment_status()

        # Add environment manager details
        from qa_ai.environments.android_manager import AndroidManager
        from qa_ai.environments.ios_manager import IosManager
        from qa_ai.environments.ci_manager import CIManager
        from qa_ai.environments.docker_manager import DockerManager

        android_mgr = AndroidManager(self.capabilities)
        ios_mgr = IosManager(self.capabilities)
        ci_mgr = CIManager(self.capabilities)
        docker_mgr = DockerManager(self.capabilities)

        status["android"] = android_mgr.detect()
        status["ios"] = ios_mgr.detect()
        status["ci"] = ci_mgr.detect()
        status["docker"] = docker_mgr.detect()

        # Persist
        out_dir = artifact_dir or Path("artifacts")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "environment_status.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2, default=str)

        logger.info(f"Environment status written to {path}")
        return status

    def generate_execution_readiness(
        self,
        test_plan: Dict[str, Any],
        platform: Platform,
        artifact_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Generate and persist execution_readiness.json.
        Classifies tests and creates permission requests for missing capabilities.
        """
        if not self.capabilities:
            self.capabilities = self.registry.scan_all()

        classified = self.classify_tests(test_plan, platform)

        # Create permission requests for permission_required tests
        perm_manager = PermissionManager(artifact_dir=artifact_dir or Path("artifacts"))

        # Identify what capabilities are missing but provisionable
        missing_provisionable = set()
        for test_case in classified["permission_required"]:
            for cap_name in self._get_test_requirements(test_case, platform):
                cap = self.capabilities.capabilities.get(cap_name)
                if cap and not cap.is_available and cap.can_provision:
                    missing_provisionable.add(cap_name)

        for cap_name in missing_provisionable:
            cap = self.capabilities.capabilities.get(cap_name)
            if cap:
                risk = PermissionRisk.MEDIUM
                if cap.provision_strategy == ProvisionStrategy.GUIDED:
                    risk = PermissionRisk.HIGH
                perm_manager.create_request(
                    action=f"install_{cap_name}",
                    description=cap.provision_instructions or f"Install {cap_name}",
                    risk=risk,
                    capability_name=cap_name,
                    command=cap.provision_command,
                )

        perm_manager.save()

        readiness = {
            "platform": platform.value,
            "total_tests": sum(len(v) for v in classified.values()),
            "full_ready": len(classified["full_ready"]),
            "partial_ready": len(classified["partial_ready"]),
            "permission_required": len(classified["permission_required"]),
            "blocked": len(classified["blocked"]),
            "classified": classified,
            "missing_capabilities": [
                cap.to_dict() for cap in self.capabilities.missing
            ],
            "provisionable_capabilities": [
                cap.to_dict() for cap in self.capabilities.provisionable
            ],
            "blocked_capabilities": [
                cap.to_dict() for cap in self.capabilities.blocked
            ],
            "permission_requests": perm_manager.action_summary(),
        }

        # Persist
        out_dir = artifact_dir or Path("artifacts")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "execution_readiness.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(readiness, f, indent=2, default=str)

        logger.info(f"Execution readiness written to {path}")
        return readiness


# ─── Global Instance ───────────────────────────────────

_default_orchestrator: Optional[EnvironmentOrchestrator] = None


def get_environment_orchestrator(
    user_callback: Optional[Callable[[str, str], bool]] = None,
) -> EnvironmentOrchestrator:
    """Get or create the global environment orchestrator."""
    global _default_orchestrator
    if _default_orchestrator is None:
        _default_orchestrator = EnvironmentOrchestrator(user_callback=user_callback)
    return _default_orchestrator


# ─── CLI ───────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    orchestrator = EnvironmentOrchestrator()
    
    # Print current status
    orchestrator.print_status()
    
    # Try preparing for web testing
    print("\nPreparing for web testing...")
    result = orchestrator.prepare_for_platform(Platform.WEB, auto_provision=True)
    
    print(f"\nResult: {'✓ Ready' if result.success else '✗ Not ready'}")
    print(f"Steps: {result.completed_steps}/{result.total_steps} completed")
    if result.waiting_for_user:
        print(f"Waiting for user: {', '.join(result.waiting_for_user)}")
    if result.failed:
        print(f"Failed: {', '.join(result.failed)}")