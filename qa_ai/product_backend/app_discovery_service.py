"""
app_discovery_service.py — Safe app fingerprint scanning.

SAFETY RULES (non-negotiable):
- No shell execution. No os.system. No subprocess. No eval.
- Folder scan: existence checks only, except package.json (name + scripts fields).
- Max depth 3. Max 200 files. Max 256 KB per file read.
- Skip: .env, .env.*, secrets.*, *.key, *.pem, .git/, node_modules/.
- GitHub URL: return unsupported (no cloning).
- Web/API URL: validate URL format only, suggest strategy by path/port heuristics.
- User must initiate scan explicitly. No background scanning.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from qa_ai.product_backend.discovery_models import (
    AppFingerprint,
    AppSourceInput,
    AuditStrategySuggestion,
    Confidence,
    DetectedLaunchCommand,
    DetectedValue,
    DiscoveryResult,
    DiscoveryStatus,
    SourceType,
)

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_DEPTH   = 3
MAX_FILES   = 200
MAX_READ    = 256 * 1024   # 256 KB

# Directories to skip entirely
_SKIP_DIRS = frozenset({
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    ".tox", "dist", "build", ".next", ".nuxt", "out", "target",
    ".cache", "coverage", ".pytest_cache", ".mypy_cache",
})

# Files never to read content from (existence check only)
_NEVER_READ = re.compile(
    r"^\.env$|^\.env\..+|secrets?\..+|.*\.key$|.*\.pem$|.*\.p12$|"
    r".*\.pfx$|.*_secret.*|.*password.*|.*credential.*",
    re.IGNORECASE,
)

# Stack detection: (file_pattern, stack_name, app_type_hint, confidence)
_STACK_SIGNALS: list[tuple[str, str, str, Confidence]] = [
    # Python
    ("requirements.txt",   "Python",       "api",     Confidence.high),
    ("pyproject.toml",     "Python",       "api",     Confidence.high),
    ("setup.py",           "Python",       "api",     Confidence.medium),
    ("manage.py",          "Django",       "web",     Confidence.high),
    ("wsgi.py",            "Django/WSGI",  "web",     Confidence.medium),
    ("asgi.py",            "ASGI",         "web",     Confidence.medium),
    # Node / JS
    ("package.json",       "Node.js",      "web",     Confidence.high),
    ("yarn.lock",          "Node.js",      "web",     Confidence.medium),
    ("pnpm-lock.yaml",     "Node.js",      "web",     Confidence.medium),
    # Frontend frameworks (detected by config files)
    ("vite.config.ts",     "Vite/React",   "web",     Confidence.high),
    ("vite.config.js",     "Vite",         "web",     Confidence.high),
    ("next.config.js",     "Next.js",      "web",     Confidence.high),
    ("next.config.ts",     "Next.js",      "web",     Confidence.high),
    ("nuxt.config.ts",     "Nuxt",         "web",     Confidence.high),
    ("svelte.config.js",   "SvelteKit",    "web",     Confidence.high),
    ("angular.json",       "Angular",      "web",     Confidence.high),
    ("vue.config.js",      "Vue",          "web",     Confidence.high),
    # Backend frameworks
    ("Cargo.toml",         "Rust",         "api",     Confidence.high),
    ("go.mod",             "Go",           "api",     Confidence.high),
    ("pom.xml",            "Java/Maven",   "api",     Confidence.high),
    ("build.gradle",       "Java/Gradle",  "api",     Confidence.high),
    ("Gemfile",            "Ruby",         "web",     Confidence.high),
    ("composer.json",      "PHP",          "web",     Confidence.high),
    # Mobile
    ("pubspec.yaml",       "Flutter",      "mobile",  Confidence.high),
    ("AndroidManifest.xml","Android",      "mobile",  Confidence.high),
    ("Info.plist",         "iOS",          "mobile",  Confidence.high),
    # Desktop
    ("tauri.conf.json",    "Tauri",        "desktop", Confidence.high),
    ("electron.js",        "Electron",     "desktop", Confidence.high),
    ("electron-builder.yml","Electron",    "desktop", Confidence.high),
    # Infra / config (low value for app type)
    ("Dockerfile",         "Docker",       "",        Confidence.medium),
    ("docker-compose.yml", "Docker Compose","",       Confidence.medium),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _new_id() -> str:
    import uuid
    return str(uuid.uuid4())

def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _safe_path(raw: str) -> Optional[Path]:
    """Resolve path. Must be absolute, not filesystem root."""
    try:
        p = Path(raw).expanduser().resolve()
        if not p.is_absolute():
            return None
        if p == p.root or str(p) in ("/", "C:\\", "C:/"):
            return None
        return p
    except Exception:
        return None


def _read_package_json_safe(path: Path) -> dict:
    """Read name and scripts from package.json only. Never full file."""
    try:
        size = path.stat().st_size
        if size > MAX_READ:
            return {}
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        if not isinstance(data, dict):
            return {}
        result: dict = {}
        if "name" in data and isinstance(data["name"], str):
            result["name"] = data["name"][:256]
        if "scripts" in data and isinstance(data["scripts"], dict):
            result["scripts"] = {
                k: v for k, v in list(data["scripts"].items())[:20]
                if isinstance(k, str) and isinstance(v, str)
            }
        return result
    except Exception:
        return {}


# ── Core scanner ──────────────────────────────────────────────────────────────

def scan_local_folder(source_input: AppSourceInput) -> DiscoveryResult:
    """
    Scan a local folder for app fingerprints.
    - Only checks file existence (except package.json name/scripts)
    - Skips secret files, node_modules, .git
    - Hard limits: depth 3, 200 files
    """
    result_id = _new_id()
    now = _now_iso()

    base_result = DiscoveryResult(
        id=result_id,
        project_id=source_input.project_id,
        source_type=SourceType.local_folder,
        local_path=source_input.local_path,
        status=DiscoveryStatus.failed,
        created_at=now,
        updated_at=now,
    )

    if not source_input.local_path:
        base_result.error_message = "No local path provided."
        return base_result

    folder = _safe_path(source_input.local_path)
    if folder is None:
        base_result.error_message = "Path must be absolute and not root."
        return base_result

    if not folder.exists():
        base_result.error_message = f"Path does not exist: {source_input.local_path}"
        return base_result

    if not folder.is_dir():
        base_result.error_message = "Path is not a directory."
        return base_result

    # ── Walk directory ─────────────────────────────────────────────────────
    fingerprint = AppFingerprint()
    found_files: set[str] = set()
    file_count = 0
    truncated = False

    # BFS with depth tracking
    queue: list[tuple[Path, int]] = [(folder, 0)]
    package_json_path: Optional[Path] = None

    while queue and file_count < MAX_FILES:
        current_dir, depth = queue.pop(0)
        if depth > MAX_DEPTH:
            truncated = True
            continue

        try:
            entries = list(current_dir.iterdir())
        except PermissionError:
            continue

        for entry in entries:
            if file_count >= MAX_FILES:
                truncated = True
                break

            name = entry.name

            if entry.is_dir():
                if name in _SKIP_DIRS:
                    if name == "node_modules":
                        fingerprint.has_node_modules = True
                    elif name == ".git":
                        fingerprint.has_git = True
                    continue
                if depth < MAX_DEPTH:
                    queue.append((entry, depth + 1))
                else:
                    truncated = True
                continue

            if entry.is_file():
                file_count += 1
                rel = str(entry.relative_to(folder))
                found_files.add(name.lower())

                if name == "package.json" and package_json_path is None:
                    package_json_path = entry

    fingerprint.files_scanned = file_count
    fingerprint.detected_files = sorted(found_files)[:100]
    fingerprint.truncated = truncated
    if fingerprint.has_node_modules or fingerprint.has_git:
        pass  # already set above

    # ── Read package.json (only name + scripts) ────────────────────────────
    pkg_data: dict = {}
    if package_json_path:
        pkg_data = _read_package_json_safe(package_json_path)
        if "name" in pkg_data:
            fingerprint.package_name = pkg_data["name"]
        if "scripts" in pkg_data:
            fingerprint.package_scripts = pkg_data["scripts"]

    # ── Match stack signals ────────────────────────────────────────────────
    detected_stack: list[DetectedValue] = []
    app_type_votes: list[tuple[str, Confidence]] = []

    for filename, stack_label, app_type_hint, conf in _STACK_SIGNALS:
        if filename.lower() in found_files:
            detected_stack.append(DetectedValue(
                value=stack_label, confidence=conf, source=filename
            ))
            if app_type_hint:
                app_type_votes.append((app_type_hint, conf))

    # ── Suggest app type ───────────────────────────────────────────────────
    suggested_app_type: Optional[DetectedValue] = None
    if app_type_votes:
        # Pick highest confidence, then first
        conf_order = {Confidence.high: 0, Confidence.medium: 1, Confidence.low: 2, Confidence.unknown: 3}
        best_type, best_conf = min(app_type_votes, key=lambda x: conf_order[x[1]])
        suggested_app_type = DetectedValue(
            value=best_type,
            confidence=best_conf,
            source="file pattern detection",
        )

    # ── Suggest name ───────────────────────────────────────────────────────
    suggested_name: Optional[DetectedValue] = None
    if pkg_data.get("name"):
        raw_name = pkg_data["name"]
        # Remove scope prefix (@org/name → name)
        display_name = raw_name.split("/")[-1].replace("-", " ").replace("_", " ").title()
        suggested_name = DetectedValue(
            value=display_name, confidence=Confidence.high, source="package.json"
        )
    else:
        suggested_name = DetectedValue(
            value=folder.name.replace("-", " ").replace("_", " ").title(),
            confidence=Confidence.low,
            source="folder name",
        )

    # ── Suggest launch command ─────────────────────────────────────────────
    suggested_launch: Optional[DetectedLaunchCommand] = None

    scripts = pkg_data.get("scripts", {})
    if "dev" in scripts:
        suggested_launch = DetectedLaunchCommand(
            command=f"npm run dev", confidence=Confidence.high, source="package.json scripts.dev"
        )
    elif "start" in scripts:
        suggested_launch = DetectedLaunchCommand(
            command=f"npm run start", confidence=Confidence.medium, source="package.json scripts.start"
        )
    elif "manage.py" in found_files:
        suggested_launch = DetectedLaunchCommand(
            command="python manage.py runserver", confidence=Confidence.high, source="manage.py"
        )
    elif "main.py" in found_files or "app.py" in found_files:
        entry_file = "main.py" if "main.py" in found_files else "app.py"
        suggested_launch = DetectedLaunchCommand(
            command=f"python {entry_file}", confidence=Confidence.medium, source=entry_file
        )
    elif "go.mod" in found_files:
        suggested_launch = DetectedLaunchCommand(
            command="go run .", confidence=Confidence.medium, source="go.mod"
        )
    elif "Cargo.toml" in found_files:
        suggested_launch = DetectedLaunchCommand(
            command="cargo run", confidence=Confidence.medium, source="Cargo.toml"
        )
    elif "Gemfile" in found_files:
        suggested_launch = DetectedLaunchCommand(
            command="bundle exec rails server", confidence=Confidence.low, source="Gemfile"
        )

    # ── Audit strategy ─────────────────────────────────────────────────────
    audit_strategy: Optional[AuditStrategySuggestion] = None
    if suggested_app_type:
        at = suggested_app_type.value
        if at == "web":
            audit_strategy = AuditStrategySuggestion(
                strategy="web-browser",
                confidence=suggested_app_type.confidence,
                reason="Detected web app — browser-based UI testing applies.",
            )
        elif at == "api":
            audit_strategy = AuditStrategySuggestion(
                strategy="api-contract",
                confidence=suggested_app_type.confidence,
                reason="Detected API app — contract and endpoint testing applies.",
            )
        elif at == "mobile":
            audit_strategy = AuditStrategySuggestion(
                strategy="mobile-ui",
                confidence=suggested_app_type.confidence,
                reason="Detected mobile app — device UI testing applies.",
            )
        elif at == "desktop":
            audit_strategy = AuditStrategySuggestion(
                strategy="desktop-ui",
                confidence=suggested_app_type.confidence,
                reason="Detected desktop app — native UI testing applies.",
            )

    result = DiscoveryResult(
        id=result_id,
        project_id=source_input.project_id,
        source_type=SourceType.local_folder,
        local_path=source_input.local_path,
        status=DiscoveryStatus.complete,
        suggested_name=suggested_name,
        suggested_app_type=suggested_app_type,
        detected_stack=detected_stack,
        suggested_launch_command=suggested_launch,
        audit_strategy=audit_strategy,
        fingerprint=fingerprint,
        created_at=now,
        updated_at=now,
    )
    return result


# ── URL-based detection ───────────────────────────────────────────────────────

def scan_web_url(source_input: AppSourceInput) -> DiscoveryResult:
    """Validate URL format, suggest web-browser audit strategy. No network request."""
    result_id = _new_id()
    now = _now_iso()

    base = DiscoveryResult(
        id=result_id,
        project_id=source_input.project_id,
        source_type=SourceType.web_url,
        url=source_input.url,
        status=DiscoveryStatus.failed,
        created_at=now,
        updated_at=now,
    )

    url = source_input.url or ""
    parsed = _validate_url(url)
    if not parsed:
        base.error_message = "Invalid URL. Must be http:// or https://."
        return base

    hostname = parsed.hostname or ""
    name_guess = hostname.replace("www.", "").split(".")[0].replace("-", " ").title()

    base.status = DiscoveryStatus.complete
    base.suggested_name = DetectedValue(
        value=name_guess, confidence=Confidence.low, source="URL hostname"
    )
    base.suggested_app_type = DetectedValue(
        value="web", confidence=Confidence.high, source="web URL provided"
    )
    base.suggested_base_url = DetectedValue(
        value=url, confidence=Confidence.high, source="user input"
    )
    base.audit_strategy = AuditStrategySuggestion(
        strategy="web-browser",
        confidence=Confidence.high,
        reason="Web URL provided — browser-based UI testing applies.",
    )
    return base


def scan_api_url(source_input: AppSourceInput) -> DiscoveryResult:
    """Validate API base URL, suggest api-contract strategy. No network request."""
    result_id = _new_id()
    now = _now_iso()

    base = DiscoveryResult(
        id=result_id,
        project_id=source_input.project_id,
        source_type=SourceType.api_base_url,
        url=source_input.url,
        status=DiscoveryStatus.failed,
        created_at=now,
        updated_at=now,
    )

    url = source_input.url or ""
    parsed = _validate_url(url)
    if not parsed:
        base.error_message = "Invalid URL. Must be http:// or https://."
        return base

    hostname = parsed.hostname or ""
    name_guess = hostname.replace("www.", "").split(".")[0].replace("-", " ").title() + " API"

    base.status = DiscoveryStatus.complete
    base.suggested_name = DetectedValue(
        value=name_guess, confidence=Confidence.low, source="URL hostname"
    )
    base.suggested_app_type = DetectedValue(
        value="api", confidence=Confidence.high, source="API URL provided"
    )
    base.suggested_base_url = DetectedValue(
        value=url, confidence=Confidence.high, source="user input"
    )
    base.audit_strategy = AuditStrategySuggestion(
        strategy="api-contract",
        confidence=Confidence.high,
        reason="API base URL provided — contract and endpoint testing applies.",
    )
    return base


def scan_github_url(source_input: AppSourceInput) -> DiscoveryResult:
    """GitHub scanning not supported (would require cloning). Return unsupported."""
    result_id = _new_id()
    now = _now_iso()
    return DiscoveryResult(
        id=result_id,
        project_id=source_input.project_id,
        source_type=SourceType.github_url,
        url=source_input.url,
        status=DiscoveryStatus.unsupported,
        error_message=(
            "GitHub URL scanning is not supported in this version. "
            "Clone the repo locally and use 'Local folder' instead."
        ),
        created_at=now,
        updated_at=now,
    )


def scan_manual(source_input: AppSourceInput) -> DiscoveryResult:
    """Manual mode — no detection, return empty result for user to fill."""
    result_id = _new_id()
    now = _now_iso()
    return DiscoveryResult(
        id=result_id,
        project_id=source_input.project_id,
        source_type=SourceType.manual,
        status=DiscoveryStatus.complete,
        created_at=now,
        updated_at=now,
    )


# ── Dispatcher ────────────────────────────────────────────────────────────────

def run_discovery(source_input: AppSourceInput) -> DiscoveryResult:
    """Route to correct scanner based on source_type."""
    if source_input.source_type == SourceType.local_folder:
        return scan_local_folder(source_input)
    elif source_input.source_type == SourceType.web_url:
        return scan_web_url(source_input)
    elif source_input.source_type == SourceType.api_base_url:
        return scan_api_url(source_input)
    elif source_input.source_type == SourceType.github_url:
        return scan_github_url(source_input)
    elif source_input.source_type == SourceType.manual:
        return scan_manual(source_input)
    else:
        result_id = _new_id()
        now = _now_iso()
        return DiscoveryResult(
            id=result_id,
            project_id=source_input.project_id,
            source_type=source_input.source_type,
            status=DiscoveryStatus.failed,
            error_message=f"Unknown source type: {source_input.source_type}",
            created_at=now,
            updated_at=now,
        )


# ── Utilities ─────────────────────────────────────────────────────────────────

def _validate_url(url: str) -> Optional[object]:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return None
        if not parsed.netloc:
            return None
        return parsed
    except Exception:
        return None
