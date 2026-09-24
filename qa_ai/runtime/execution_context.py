"""
execution_context.py - Immutable context for every audit run.
Tracks platform, device, environment, network, build type, trigger source.
Every agent reads this to understand what environment it's operating in.
"""

from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging
import uuid
import platform as sys_platform
import socket
import getpass
import json

logger = logging.getLogger(__name__)


# ─── Enums ─────────────────────────────────────────────

class Platform(Enum):
    """Target platform being audited."""
    WEB = "web"
    ANDROID = "android"
    IOS = "ios"
    MACOS = "macos"
    WINDOWS = "windows"
    LINUX = "linux"
    BACKEND = "backend"
    CLI = "cli"
    LIBRARY = "library"
    EXTENSION = "extension"
    DESKTOP = "desktop"
    CROSS_PLATFORM = "cross_platform"
    UNKNOWN = "unknown"


class Environment(Enum):
    """Execution environment type."""
    LOCAL = "local"
    EMULATOR = "emulator"
    SIMULATOR = "simulator"
    PHYSICAL_DEVICE = "physical_device"
    DOCKER = "docker"
    CI = "ci"
    SAAS = "saas"
    CLOUD = "cloud"
    STAGING = "staging"
    PRODUCTION = "production"
    UNKNOWN = "unknown"


class NetworkState(Enum):
    """Network condition for the audit run."""
    ONLINE = "online"
    OFFLINE = "offline"
    SLOW = "slow"
    THROTTLED = "throttled"
    INTERMITTENT = "intermittent"
    AIRPLANE_MODE = "airplane_mode"
    UNKNOWN = "unknown"


class BuildType(Enum):
    """Build configuration being tested."""
    DEBUG = "debug"
    RELEASE = "release"
    PROFILE = "profile"
    STAGING = "staging"
    PRODUCTION = "production"
    UNKNOWN = "unknown"


class TriggerSource(Enum):
    """What triggered this audit run."""
    CLI = "cli"
    CI_PIPELINE = "ci_pipeline"
    GIT_HOOK = "git_hook"
    SCHEDULED = "scheduled"
    API_CALL = "api_call"
    MANUAL = "manual"
    PRE_RELEASE = "pre_release"
    POST_DEPLOY = "post_deploy"
    UNKNOWN = "unknown"


class AuditPhase(Enum):
    """Current phase of the audit."""
    INTAKE = "intake"
    DISCOVERY = "discovery"
    INTELLIGENCE = "intelligence"
    PLANNING = "planning"
    ORCHESTRATION = "orchestration"
    EXECUTION = "execution"
    EXPLORATION = "exploration"
    AUDIT = "audit"
    EVIDENCE = "evidence"
    ANALYSIS = "analysis"
    REPORTING = "reporting"
    COMPLETE = "complete"
    FAILED = "failed"


# ─── Data Models ───────────────────────────────────────

@dataclass
class DeviceInfo:
    """Information about the device running or being tested."""
    device_name: str = ""
    device_model: str = ""
    device_id: str = ""
    os_name: str = ""
    os_version: str = ""
    screen_width: int = 0
    screen_height: int = 0
    screen_density: float = 0.0
    is_physical: bool = False
    is_rooted: bool = False
    locale: str = "en_US"
    timezone: str = "UTC"
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NetworkInfo:
    """Network conditions during the audit."""
    state: NetworkState = NetworkState.UNKNOWN
    is_online: bool = True
    latency_ms: float = 0.0
    bandwidth_mbps: float = 0.0
    packet_loss_percent: float = 0.0
    proxy_enabled: bool = False
    vpn_enabled: bool = False
    firewall_active: bool = False
    
    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "is_online": self.is_online,
            "latency_ms": self.latency_ms,
            "bandwidth_mbps": self.bandwidth_mbps,
            "packet_loss_percent": self.packet_loss_percent,
            "proxy_enabled": self.proxy_enabled,
            "vpn_enabled": self.vpn_enabled,
            "firewall_active": self.firewall_active,
        }


