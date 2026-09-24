"""
permission_manager.py - Manages permission requests for environment provisioning.
No installation or destructive action happens without explicit approval.
"""

from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import logging
import json

logger = logging.getLogger(__name__)


class PermissionRisk(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PermissionStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass
class PermissionRequest:
    """A request to perform an action that requires user approval."""
    request_id: str
    action: str                          # e.g., "install_playwright", "launch_emulator"
    description: str
    risk: PermissionRisk = PermissionRisk.MEDIUM
    capability_name: str = ""
    command: Optional[str] = None        # The command that would be executed
    status: PermissionStatus = PermissionStatus.PENDING
    requested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "action": self.action,
            "description": self.description,
            "risk": self.risk.value,
            "capability_name": self.capability_name,
            "command": self.command,
            "status": self.status.value,
            "requested_at": self.requested_at,
            "resolved_at": self.resolved_at,
            "resolved_by": self.resolved_by,
            "reason": self.reason,
        }


class PermissionManager:
    """
    Manages permission requests for environment provisioning.

    Rules:
    - No installation happens without explicit approval
    - No destructive action happens without explicit approval
    - All requests are persisted to artifacts/permissions.json
    - Risk levels guide the user on what they're approving
    """

    def __init__(self, artifact_dir: Optional[Path] = None):
        self.artifact_dir = artifact_dir or Path("artifacts")
        self._requests: List[PermissionRequest] = []
        self._counter = 0

    def create_request(
        self,
        action: str,
        description: str,
        risk: PermissionRisk = PermissionRisk.MEDIUM,
        capability_name: str = "",
        command: Optional[str] = None,
    ) -> PermissionRequest:
        """Create a new permission request."""
        self._counter += 1
        request_id = f"perm-{self._counter:04d}"

        request = PermissionRequest(
            request_id=request_id,
            action=action,
            description=description,
            risk=risk,
            capability_name=capability_name,
            command=command,
        )
        self._requests.append(request)
        logger.info(f"Permission request created: {request_id} - {action} (risk: {risk.value})")
        return request

    def approve(self, request_id: str, approved_by: str = "user") -> bool:
        """Approve a pending permission request."""
        for req in self._requests:
            if req.request_id == request_id and req.status == PermissionStatus.PENDING:
                req.status = PermissionStatus.APPROVED
                req.resolved_at = datetime.now(timezone.utc).isoformat()
                req.resolved_by = approved_by
                logger.info(f"Permission approved: {request_id} by {approved_by}")
                return True
        return False

    def deny(self, request_id: str, reason: str = "", denied_by: str = "user") -> bool:
        """Deny a pending permission request."""
        for req in self._requests:
            if req.request_id == request_id and req.status == PermissionStatus.PENDING:
                req.status = PermissionStatus.DENIED
                req.resolved_at = datetime.now(timezone.utc).isoformat()
                req.resolved_by = denied_by
                req.reason = reason
                logger.info(f"Permission denied: {request_id} - {reason}")
                return True
        return False

    def get_pending(self) -> List[PermissionRequest]:
        """Get all pending permission requests."""
        return [r for r in self._requests if r.status == PermissionStatus.PENDING]

    def get_approved(self) -> List[PermissionRequest]:
        """Get all approved permission requests."""
        return [r for r in self._requests if r.status == PermissionStatus.APPROVED]

    def get_denied(self) -> List[PermissionRequest]:
        """Get all denied permission requests."""
        return [r for r in self._requests if r.status == PermissionStatus.DENIED]

    def get_request(self, request_id: str) -> Optional[PermissionRequest]:
        """Look up a specific request by ID."""
        for req in self._requests:
            if req.request_id == request_id:
                return req
        return None

    def is_approved(self, action: str, capability_name: str = "") -> bool:
        """Check if a specific action has been approved."""
        for req in self._requests:
            if req.status == PermissionStatus.APPROVED:
                if req.action == action:
                    if not capability_name or req.capability_name == capability_name:
                        return True
        return False

    def action_summary(self) -> Dict[str, Any]:
        """Get a summary of all permission requests by status."""
        return {
            "total": len(self._requests),
            "pending": len(self.get_pending()),
            "approved": len(self.get_approved()),
            "denied": len(self.get_denied()),
            "by_risk": {
                "low": len([r for r in self._requests if r.risk == PermissionRisk.LOW]),
                "medium": len([r for r in self._requests if r.risk == PermissionRisk.MEDIUM]),
                "high": len([r for r in self._requests if r.risk == PermissionRisk.HIGH]),
                "critical": len([r for r in self._requests if r.risk == PermissionRisk.CRITICAL]),
            },
            "requests": [r.to_dict() for r in self._requests],
        }

    def save(self) -> Path:
        """Persist all permission requests to artifacts/permissions.json."""
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        path = self.artifact_dir / "permissions.json"
        data = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "summary": self.action_summary(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.debug(f"Permissions saved to {path}")
        return path

    def load(self) -> bool:
        """Load permission requests from artifacts/permissions.json."""
        path = self.artifact_dir / "permissions.json"
        if not path.exists():
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            requests_data = data.get("summary", {}).get("requests", [])
            self._requests = []
            self._counter = 0

            for rd in requests_data:
                req = PermissionRequest(
                    request_id=rd["request_id"],
                    action=rd["action"],
                    description=rd["description"],
                    risk=PermissionRisk(rd["risk"]),
                    capability_name=rd.get("capability_name", ""),
                    command=rd.get("command"),
                    status=PermissionStatus(rd["status"]),
                    requested_at=rd.get("requested_at", ""),
                    resolved_at=rd.get("resolved_at"),
                    resolved_by=rd.get("resolved_by"),
                    reason=rd.get("reason"),
                )
                self._requests.append(req)
                # Extract counter from request_id
                try:
                    num = int(req.request_id.split("-")[1])
                    self._counter = max(self._counter, num)
                except (IndexError, ValueError):
                    pass

            return True
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load permissions: {e}")
            return False

    def clear(self):
        """Clear all permission requests."""
        self._requests = []
        self._counter = 0
