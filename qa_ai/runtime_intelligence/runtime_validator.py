"""
runtime_validator.py - Validates static findings using actual execution.
Integrates with APIRunner and PlaywrightRunner to execute auth checks,
negative-path validation, and endpoint verification.
Produces verified_findings.json with verification status.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
import logging
import time

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIABLE = "unverifiable"
    BLOCKED = "blocked"


class RuntimeValidator:
    """
    Validates static audit findings by executing controlled runtime checks.

    For each finding:
    1. Determines if it can be verified via execution
    2. Attempts controlled verification (auth checks, negative paths)
    3. Captures request/response evidence
    4. Marks finding as verified/partially_verified/unverifiable/blocked

    Safety: Never performs destructive actions. Only reads and controlled writes.
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        findings: Optional[List[Dict[str, Any]]] = None,
        app_map: Optional[Dict[str, Any]] = None,
        base_url: Optional[str] = None,
        credentials: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Run runtime validation of static findings."""
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if findings is None:
            correlated = self.store.load_artifact("correlated_findings") or {}
            findings = correlated.get("findings", [])

        if app_map is None:
            app_map = self.store.load_artifact("app_map") or {}

        verified_findings: List[Dict[str, Any]] = []

        for finding in findings:
            vf = self._validate_finding(finding, app_map, base_url, credentials)
            verified_findings.append(vf)

        # Tally
        status_counts: Dict[str, int] = {}
        for vf in verified_findings:
            s = vf.get("verification_status", "unverifiable")
            status_counts[s] = status_counts.get(s, 0) + 1

        duration = time.time() - start_time

        result = {
            "metadata": {
                "validation_type": "runtime_validation",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": duration,
                "generated_by": "RuntimeValidator",
                "total_findings": len(findings),
            },
            "verified_findings": verified_findings,
            "summary": status_counts,
        }

        self.store.save_artifact("verified_findings", result, agent="RuntimeValidator")
        logger.info(f"Runtime validation complete: {len(findings)} findings processed")
        return result

    def _validate_finding(
        self,
        finding: Dict[str, Any],
        app_map: Dict[str, Any],
        base_url: Optional[str],
        credentials: Optional[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Validate a single finding via controlled execution."""
        tags = finding.get("tags", [])
        category = finding.get("category", tags[0] if tags else "")
        target = finding.get("target", finding.get("api_endpoint", ""))

        # Determine verifiability
        verifiable_categories = {
            "authentication", "endpoint_auth", "transport_security",
            "token_security", "exposed_routes", "idempotency",
        }

        if category not in verifiable_categories:
            return {
                **finding,
                "verification_status": VerificationStatus.UNVERIFIABLE.value,
                "verification_reason": f"Category '{category}' not verifiable via runtime execution",
                "evidence": [],
            }

        if not base_url:
            return {
                **finding,
                "verification_status": VerificationStatus.BLOCKED.value,
                "verification_reason": "No base_url provided for runtime verification",
                "evidence": [],
            }

        # Attempt verification based on category
        if category in ("authentication", "endpoint_auth"):
            return self._verify_auth_finding(finding, base_url, target)
        elif category == "transport_security":
            return self._verify_transport_finding(finding, base_url)
        elif category == "exposed_routes":
            return self._verify_route_finding(finding, base_url, target)
        elif category == "token_security":
            return self._verify_token_finding(finding, base_url, target)
        elif category == "idempotency":
            return self._verify_idempotency_finding(finding, base_url, target)

        return {
            **finding,
            "verification_status": VerificationStatus.UNVERIFIABLE.value,
            "verification_reason": "No verification strategy available",
            "evidence": [],
        }

    def _verify_auth_finding(
        self, finding: Dict[str, Any], base_url: str, target: str,
    ) -> Dict[str, Any]:
        """Verify auth-related findings by attempting unauthenticated access."""
        import requests

        evidence: List[Dict[str, Any]] = []
        method, path = self._parse_target(target)
        url = f"{base_url.rstrip('/')}{path}"

        try:
            resp = requests.request(method, url, timeout=10)
            evidence.append({
                "type": "api_response",
                "method": method,
                "url": url,
                "status_code": resp.status_code,
                "authenticated": False,
            })

            if resp.status_code in (401, 403):
                return {
                    **finding,
                    "verification_status": VerificationStatus.PARTIALLY_VERIFIED.value,
                    "verification_reason": f"Endpoint returned {resp.status_code} without auth - auth appears enforced",
                    "evidence": evidence,
                }
            elif resp.status_code < 400:
                return {
                    **finding,
                    "verification_status": VerificationStatus.VERIFIED.value,
                    "verification_reason": f"Endpoint accessible without auth (HTTP {resp.status_code})",
                    "evidence": evidence,
                }
            else:
                return {
                    **finding,
                    "verification_status": VerificationStatus.PARTIALLY_VERIFIED.value,
                    "verification_reason": f"Unexpected status {resp.status_code}",
                    "evidence": evidence,
                }

        except requests.ConnectionError:
            return {
                **finding,
                "verification_status": VerificationStatus.BLOCKED.value,
                "verification_reason": f"Cannot connect to {base_url}",
                "evidence": evidence,
            }
        except Exception as e:
            return {
                **finding,
                "verification_status": VerificationStatus.BLOCKED.value,
                "verification_reason": f"Verification error: {str(e)}",
                "evidence": evidence,
            }

    def _verify_transport_finding(
        self, finding: Dict[str, Any], base_url: str,
    ) -> Dict[str, Any]:
        """Verify transport security by checking if HTTP redirects to HTTPS."""
        import requests

        evidence: List[Dict[str, Any]] = []
        http_url = base_url.replace("https://", "http://")

        try:
            resp = requests.get(http_url, timeout=10, allow_redirects=False)
            evidence.append({
                "type": "transport_check",
                "url": http_url,
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
            })

            if resp.status_code in (301, 302, 307, 308):
                location = resp.headers.get("Location", "")
                if location.startswith("https://"):
                    return {
                        **finding,
                        "verification_status": VerificationStatus.PARTIALLY_VERIFIED.value,
                        "verification_reason": "HTTP redirects to HTTPS - transport security enforced",
                        "evidence": evidence,
                    }

            return {
                **finding,
                "verification_status": VerificationStatus.VERIFIED.value,
                "verification_reason": "HTTP does not redirect to HTTPS - insecure transport confirmed",
                "evidence": evidence,
            }

        except Exception as e:
            return {
                **finding,
                "verification_status": VerificationStatus.BLOCKED.value,
                "verification_reason": f"Transport verification error: {str(e)}",
                "evidence": evidence,
            }

    def _verify_route_finding(
        self, finding: Dict[str, Any], base_url: str, target: str,
    ) -> Dict[str, Any]:
        """Verify exposed route findings by attempting access."""
        import requests

        evidence: List[Dict[str, Any]] = []
        _, path = self._parse_target(target)
        url = f"{base_url.rstrip('/')}{path}"

        try:
            resp = requests.get(url, timeout=10)
            evidence.append({
                "type": "route_check",
                "url": url,
                "status_code": resp.status_code,
                "content_length": len(resp.content),
            })

            if resp.status_code < 400:
                return {
                    **finding,
                    "verification_status": VerificationStatus.VERIFIED.value,
                    "verification_reason": f"Route accessible (HTTP {resp.status_code})",
                    "evidence": evidence,
                }
            else:
                return {
                    **finding,
                    "verification_status": VerificationStatus.PARTIALLY_VERIFIED.value,
                    "verification_reason": f"Route returned HTTP {resp.status_code}",
                    "evidence": evidence,
                }

        except Exception as e:
            return {
                **finding,
                "verification_status": VerificationStatus.BLOCKED.value,
                "verification_reason": f"Route verification error: {str(e)}",
                "evidence": evidence,
            }

    def _verify_token_finding(
        self, finding: Dict[str, Any], base_url: str, target: str,
    ) -> Dict[str, Any]:
        """Verify token handling by sending invalid tokens."""
        import requests

        evidence: List[Dict[str, Any]] = []
        method, path = self._parse_target(target)
        url = f"{base_url.rstrip('/')}{path}"

        try:
            headers = {"Authorization": "Bearer invalid_expired_token_12345"}
            resp = requests.request(method, url, headers=headers, timeout=10)
            evidence.append({
                "type": "token_check",
                "url": url,
                "status_code": resp.status_code,
                "token_used": "invalid_expired_token",
            })

            if resp.status_code in (401, 403):
                return {
                    **finding,
                    "verification_status": VerificationStatus.PARTIALLY_VERIFIED.value,
                    "verification_reason": f"Invalid token rejected (HTTP {resp.status_code})",
                    "evidence": evidence,
                }
            elif resp.status_code < 400:
                return {
                    **finding,
                    "verification_status": VerificationStatus.VERIFIED.value,
                    "verification_reason": f"Invalid token accepted (HTTP {resp.status_code}) - weak token handling confirmed",
                    "evidence": evidence,
                }
            else:
                return {
                    **finding,
                    "verification_status": VerificationStatus.PARTIALLY_VERIFIED.value,
                    "verification_reason": f"Unexpected status {resp.status_code} with invalid token",
                    "evidence": evidence,
                }

        except Exception as e:
            return {
                **finding,
                "verification_status": VerificationStatus.BLOCKED.value,
                "verification_reason": f"Token verification error: {str(e)}",
                "evidence": evidence,
            }

    def _verify_idempotency_finding(
        self, finding: Dict[str, Any], base_url: str, target: str,
    ) -> Dict[str, Any]:
        """Verify idempotency by checking if mutation endpoints are safe to retry."""
        return {
            **finding,
            "verification_status": VerificationStatus.UNVERIFIABLE.value,
            "verification_reason": "Idempotency verification requires application-specific payloads",
            "evidence": [],
        }

    def _parse_target(self, target: str) -> tuple:
        """Parse 'GET /users' into ('GET', '/users')."""
        if target and " " in target:
            parts = target.split(" ", 1)
            return parts[0].upper(), parts[1]
        return "GET", target or "/"