@dataclass
class AuditMetadata:
    """Additional metadata about the audit run."""
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None
    git_tag: Optional[str] = None
    ci_job_id: Optional[str] = None
    ci_pipeline_id: Optional[str] = None
    pr_number: Optional[str] = None
    release_version: Optional[str] = None
    custom_tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        result = {
            "git_commit": self.git_commit,
            "git_branch": self.git_branch,
            "git_tag": self.git_tag,
            "ci_job_id": self.ci_job_id,
            "ci_pipeline_id": self.ci_pipeline_id,
            "pr_number": self.pr_number,
            "release_version": self.release_version,
            "custom_tags": self.custom_tags,
        }
        return {k: v for k, v in result.items() if v is not None or k == "custom_tags"}


@dataclass
class CredentialRequirement:
    """A credential or permission needed for the audit."""
    name: str
    description: str
    credential_type: str  # "api_key", "password", "token", "certificate", "device"
    is_satisfied: bool = False
    provided_by: Optional[str] = None
    provided_at: Optional[str] = None
    expires_at: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "credential_type": self.credential_type,
            "is_satisfied": self.is_satisfied,
            "provided_by": self.provided_by,
            "provided_at": self.provided_at,
            "expires_at": self.expires_at,
        }


@dataclass
class ExecutionContext:
    """
    Complete execution context for a single audit run.
    
    This is immutable after creation. Every agent receives this context
    and uses it to understand the environment it's operating in.
    
    Critical for:
    - Regression history (compare runs across time)
    - RCA (what environment did this failure occur in?)
    - Evidence provenance (what device/screen/network produced this screenshot?)
    """
    
    # Identity
    run_id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex[:12]}")
    app_name: str = ""
    app_path: str = ""
    app_version: Optional[str] = None
    
    # Platform
    platform: Platform = Platform.UNKNOWN
    target_platforms: List[Platform] = field(default_factory=list)
    
    # Environment
    environment: Environment = Environment.UNKNOWN
    device: DeviceInfo = field(default_factory=DeviceInfo)
    network: NetworkInfo = field(default_factory=NetworkInfo)
    
    # Build
    build_type: BuildType = BuildType.UNKNOWN
    build_id: Optional[str] = None
    
    # Trigger
    trigger_source: TriggerSource = TriggerSource.UNKNOWN
    triggered_by: str = ""  # User or system that triggered this
    triggered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Runtime
    host_machine: str = field(default_factory=socket.gethostname)
    host_user: str = field(default_factory=getpass.getuser)
    host_os: str = field(default_factory=lambda: f"{sys_platform.system()} {sys_platform.release()}")
    python_version: str = field(default_factory=lambda: sys_platform.python_version())
    
    # Metadata
    audit_metadata: AuditMetadata = field(default_factory=AuditMetadata)
    
    # Credentials & Permissions
    required_credentials: List[CredentialRequirement] = field(default_factory=list)
    satisfied_credentials: List[str] = field(default_factory=list)
    
    # Phase tracking
    current_phase: AuditPhase = AuditPhase.INTAKE
    phase_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Timing
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    # Results
    total_agents_run: int = 0
    agents_succeeded: int = 0
    agents_failed: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "run_id": self.run_id,
            "app_name": self.app_name,
            "app_path": self.app_path,
            "app_version": self.app_version,
            "platform": self.platform.value,
            "target_platforms": [p.value for p in self.target_platforms],
            "environment": self.environment.value,
            "device": self.device.to_dict(),
            "network": self.network.to_dict(),
            "build_type": self.build_type.value,
            "build_id": self.build_id,
            "trigger_source": self.trigger_source.value,
            "triggered_by": self.triggered_by,
            "triggered_at": self.triggered_at,
            "host_machine": self.host_machine,
            "host_user": self.host_user,
            "host_os": self.host_os,
            "python_version": self.python_version,
            "audit_metadata": self.audit_metadata.to_dict(),
            "required_credentials": [c.to_dict() for c in self.required_credentials],
            "satisfied_credentials": self.satisfied_credentials,
            "current_phase": self.current_phase.value,
            "phase_history": self.phase_history,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "total_agents_run": self.total_agents_run,
            "agents_succeeded": self.agents_succeeded,
            "agents_failed": self.agents_failed,
        }
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    # ─── Phase Tracking ────────────────────────────────
    
    def transition_to(self, phase: AuditPhase):
        """Record a phase transition."""
        now = datetime.now(timezone.utc).isoformat()
        
        self.phase_history.append({
            "from_phase": self.current_phase.value,
            "to_phase": phase.value,
            "transitioned_at": now,
        })
        
        self.current_phase = phase
        
        if phase == AuditPhase.COMPLETE or phase == AuditPhase.FAILED:
            self.completed_at = now
            if self.started_at:
                try:
                    start = datetime.fromisoformat(self.started_at)
                    end = datetime.fromisoformat(now)
                    self.duration_seconds = (end - start).total_seconds()
                except Exception as e:
                    logger.debug("Failed to compute audit duration: %s", e)
    
    def mark_complete(self):
        """Mark the audit as successfully completed."""
        self.transition_to(AuditPhase.COMPLETE)
    
    def mark_failed(self, reason: str = ""):
        """Mark the audit as failed."""
        self.phase_history.append({
            "failure_reason": reason,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        })
        self.transition_to(AuditPhase.FAILED)
    
    # ─── Agent Tracking ────────────────────────────────
    
    def record_agent_run(self, agent_name: str, success: bool):
        """Record that an agent ran and whether it succeeded."""
        self.total_agents_run += 1
        if success:
            self.agents_succeeded += 1
        else:
            self.agents_failed += 1
        
        self.phase_history.append({
            "agent": agent_name,
            "success": success,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
    
    # ─── Credential Management ─────────────────────────
    
    def add_credential_requirement(
        self,
        name: str,
        description: str,
        credential_type: str,
    ) -> CredentialRequirement:
        """Register a credential requirement for this audit."""
        cred = CredentialRequirement(
            name=name,
            description=description,
            credential_type=credential_type,
        )
        self.required_credentials.append(cred)
        return cred
    
    def satisfy_credential(self, name: str, provided_by: str = "user"):
        """Mark a credential as satisfied."""
        for cred in self.required_credentials:
            if cred.name == name:
                cred.is_satisfied = True
                cred.provided_by = provided_by
                cred.provided_at = datetime.now(timezone.utc).isoformat()
                
                if name not in self.satisfied_credentials:
                    self.satisfied_credentials.append(name)
                return
    
    def unsatisfied_credentials(self) -> List[CredentialRequirement]:
        """Get list of credentials still needed."""
        return [c for c in self.required_credentials if not c.is_satisfied]
    
    def all_credentials_satisfied(self) -> bool:
        """Check if all required credentials are available."""
        return len(self.unsatisfied_credentials()) == 0
    
    # ─── Environment Detection ─────────────────────────
    
    def detect_environment(self):
        """
        Auto-detect the execution environment.
        Called once at the start of an audit run.
        """
        import os
        
        # Detect CI environment
        if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS") or os.environ.get("GITLAB_CI"):
            self.environment = Environment.CI
            return
        
        # Detect Docker
        if os.path.exists("/.dockerenv") or "docker" in (os.environ.get("container") or ""):
            self.environment = Environment.DOCKER
            return
        
        # Default
        self.environment = Environment.LOCAL
    
    def __repr__(self) -> str:
        return (
            f"ExecutionContext(run_id={self.run_id}, "
            f"app={self.app_name}, "
            f"platform={self.platform.value}, "
            f"env={self.environment.value}, "
            f"phase={self.current_phase.value})"
        )


# ─── Factory ───────────────────────────────────────────

def create_execution_context(
    app_name: str,
    app_path: str,
    platform: Platform = Platform.UNKNOWN,
    environment: Optional[Environment] = None,
    build_type: BuildType = BuildType.UNKNOWN,
    trigger_source: TriggerSource = TriggerSource.CLI,
    triggered_by: str = "",
    app_version: Optional[str] = None,
    git_commit: Optional[str] = None,
    git_branch: Optional[str] = None,
) -> ExecutionContext:
    """
    Create a new execution context for an audit run.
    
    Args:
        app_name: Name of the application being audited
        app_path: Path to the application source
        platform: Target platform
        environment: Execution environment (auto-detected if None)
        build_type: Build configuration
        trigger_source: What triggered this audit
        triggered_by: Who/what triggered it
        app_version: Version of the app being tested
        git_commit: Git commit hash
        git_branch: Git branch name
        
    Returns:
        Configured ExecutionContext
    """
    ctx = ExecutionContext(
        app_name=app_name,
        app_path=app_path,
        platform=platform,
        build_type=build_type,
        trigger_source=trigger_source,
        triggered_by=triggered_by or getpass.getuser(),
        app_version=app_version,
        audit_metadata=AuditMetadata(
            git_commit=git_commit,
            git_branch=git_branch,
        ),
    )
    
    # Auto-detect environment if not specified
    if environment:
        ctx.environment = environment
    else:
        ctx.detect_environment()
    
    return ctx


def load_execution_context(data: Dict[str, Any]) -> ExecutionContext:
    """Reconstruct an ExecutionContext from a dictionary (e.g., from JSON)."""
    ctx = ExecutionContext()
    
    # Identity
    ctx.run_id = data.get("run_id", ctx.run_id)
    ctx.app_name = data.get("app_name", "")
    ctx.app_path = data.get("app_path", "")
    ctx.app_version = data.get("app_version")
    
    # Platform
    try:
        ctx.platform = Platform(data.get("platform", "unknown"))
    except ValueError:
        ctx.platform = Platform.UNKNOWN
    
    ctx.target_platforms = [
        Platform(p) for p in data.get("target_platforms", [])
    ]
    
    # Environment
    try:
        ctx.environment = Environment(data.get("environment", "unknown"))
    except ValueError:
        ctx.environment = Environment.UNKNOWN
    
    # Device
    device_data = data.get("device", {})
    ctx.device = DeviceInfo(**device_data) if device_data else DeviceInfo()
    
    # Network
    network_data = data.get("network", {})
    if network_data:
        try:
            network_state = NetworkState(network_data.pop("state", "unknown"))
        except ValueError:
            network_state = NetworkState.UNKNOWN
        ctx.network = NetworkInfo(state=network_state, **network_data)
    
    # Build
    try:
        ctx.build_type = BuildType(data.get("build_type", "unknown"))
    except ValueError:
        ctx.build_type = BuildType.UNKNOWN
    
    ctx.build_id = data.get("build_id")
    
    # Trigger
    try:
        ctx.trigger_source = TriggerSource(data.get("trigger_source", "unknown"))
    except ValueError:
        ctx.trigger_source = TriggerSource.UNKNOWN
    
    ctx.triggered_by = data.get("triggered_by", "")
    ctx.triggered_at = data.get("triggered_at", "")
    
    # Timing
    ctx.started_at = data.get("started_at", "")
    ctx.completed_at = data.get("completed_at")
    ctx.duration_seconds = data.get("duration_seconds")
    
    # Results
    ctx.total_agents_run = data.get("total_agents_run", 0)
    ctx.agents_succeeded = data.get("agents_succeeded", 0)
    ctx.agents_failed = data.get("agents_failed", 0)
    
    # Current phase
    try:
        ctx.current_phase = AuditPhase(data.get("current_phase", "intake"))
    except ValueError:
        ctx.current_phase = AuditPhase.INTAKE
    
    ctx.phase_history = data.get("phase_history", [])
    
    return ctx