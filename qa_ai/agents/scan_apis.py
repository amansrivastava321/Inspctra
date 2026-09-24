"""
scan_apis.py - Production-grade API endpoint scanner.
Uses file_walker for filtered iteration, deduplication,
line number tracking, and confidence scoring.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
import re
import json
import hashlib
import logging

from qa_ai.agents.file_walker import iter_source_files

logger = logging.getLogger(__name__)


# ─── Data Models ───────────────────────────────────────

class HttpMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"


class ApiType(Enum):
    REST = "rest"
    GRAPHQL = "graphql"
    WEBSOCKET = "websocket"
    GRPC = "grpc"
    INTERNAL = "internal"
    EXTERNAL = "external"


@dataclass
class ApiEndpoint:
    method: Optional[HttpMethod] = None
    path: str = ""
    full_url: Optional[str] = None
    base_url: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    api_type: ApiType = ApiType.REST
    auth_required: bool = False
    auth_type: Optional[str] = None
    parameters: list = field(default_factory=list)
    query_params: list = field(default_factory=list)
    request_body: Optional[dict] = None
    response_type: Optional[str] = None
    headers: list = field(default_factory=list)
    error_handling: bool = False
    rate_limited: bool = False
    deprecated: bool = False
    called_by_screens: list = field(default_factory=list)
    confidence: float = 0.0

    @property
    def unique_key(self) -> str:
        raw = f"{self.method.value if self.method else 'UNKNOWN'}::{self.path}::{self.file_path}"
        return hashlib.md5(raw.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "method": self.method.value if self.method else None,
            "path": self.path,
            "full_url": self.full_url,
            "base_url": self.base_url,
            "file": self.file_path,
            "line": self.line_number,
            "type": self.api_type.value,
            "auth_required": self.auth_required,
            "auth_type": self.auth_type,
            "params": self.parameters,
            "query": self.query_params,
            "request_body": self.request_body,
            "response_type": self.response_type,
            "headers": self.headers,
            "error_handling": self.error_handling,
            "rate_limited": self.rate_limited,
            "deprecated": self.deprecated,
            "called_by": self.called_by_screens,
            "confidence": self.confidence,
        }


# ─── Deduplication Helper ──────────────────────────────

def _deduplicate_endpoints(endpoints: List[ApiEndpoint]) -> List[ApiEndpoint]:
    """Remove duplicate endpoints. Keeps the one with highest confidence."""
    seen: Dict[str, ApiEndpoint] = {}

    for ep in endpoints:
        key = ep.unique_key
        if key in seen:
            # Keep the one with higher confidence
            if ep.confidence > seen[key].confidence:
                seen[key] = ep
        else:
            seen[key] = ep

    return list(seen.values())


def _normalize_path(path: str) -> str:
    """Normalize API paths: trailing slash, double slashes, etc."""
    path = path.strip()
    path = re.sub(r'/+', '/', path)  # Collapse double slashes
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return path


# ─── Main Scanner ────────────────────────────────────

class ApiScanner:
    """Production-grade API scanner using file_walker."""

    def __init__(self, app_path: Path, stack_info: dict = None):
        self.app_path = Path(app_path)
        self.stack = stack_info or {}
        self.endpoints: List[ApiEndpoint] = []
        self.backend_endpoints: List[ApiEndpoint] = []
        self.frontend_calls: List[ApiEndpoint] = []

    def scan_all(self) -> dict:
        framework = self.stack.get("framework", "unknown")
        language = self.stack.get("language", "unknown")

        # ─── Backend scanning ────────────────────
        backend_scanners = {
            "fastapi": self._scan_python_backend,
            "django": self._scan_python_backend,
            "flask": self._scan_python_backend,
            "express": self._scan_node_backend,
            "nestjs": self._scan_node_backend,
            "rails": self._scan_rails_backend,
            "gin": self._scan_go_backend,
            "spring_boot": self._scan_spring_backend,
            "laravel": self._scan_laravel_backend,
            "dotnet": self._scan_dotnet_backend,
        }

        scanner = backend_scanners.get(framework)
        if scanner:
            scanner()

        # ─── Frontend scanning ────────────────────
        frontend_scanners = {
            "dart": self._scan_flutter_services,
            "javascript": self._scan_js_services,
            "typescript": self._scan_js_services,
            "swift": self._scan_swift_services,
            "kotlin": self._scan_kotlin_services,
        }

        scanner = frontend_scanners.get(language)
        if scanner:
            scanner()

        # ─── Special protocols ────────────────────
        self._scan_graphql()
        self._scan_websockets()

        # ─── Post-processing ──────────────────────
        self.backend_endpoints = _deduplicate_endpoints(self.backend_endpoints)
        self.frontend_calls = _deduplicate_endpoints(self.frontend_calls)
        self.endpoints = _deduplicate_endpoints(self.endpoints)

        # Link frontend calls to backend endpoints
        self._link_frontend_to_backend()

        # Calculate confidence for any unscored endpoints
        for ep in self.endpoints:
            if ep.confidence == 0.0:
                ep.confidence = self._default_confidence(ep)

        return {
            "backend_endpoints": [e.to_dict() for e in self.backend_endpoints],
            "frontend_calls": [e.to_dict() for e in self.frontend_calls],
            "all_endpoints": [e.to_dict() for e in self.endpoints],
            "total_backend": len(self.backend_endpoints),
            "total_frontend": len(self.frontend_calls),
            "auth_protected": len([e for e in self.endpoints if e.auth_required]),
            "unprotected": len([e for e in self.endpoints if not e.auth_required]),
            "external_services": list(set(
                e.base_url for e in self.endpoints
                if e.api_type == ApiType.EXTERNAL and e.base_url
            )),
        }

    # ─── Confidence Helpers ──────────────────────────

    def _default_confidence(self, endpoint: ApiEndpoint) -> float:
        """Default confidence based on endpoint properties."""
        score = 0.5
        if endpoint.method:
            score += 0.2
        if endpoint.path and endpoint.path != "/":
            score += 0.1
        if endpoint.file_path:
            score += 0.1
        if endpoint.line_number:
            score += 0.1
        return min(score, 1.0)

    def _link_frontend_to_backend(self):
        """Link frontend API calls to backend endpoint definitions."""
        backend_paths = {ep.path: ep for ep in self.backend_endpoints if ep.path}

        for fc in self.frontend_calls:
            # Try exact path match
            if fc.path in backend_paths:
                be = backend_paths[fc.path]
                be.called_by_screens.append(fc.file_path or "unknown")
                fc.confidence = 0.9
                continue

            # Try normalized match
            norm_path = _normalize_path(fc.path)
            if norm_path in backend_paths:
                be = backend_paths[norm_path]
                be.called_by_screens.append(fc.file_path or "unknown")
                fc.confidence = 0.85
                continue

    # ─── Python Backend ─────────────────────────────

    def _scan_python_backend(self):
        for py_file in iter_source_files(self.app_path):
            try:
                content = py_file.read_text(errors="ignore")
                rel_path = str(py_file.relative_to(self.app_path))
                lines = content.split("\n")

                # FastAPI
                for i, line in enumerate(lines):
                    match = re.search(
                        r'@(?:\w+\.)?(get|post|put|delete|patch|options|head)\s*\(\s*["\']([^"\']+)["\']',
                        line
                    )
                    if match:
                        method_str, path = match.group(1), match.group(2)
                        endpoint = ApiEndpoint(
                            method=HttpMethod(method_str.upper()),
                            path=_normalize_path(path),
                            file_path=rel_path,
                            line_number=i + 1,
                            api_type=ApiType.REST,
                            confidence=0.8,
                        )
                        # Auth check
                        if any(kw in content.lower() for kw in ['depends', 'jwt', 'token', 'oauth']):
                            endpoint.auth_required = True
                        params = re.findall(r'\{(\w+)\}', path)
                        endpoint.parameters = params
                        self.backend_endpoints.append(endpoint)
                        self.endpoints.append(endpoint)

                # Django
                for i, line in enumerate(lines):
                    match = re.search(
                        r'(?:path|re_path|url)\s*\(\s*["\']([^"\']+)["\']',
                        line
                    )
                    if match:
                        path = match.group(1)
                        endpoint = ApiEndpoint(
                            path=_normalize_path(path),
                            file_path=rel_path,
                            line_number=i + 1,
                            api_type=ApiType.REST,
                            confidence=0.7,
                        )
                        if "login_required" in content:
                            endpoint.auth_required = True
                        self.backend_endpoints.append(endpoint)
                        self.endpoints.append(endpoint)

                # Flask
                for i, line in enumerate(lines):
                    match = re.search(r'@\w+\.route\s*\(\s*["\']([^"\']+)["\']', line)
                    if match:
                        path = match.group(1)
                        methods_match = re.search(r'methods\s*=\s*\[(.*?)\]', content)
                        method_str = methods_match.group(1).strip("'\" ") if methods_match else "GET"

                        endpoint = ApiEndpoint(
                            method=HttpMethod(method_str.upper()),
                            path=_normalize_path(path),
                            file_path=rel_path,
                            line_number=i + 1,
                            api_type=ApiType.REST,
                            confidence=0.75,
                        )
                        self.backend_endpoints.append(endpoint)
                        self.endpoints.append(endpoint)

            except Exception as e:
                logger.debug(f"Error scanning {py_file}: {e}")
                continue

    # ─── Node.js Backend ────────────────────────────

    def _scan_node_backend(self):
        for js_file in iter_source_files(self.app_path):
            try:
                content = js_file.read_text(errors="ignore")
                rel_path = str(js_file.relative_to(self.app_path))
                lines = content.split("\n")

                # Express
                for i, line in enumerate(lines):
                    match = re.search(
                        r'(?:app|router)\.(get|post|put|delete|patch|use|all)\s*\(\s*["\'`]([^"\'`]+)["\'`]',
                        line
                    )
                    if match:
                        method_str, path = match.group(1), match.group(2)
                        endpoint = ApiEndpoint(
                            method=HttpMethod(method_str.upper()) if method_str != "use" else None,
                            path=_normalize_path(path),
                            file_path=rel_path,
                            line_number=i + 1,
                            api_type=ApiType.REST,
                            confidence=0.8,
                        )
                        if any(kw in content for kw in ["auth", "jwt", "token", "passport"]):
                            endpoint.auth_required = True
                        params = re.findall(r':(\w+)', path)
                        endpoint.parameters = params
                        self.backend_endpoints.append(endpoint)
                        self.endpoints.append(endpoint)

                # NestJS
                controller_match = re.search(
                    r'@Controller\s*\(\s*["\'`]([^"\'`]+)["\'`]', content
                )
                base_path = controller_match.group(1) if controller_match else ""

                for i, line in enumerate(lines):
                    match = re.search(
                        r'@(Get|Post|Put|Delete|Patch)\s*\(\s*["\'`]?([^"\'`)]*)["\'`]?\s*\)',
                        line
                    )
                    if match:
                        method_str, sub_path = match.group(1), match.group(2).strip("'\"` ")
                        full_path = f"{base_path}/{sub_path}" if sub_path else base_path
                        full_path = _normalize_path(full_path)

                        endpoint = ApiEndpoint(
                            method=HttpMethod(method_str.upper()),
                            path=full_path,
                            file_path=rel_path,
                            line_number=i + 1,
                            api_type=ApiType.REST,
                            confidence=0.85,
                        )
                        if "@UseGuards" in content and "Auth" in content:
                            endpoint.auth_required = True
                        self.backend_endpoints.append(endpoint)
                        self.endpoints.append(endpoint)

            except Exception as e:
                logger.debug(f"Error scanning {js_file}: {e}")
                continue

    # ─── Rails ──────────────────────────────────────

    def _scan_rails_backend(self):
        routes_file = self.app_path / "config" / "routes.rb"
        if not routes_file.exists():
            return

        try:
            content = routes_file.read_text(errors="ignore")
            lines = content.split("\n")

            for i, line in enumerate(lines):
                match = re.search(
                    r'(get|post|put|patch|delete)\s+[\'"]([^\'"]+)[\'"]',
                    line
                )
                if match:
                    method_str, path = match.group(1), match.group(2)
                    endpoint = ApiEndpoint(
                        method=HttpMethod(method_str.upper()),
                        path=_normalize_path(path),
                        file_path="config/routes.rb",
                        line_number=i + 1,
                        api_type=ApiType.REST,
                        confidence=0.8,
                    )
                    self.backend_endpoints.append(endpoint)
                    self.endpoints.append(endpoint)

            resources = re.findall(r'resources\s+:(\w+)', content)
            for resource in resources:
                for action, path_suffix in [
                    (HttpMethod.GET, ""),
                    (HttpMethod.GET, "/:id"),
                    (HttpMethod.POST, ""),
                    (HttpMethod.PUT, "/:id"),
                    (HttpMethod.DELETE, "/:id"),
                ]:
                    endpoint = ApiEndpoint(
                        method=action,
                        path=_normalize_path(f"/{resource}{path_suffix}"),
                        file_path="config/routes.rb",
                        api_type=ApiType.REST,
                        confidence=0.6,
                    )
                    self.backend_endpoints.append(endpoint)
                    self.endpoints.append(endpoint)

        except Exception as e:
            logger.debug(f"Error scanning Rails routes: {e}")

    # ─── Go / Gin ───────────────────────────────────

    def _scan_go_backend(self):
        for go_file in iter_source_files(self.app_path):
            try:
                content = go_file.read_text(errors="ignore")
                rel_path = str(go_file.relative_to(self.app_path))
                lines = content.split("\n")

                for i, line in enumerate(lines):
                    match = re.search(
                        r'(?:router|r|engine)\.(GET|POST|PUT|DELETE|PATCH)\s*\(\s*"([^"]+)"',
                        line
                    )
                    if match:
                        method_str, path = match.group(1), match.group(2)
                        endpoint = ApiEndpoint(
                            method=HttpMethod(method_str.upper()),
                            path=_normalize_path(path),
                            file_path=rel_path,
                            line_number=i + 1,
                            api_type=ApiType.REST,
                            confidence=0.75,
                        )
                        self.backend_endpoints.append(endpoint)
                        self.endpoints.append(endpoint)

            except Exception as e:
                logger.debug(f"Error scanning {go_file}: {e}")
                continue

    # ─── Spring Boot ────────────────────────────────

    def _scan_spring_backend(self):
        for java_file in iter_source_files(self.app_path):
            try:
                content = java_file.read_text(errors="ignore")
                rel_path = str(java_file.relative_to(self.app_path))
                lines = content.split("\n")

                base_match = re.search(
                    r'@RequestMapping\s*\(\s*["\'`]([^"\'`]+)["\'`]', content
                )
                base_path = base_match.group(1) if base_match else ""

                for i, line in enumerate(lines):
                    match = re.search(
                        r'@(Get|Post|Put|Delete|Patch)Mapping\s*\(\s*["\'`]?([^"\'`)]*)["\'`]?\s*\)',
                        line
                    )
                    if match:
                        method_str = match.group(1).replace("Mapping", "")
                        sub_path = match.group(2).strip("'\"` ")
                        full_path = f"{base_path}/{sub_path}" if sub_path else base_path
                        full_path = _normalize_path(full_path)

                        endpoint = ApiEndpoint(
                            method=HttpMethod(method_str.upper()),
                            path=full_path,
                            file_path=rel_path,
                            line_number=i + 1,
                            api_type=ApiType.REST,
                            confidence=0.8,
                        )
                        self.backend_endpoints.append(endpoint)
                        self.endpoints.append(endpoint)

            except Exception as e:
                logger.debug(f"Error scanning {java_file}: {e}")
                continue

    # ─── Laravel ────────────────────────────────────

    def _scan_laravel_backend(self):
        for routes_name in ["web.php", "api.php"]:
            routes_path = self.app_path / "routes" / routes_name
            if not routes_path.exists():
                continue

            try:
                content = routes_path.read_text(errors="ignore")
                rel_path = str(routes_path.relative_to(self.app_path))
                lines = content.split("\n")

                for i, line in enumerate(lines):
                    match = re.search(
                        r'Route::(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
                        line
                    )
                    if match:
                        method_str, path = match.group(1), match.group(2)
                        endpoint = ApiEndpoint(
                            method=HttpMethod(method_str.upper()),
                            path=_normalize_path(path),
                            file_path=rel_path,
                            line_number=i + 1,
                            api_type=ApiType.REST,
                            confidence=0.8,
                        )
                        if "auth" in content or "middleware" in content:
                            endpoint.auth_required = True
                        self.backend_endpoints.append(endpoint)
                        self.endpoints.append(endpoint)

            except Exception as e:
                logger.debug(f"Error scanning Laravel routes: {e}")

    # ─── .NET ───────────────────────────────────────

    def _scan_dotnet_backend(self):
        for cs_file in iter_source_files(self.app_path):
            try:
                content = cs_file.read_text(errors="ignore")
                rel_path = str(cs_file.relative_to(self.app_path))
                lines = content.split("\n")

                base_match = re.search(r'\[Route\s*\(\s*"([^"]+)"\s*\)\]', content)
                base_path = base_match.group(1) if base_match else ""

                for i, line in enumerate(lines):
                    match = re.search(
                        r'\[Http(Get|Post|Put|Delete|Patch)\s*(?:\(\s*"([^"]*)"\s*\))?\]',
                        line
                    )
                    if match:
                        method_str = match.group(1)
                        sub_path = match.group(2) or ""
                        full_path = f"{base_path}/{sub_path}" if sub_path else base_path
                        full_path = _normalize_path(full_path.replace("[controller]", ""))

                        endpoint = ApiEndpoint(
                            method=HttpMethod(method_str.upper()),
                            path=full_path,
                            file_path=rel_path,
                            line_number=i + 1,
                            api_type=ApiType.REST,
                            confidence=0.8,
                        )
                        if "[Authorize]" in content:
                            endpoint.auth_required = True
                        self.backend_endpoints.append(endpoint)
                        self.endpoints.append(endpoint)

            except Exception as e:
                logger.debug(f"Error scanning {cs_file}: {e}")
                continue

    # ─── Flutter Services ───────────────────────────

    def _scan_flutter_services(self):
        for dart_file in iter_source_files(self.app_path):
            try:
                content = dart_file.read_text(errors="ignore")
                rel_path = str(dart_file.relative_to(self.app_path))
                lines = content.split("\n")

                # Dio
                for i, line in enumerate(lines):
                    match = re.search(
                        r'dio\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
                        line
                    )
                    if match:
                        method_str, path = match.group(1), match.group(2)
                        endpoint = ApiEndpoint(
                            method=HttpMethod(method_str.upper()),
                            path=_normalize_path(path),
                            file_path=rel_path,
                            line_number=i + 1,
                            api_type=ApiType.INTERNAL,
                            confidence=0.85,
                        )
                        base_match = re.search(r'baseUrl\s*=\s*[\'"]([^\'"]+)[\'"]', content)
                        if base_match:
                            endpoint.base_url = base_match.group(1)
                            endpoint.full_url = f"{endpoint.base_url}{path}"
                        if "Authorization" in content or "token" in content.lower():
                            endpoint.auth_required = True
                            endpoint.auth_type = "bearer"
                        self.frontend_calls.append(endpoint)
                        self.endpoints.append(endpoint)

                # http package
                for i, line in enumerate(lines):
                    match = re.search(
                        r'http\.(get|post|put|delete|patch)\s*\(.*?[\'"]([^\'"]+)[\'"]',
                        line
                    )
                    if match:
                        method_str, url = match.group(1), match.group(2)
                        endpoint = ApiEndpoint(
                            method=HttpMethod(method_str.upper()),
                            path=_normalize_path(url),
                            file_path=rel_path,
                            line_number=i + 1,
                            api_type=ApiType.INTERNAL,
                            confidence=0.7,
                        )
                        self.frontend_calls.append(endpoint)
                        self.endpoints.append(endpoint)

                # External services
                for service, url in [
                    ("firebase", "https://firebase.google.com"),
                    ("stripe", "https://api.stripe.com"),
                    ("sendgrid", "https://api.sendgrid.com"),
                    ("twilio", "https://api.twilio.com"),
                ]:
                    if service in content.lower():
                        endpoint = ApiEndpoint(
                            base_url=url,
                            api_type=ApiType.EXTERNAL,
                            file_path=rel_path,
                            confidence=0.5,
                        )
                        self.frontend_calls.append(endpoint)
                        self.endpoints.append(endpoint)

            except Exception as e:
                logger.debug(f"Error scanning {dart_file}: {e}")
                continue

    # ─── JavaScript Services ────────────────────────

    def _scan_js_services(self):
        for js_file in iter_source_files(self.app_path):
            try:
                content = js_file.read_text(errors="ignore")
                rel_path = str(js_file.relative_to(self.app_path))
                lines = content.split("\n")

                # Axios
                for i, line in enumerate(lines):
                    match = re.search(
                        r'axios\.(get|post|put|delete|patch)\s*\(\s*["\'`]([^"\'`]+)["\'`]',
                        line
                    )
                    if match:
                        method_str, path = match.group(1), match.group(2)
                        endpoint = ApiEndpoint(
                            method=HttpMethod(method_str.upper()),
                            path=_normalize_path(path),
                            file_path=rel_path,
                            line_number=i + 1,
                            api_type=ApiType.INTERNAL,
                            confidence=0.85,
                        )
                        base_match = re.search(r'baseURL\s*:\s*["\'`]([^"\'`]+)["\'`]', content)
                        if base_match:
                            endpoint.base_url = base_match.group(1)
                        self.frontend_calls.append(endpoint)
                        self.endpoints.append(endpoint)

                # Fetch
                for i, line in enumerate(lines):
                    match = re.search(r'fetch\s*\(\s*["\'`]([^"\'`]+)["\'`]', line)
                    if match:
                        url = match.group(1)
                        endpoint = ApiEndpoint(
                            path=url,
                            file_path=rel_path,
                            line_number=i + 1,
                            api_type=ApiType.INTERNAL if not url.startswith("http") else ApiType.EXTERNAL,
                            confidence=0.75,
                        )
                        self.frontend_calls.append(endpoint)
                        self.endpoints.append(endpoint)

                # Next.js API routes
                if "api/" in rel_path or "route.ts" in rel_path or "route.js" in rel_path:
                    for i, line in enumerate(lines):
                        match = re.search(
                            r'export\s+(?:async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH)\s*\(',
                            line
                        )
                        if match:
                            method_str = match.group(1)
                            path = rel_path.replace("route.ts", "").replace("route.js", "")
                            path = path.replace("\\", "/").strip("/")
                            path = f"/api/{path}" if not path.startswith("api/") else f"/{path}"

                            endpoint = ApiEndpoint(
                                method=HttpMethod(method_str.upper()),
                                path=_normalize_path(path),
                                file_path=rel_path,
                                line_number=i + 1,
                                api_type=ApiType.REST,
                                confidence=0.9,
                            )
                            self.backend_endpoints.append(endpoint)
                            self.endpoints.append(endpoint)

            except Exception as e:
                logger.debug(f"Error scanning {js_file}: {e}")
                continue

    # ─── Swift ──────────────────────────────────────

    def _scan_swift_services(self):
        for swift_file in iter_source_files(self.app_path):
            try:
                content = swift_file.read_text(errors="ignore")
                rel_path = str(swift_file.relative_to(self.app_path))
                lines = content.split("\n")

                for i, line in enumerate(lines):
                    match = re.search(r'AF\.request\s*\(\s*"([^"]+)"', line)
                    if match:
                        url = match.group(1)
                        endpoint = ApiEndpoint(
                            path=url,
                            file_path=rel_path,
                            line_number=i + 1,
                            api_type=ApiType.INTERNAL if "localhost" in url else ApiType.EXTERNAL,
                            confidence=0.7,
                        )
                        self.frontend_calls.append(endpoint)
                        self.endpoints.append(endpoint)

            except Exception as e:
                logger.debug(f"Error scanning {swift_file}: {e}")
                continue

    # ─── Kotlin ─────────────────────────────────────

    def _scan_kotlin_services(self):
        for kt_file in iter_source_files(self.app_path):
            try:
                content = kt_file.read_text(errors="ignore")
                rel_path = str(kt_file.relative_to(self.app_path))
                lines = content.split("\n")

                for i, line in enumerate(lines):
                    match = re.search(r'@(GET|POST|PUT|DELETE|PATCH)\s*\(\s*"([^"]+)"', line)
                    if match:
                        method_str, path = match.group(1), match.group(2)
                        endpoint = ApiEndpoint(
                            method=HttpMethod(method_str.upper()),
                            path=_normalize_path(path),
                            file_path=rel_path,
                            line_number=i + 1,
                            api_type=ApiType.INTERNAL,
                            confidence=0.8,
                        )
                        self.frontend_calls.append(endpoint)
                        self.endpoints.append(endpoint)

            except Exception as e:
                logger.debug(f"Error scanning {kt_file}: {e}")
                continue

    # ─── GraphQL ────────────────────────────────────

    def _scan_graphql(self):
        for file in iter_source_files(self.app_path):
            try:
                content = file.read_text(errors="ignore")
                rel_path = str(file.relative_to(self.app_path))

                if "graphql" not in content.lower():
                    continue

                if "apollo" in content.lower() or "graphqlHTTP" in content:
                    endpoint = ApiEndpoint(
                        path="/graphql",
                        file_path=rel_path,
                        api_type=ApiType.GRAPHQL,
                        confidence=0.7,
                    )
                    self.backend_endpoints.append(endpoint)
                    self.endpoints.append(endpoint)

                for pattern in [r'useQuery\s*\(', r'useMutation\s*\(', r'gql\s*`']:
                    if re.search(pattern, content):
                        endpoint = ApiEndpoint(
                            path="/graphql",
                            file_path=rel_path,
                            api_type=ApiType.GRAPHQL,
                            confidence=0.6,
                        )
                        if not any(
                            e.path == "/graphql" and e.api_type == ApiType.GRAPHQL
                            for e in self.endpoints
                        ):
                            self.frontend_calls.append(endpoint)
                            self.endpoints.append(endpoint)
                        break

            except Exception as e:
                logger.debug(f"Error scanning {file} for GraphQL: {e}")
                continue

    # ─── WebSocket ──────────────────────────────────

    def _scan_websockets(self):
        ws_keywords = ["websocket", "ws://", "wss://", "socket.io", "WebSocket("]

        for file in iter_source_files(self.app_path):
            try:
                content = file.read_text(errors="ignore")
                rel_path = str(file.relative_to(self.app_path))

                if not any(kw in content.lower() for kw in ws_keywords):
                    continue

                ws_url = None
                url_match = re.search(r'["\']((?:ws|wss)://[^"\']+)["\']', content)
                if url_match:
                    ws_url = url_match.group(1)

                endpoint = ApiEndpoint(
                    path=ws_url or "websocket",
                    file_path=rel_path,
                    api_type=ApiType.WEBSOCKET,
                    confidence=0.6,
                )
                self.endpoints.append(endpoint)

            except Exception as e:
                logger.debug(f"Error scanning {file} for WebSocket: {e}")
                continue


# ─── Wrapper ────────────────────────────────────────

def scan_apis(app_path: Path, stack_info: dict = None) -> dict:
    """Main entry point. Returns structured API map."""
    scanner = ApiScanner(Path(app_path), stack_info)
    return scanner.scan_all()