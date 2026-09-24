"""
detect_stack.py - Deep framework detection for autonomous QA system.

Determines stack, versions, platforms, and capabilities so downstream
QA agents can configure themselves correctly.
"""

from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import yaml
import re

logger = logging.getLogger(__name__)


# ─── Data Models ───────────────────────────────────────

class AppType(Enum):
    WEB = "web"
    MOBILE = "mobile"
    DESKTOP = "desktop"
    BACKEND = "backend"
    CLI = "cli"
    LIBRARY = "library"
    MONOREPO = "monorepo"


class Language(Enum):
    DART = "dart"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    PYTHON = "python"
    KOTLIN = "kotlin"
    JAVA = "java"
    SWIFT = "swift"
    RUST = "rust"
    GO = "go"
    CSHARP = "csharp"
    RUBY = "ruby"
    PHP = "php"
    UNKNOWN = "unknown"


class Framework(Enum):
    FLUTTER = "flutter"
    REACT = "react"
    NEXT_JS = "nextjs"
    VUE = "vue"
    ANGULAR = "angular"
    SVELTE = "svelte"
    DJANGO = "django"
    FASTAPI = "fastapi"
    FLASK = "flask"
    EXPRESS = "express"
    NEST_JS = "nestjs"
    SPRING_BOOT = "spring_boot"
    LARAVEL = "laravel"
    RAILS = "rails"
    DOTNET = "dotnet"
    GIN = "gin"
    REACT_NATIVE = "react_native"
    SWIFTUI = "swiftui"
    JETPACK_COMPOSE = "jetpack_compose"
    UNKNOWN = "unknown"


@dataclass
class StackInfo:
    framework: Framework = Framework.UNKNOWN
    language: Language = Language.UNKNOWN
    app_type: AppType = AppType.WEB
    framework_version: Optional[str] = None
    language_version: Optional[str] = None

    state_management: Optional[str] = None
    router_library: Optional[str] = None
    http_client: Optional[str] = None
    database: Optional[str] = None
    auth_provider: Optional[str] = None
    css_framework: Optional[str] = None
    bundler: Optional[str] = None
    test_framework: Optional[str] = None
    build_tool: Optional[str] = None
    package_manager: Optional[str] = None

    has_auth: bool = False
    has_api: bool = False
    has_database: bool = False
    has_payments: bool = False
    has_file_upload: bool = False
    has_real_time: bool = False
    has_i18n: bool = False
    has_dark_mode: bool = False
    has_offline_support: bool = False
    has_e2e_tests: bool = False
    has_unit_tests: bool = False

    raw_dependencies: list = field(default_factory=list)
    detected_files: list = field(default_factory=list)
    confidence_score: float = 0.0


# ─── Main Detection ─────────────────────────────────────

def detect_stack(app_path: Path) -> StackInfo:
    stack = StackInfo()

    if not app_path.exists() or not app_path.is_dir():
        return stack

    _detect_by_lock_files(app_path, stack)

    if stack.framework != Framework.UNKNOWN:
        _detect_deep_specifics(app_path, stack)
        stack.confidence_score = 0.95
    else:
        _detect_by_heuristics(app_path, stack)
        stack.confidence_score = 0.5 if stack.language != Language.UNKNOWN else 0.1

    return stack


def _detect_by_lock_files(path: Path, stack: StackInfo) -> None:
    pubspec = path / "pubspec.yaml"
    if pubspec.exists():
        stack.framework = Framework.FLUTTER
        stack.language = Language.DART
        stack.package_manager = "pub"
        _parse_pubspec(pubspec, stack)
        return

    package_json = path / "package.json"
    if package_json.exists():
        _parse_package_json(package_json, path, stack)
        return

    pyproject = path / "pyproject.toml"
    requirements = path / "requirements.txt"

    if pyproject.exists():
        stack.language = Language.PYTHON
        stack.package_manager = "poetry/pip"
        _parse_pyproject(pyproject, stack)
        return

    if requirements.exists():
        stack.language = Language.PYTHON
        stack.package_manager = "pip"
        _parse_requirements(requirements, stack)
        return

    gradle = path / "build.gradle"
    gradle_kts = path / "build.gradle.kts"

    if gradle.exists() or gradle_kts.exists():
        stack.language = Language.KOTLIN if gradle_kts.exists() else Language.JAVA
        _parse_gradle(path, stack)
        return

    if (path / "pom.xml").exists():
        stack.language = Language.JAVA
        _parse_maven(path, stack)
        return

    if (path / "Package.swift").exists() or list(path.glob("*.xcodeproj")):
        stack.language = Language.SWIFT
        _parse_swift(path, stack)
        return

    cargo = path / "Cargo.toml"
    if cargo.exists():
        stack.language = Language.RUST
        stack.build_tool = "cargo"
        _parse_cargo(cargo, stack)
        return

    go_mod = path / "go.mod"
    if go_mod.exists():
        stack.language = Language.GO
        _parse_go_mod(go_mod, stack)
        return

    csproj = list(path.glob("*.csproj"))
    if csproj:
        stack.language = Language.CSHARP
        stack.framework = Framework.DOTNET
        _parse_csproj(csproj[0], stack)
        return

    if (path / "Gemfile").exists():
        stack.language = Language.RUBY
        _parse_gemfile(path, stack)
        return

    composer = path / "composer.json"
    if composer.exists():
        stack.language = Language.PHP
        _parse_composer(composer, stack)
        return


# ─── Parsers ────────────────────────────────────────────

def _parse_pubspec(yaml_path: Path, stack: StackInfo) -> None:
    stack.detected_files.append("pubspec.yaml")

    try:
        data = yaml.safe_load(yaml_path.read_text()) or {}
    except Exception as e:
        logger.debug("Failed to parse pubspec.yaml: %s", e)
        return

    stack.app_type = AppType.MOBILE

    env = data.get("environment", {})
    stack.framework_version = env.get("flutter")
    stack.language_version = env.get("sdk")

    deps = data.get("dependencies", {}) or {}
    dev_deps = data.get("dev_dependencies", {}) or {}
    all_deps = {**deps, **dev_deps}

    stack.raw_dependencies = list(all_deps.keys())

    if "firebase_auth" in all_deps:
        stack.has_auth = True
        stack.auth_provider = "firebase"

    if any(d in all_deps for d in ["firebase_core", "sqflite", "hive", "drift"]):
        stack.has_database = True
        if "firebase_core" in all_deps:
            stack.database = "firebase"
        elif "drift" in all_deps:
            stack.database = "drift"
        elif "sqflite" in all_deps:
            stack.database = "sqflite"
        elif "hive" in all_deps:
            stack.database = "hive"

    if any(d in all_deps for d in ["stripe_sdk", "flutter_stripe", "razorpay_flutter"]):
        stack.has_payments = True

    if any(d in all_deps for d in ["file_picker", "image_picker"]):
        stack.has_file_upload = True

    if any(d in all_deps for d in ["firebase_messaging", "web_socket_channel", "socket_io_client"]):
        stack.has_real_time = True

    if any(d in all_deps for d in ["flutter_localizations", "easy_localization", "intl"]):
        stack.has_i18n = True

    if any(d in all_deps for d in ["riverpod", "flutter_riverpod", "hooks_riverpod"]):
        stack.state_management = "riverpod"
    elif any(d in all_deps for d in ["flutter_bloc", "bloc"]):
        stack.state_management = "bloc"
    elif "provider" in all_deps:
        stack.state_management = "provider"
    elif "get" in all_deps:
        stack.state_management = "getx"

    if "go_router" in all_deps:
        stack.router_library = "go_router"
    elif "auto_route" in all_deps:
        stack.router_library = "auto_route"

    if "dio" in all_deps:
        stack.http_client = "dio"
    elif "http" in all_deps:
        stack.http_client = "http"

    if "flutter_test" in all_deps:
        stack.test_framework = "flutter_test"
        stack.has_unit_tests = True

    if "integration_test" in all_deps:
        stack.has_e2e_tests = True

    flutter_config = data.get("flutter", {})
    if isinstance(flutter_config, dict) and "plugin" in flutter_config:
        stack.app_type = AppType.LIBRARY


def _parse_package_json(json_path: Path, app_path: Path, stack: StackInfo) -> None:
    stack.detected_files.append("package.json")

    try:
        data = json.loads(json_path.read_text())
    except Exception as e:
        logger.debug("Failed to parse package.json: %s", e)
        return

    deps = data.get("dependencies", {}) or {}
    dev_deps = data.get("devDependencies", {}) or {}
    all_deps = {**deps, **dev_deps}

    stack.raw_dependencies = list(all_deps.keys())
    stack.language = Language.TYPESCRIPT if _has_typescript(app_path) else Language.JAVASCRIPT

    if "next" in deps:
        stack.framework = Framework.NEXT_JS
        stack.framework_version = _clean_version(deps.get("next"))
    elif "react-native" in deps:
        stack.framework = Framework.REACT_NATIVE
        stack.app_type = AppType.MOBILE
    elif "react" in deps and "react-dom" in deps:
        stack.framework = Framework.REACT
        stack.framework_version = _clean_version(deps.get("react"))
    elif "vue" in deps:
        stack.framework = Framework.VUE
    elif "@angular/core" in deps:
        stack.framework = Framework.ANGULAR
        stack.language = Language.TYPESCRIPT
    elif "svelte" in deps:
        stack.framework = Framework.SVELTE
    elif "@nestjs/core" in deps:
        stack.framework = Framework.NEST_JS
        stack.app_type = AppType.BACKEND
    elif "express" in deps:
        stack.framework = Framework.EXPRESS
        stack.app_type = AppType.BACKEND

    if (app_path / "pnpm-lock.yaml").exists():
        stack.package_manager = "pnpm"
    elif (app_path / "yarn.lock").exists():
        stack.package_manager = "yarn"
    elif (app_path / "package-lock.json").exists():
        stack.package_manager = "npm"

    if "vite" in all_deps:
        stack.bundler = "vite"
    elif "webpack" in all_deps:
        stack.bundler = "webpack"
    elif "turbo" in all_deps or "turbopack" in all_deps:
        stack.bundler = "turbopack/turbo"

    if "@reduxjs/toolkit" in all_deps or "redux" in all_deps:
        stack.state_management = "redux"
    elif "zustand" in all_deps:
        stack.state_management = "zustand"
    elif "jotai" in all_deps:
        stack.state_management = "jotai"
    elif "recoil" in all_deps:
        stack.state_management = "recoil"
    elif "pinia" in all_deps:
        stack.state_management = "pinia"

    if "react-router-dom" in all_deps:
        stack.router_library = "react-router"
    elif "vue-router" in all_deps:
        stack.router_library = "vue-router"

    if "axios" in all_deps:
        stack.http_client = "axios"
    elif "got" in all_deps:
        stack.http_client = "got"
    elif "node-fetch" in all_deps:
        stack.http_client = "node-fetch"

    if "tailwindcss" in all_deps:
        stack.css_framework = "tailwind"
    elif "bootstrap" in all_deps:
        stack.css_framework = "bootstrap"
    elif "@mui/material" in all_deps:
        stack.css_framework = "material_ui"
    elif "antd" in all_deps:
        stack.css_framework = "ant_design"

    if "jest" in all_deps or "vitest" in all_deps:
        stack.test_framework = "vitest" if "vitest" in all_deps else "jest"
        stack.has_unit_tests = True

    if "cypress" in all_deps or "playwright" in all_deps or "@playwright/test" in all_deps:
        stack.has_e2e_tests = True

    if any(d in all_deps for d in ["next-auth", "@auth0/auth0-react", "firebase", "jsonwebtoken"]):
        stack.has_auth = True
        if "next-auth" in all_deps:
            stack.auth_provider = "next-auth"
        elif "@auth0/auth0-react" in all_deps:
            stack.auth_provider = "auth0"
        elif "firebase" in all_deps:
            stack.auth_provider = "firebase"
        else:
            stack.auth_provider = "jwt"

    if any(d in all_deps for d in ["prisma", "mongoose", "typeorm", "sequelize"]):
        stack.has_database = True
        if "prisma" in all_deps:
            stack.database = "prisma"
        elif "mongoose" in all_deps:
            stack.database = "mongodb/mongoose"
        elif "typeorm" in all_deps:
            stack.database = "typeorm"
        else:
            stack.database = "sequelize"

    if any(d in all_deps for d in ["stripe", "@stripe/stripe-js"]):
        stack.has_payments = True


def _parse_pyproject(toml_path: Path, stack: StackInfo) -> None:
    stack.detected_files.append("pyproject.toml")
    stack.app_type = AppType.BACKEND

    content = toml_path.read_text(errors="ignore").lower()

    if "fastapi" in content:
        stack.framework = Framework.FASTAPI
    elif "django" in content:
        stack.framework = Framework.DJANGO
    elif "flask" in content:
        stack.framework = Framework.FLASK

    if "pytest" in content:
        stack.test_framework = "pytest"
        stack.has_unit_tests = True

    if any(x in content for x in ["sqlalchemy", "psycopg", "pymongo", "alembic"]):
        stack.has_database = True

    if any(x in content for x in ["jwt", "authlib", "passlib"]):
        stack.has_auth = True


def _parse_requirements(req_path: Path, stack: StackInfo) -> None:
    stack.detected_files.append("requirements.txt")
    stack.app_type = AppType.BACKEND

    content = req_path.read_text(errors="ignore").lower()

    if "fastapi" in content:
        stack.framework = Framework.FASTAPI
    elif "django" in content:
        stack.framework = Framework.DJANGO
    elif "flask" in content:
        stack.framework = Framework.FLASK

    if "pytest" in content:
        stack.test_framework = "pytest"
        stack.has_unit_tests = True

    if any(x in content for x in ["sqlalchemy", "psycopg", "pymongo", "alembic"]):
        stack.has_database = True

    if any(x in content for x in ["jwt", "authlib", "passlib"]):
        stack.has_auth = True


def _parse_gradle(path: Path, stack: StackInfo) -> None:
    stack.app_type = AppType.MOBILE
    stack.build_tool = "gradle"

    if (path / "build.gradle.kts").exists():
        stack.detected_files.append("build.gradle.kts")
    else:
        stack.detected_files.append("build.gradle")

    gradle_text = ""
    for file_name in ["build.gradle", "build.gradle.kts", "app/build.gradle", "app/build.gradle.kts"]:
        file_path = path / file_name
        if file_path.exists():
            gradle_text += file_path.read_text(errors="ignore").lower()

    if "com.android.application" in gradle_text:
        stack.app_type = AppType.MOBILE
        stack.framework = Framework.JETPACK_COMPOSE if "compose" in gradle_text else Framework.UNKNOWN
    elif "spring-boot" in gradle_text or "org.springframework.boot" in gradle_text:
        stack.app_type = AppType.BACKEND
        stack.framework = Framework.SPRING_BOOT


def _parse_maven(path: Path, stack: StackInfo) -> None:
    stack.language = Language.JAVA
    stack.build_tool = "maven"
    stack.app_type = AppType.BACKEND
    stack.detected_files.append("pom.xml")

    content = (path / "pom.xml").read_text(errors="ignore").lower()
    if "spring-boot" in content:
        stack.framework = Framework.SPRING_BOOT


def _parse_swift(path: Path, stack: StackInfo) -> None:
    stack.framework = Framework.SWIFTUI
    stack.app_type = AppType.MOBILE
    stack.build_tool = "xcodebuild"

    if (path / "Package.swift").exists():
        stack.detected_files.append("Package.swift")
    else:
        projects = list(path.glob("*.xcodeproj"))
        if projects:
            stack.detected_files.append(projects[0].name)


def _parse_cargo(toml_path: Path, stack: StackInfo) -> None:
    stack.detected_files.append("Cargo.toml")
    stack.app_type = AppType.CLI


def _parse_go_mod(mod_path: Path, stack: StackInfo) -> None:
    stack.detected_files.append("go.mod")
    stack.app_type = AppType.BACKEND

    content = mod_path.read_text(errors="ignore").lower()
    if "gin-gonic" in content:
        stack.framework = Framework.GIN


def _parse_csproj(csproj_path: Path, stack: StackInfo) -> None:
    stack.detected_files.append(csproj_path.name)
    stack.app_type = AppType.BACKEND
    stack.framework = Framework.DOTNET
    stack.build_tool = "dotnet"


def _parse_gemfile(path: Path, stack: StackInfo) -> None:
    stack.detected_files.append("Gemfile")
    stack.app_type = AppType.BACKEND

    content = (path / "Gemfile").read_text(errors="ignore").lower()
    if "rails" in content:
        stack.framework = Framework.RAILS


def _parse_composer(json_path: Path, stack: StackInfo) -> None:
    stack.detected_files.append("composer.json")
    stack.app_type = AppType.BACKEND

    content = json_path.read_text(errors="ignore").lower()
    if "laravel" in content:
        stack.framework = Framework.LARAVEL


# ─── Deeper Scans ───────────────────────────────────────

def _detect_deep_specifics(path: Path, stack: StackInfo) -> None:
    file_names = {p.name.lower() for p in path.rglob("*") if p.is_file()}

    if any(name in file_names for name in [".env", ".env.local", ".env.example"]):
        stack.has_api = True

    if any("dark" in name for name in file_names):
        stack.has_dark_mode = True

    if any(name in file_names for name in ["dockerfile", "docker-compose.yml", "docker-compose.yaml"]):
        stack.detected_files.append("docker")

    if any(name in file_names for name in ["playwright.config.ts", "playwright.config.js", "cypress.config.ts", "cypress.config.js"]):
        stack.has_e2e_tests = True


# ─── Helpers ────────────────────────────────────────────

def _has_typescript(app_path: Path) -> bool:
    return (
        (app_path / "tsconfig.json").exists()
        or any(app_path.glob("**/*.ts"))
        or any(app_path.glob("**/*.tsx"))
    )


def _clean_version(version: Optional[str]) -> Optional[str]:
    if not version:
        return None
    return re.sub(r"^[\^~>=< ]+", "", version.strip())


def _detect_by_heuristics(path: Path, stack: StackInfo) -> None:
    files = [f for f in path.rglob("*") if f.is_file()]

    if not files:
        return

    ext_count = {}
    for file in files:
        if file.suffix:
            ext_count[file.suffix.lower()] = ext_count.get(file.suffix.lower(), 0) + 1

    if not ext_count:
        return

    dominant = max(ext_count, key=ext_count.get)

    ext_to_lang = {
        ".dart": Language.DART,
        ".js": Language.JAVASCRIPT,
        ".jsx": Language.JAVASCRIPT,
        ".ts": Language.TYPESCRIPT,
        ".tsx": Language.TYPESCRIPT,
        ".py": Language.PYTHON,
        ".kt": Language.KOTLIN,
        ".java": Language.JAVA,
        ".swift": Language.SWIFT,
        ".rs": Language.RUST,
        ".go": Language.GO,
        ".cs": Language.CSHARP,
        ".rb": Language.RUBY,
        ".php": Language.PHP,
    }

    stack.language = ext_to_lang.get(dominant, Language.UNKNOWN)


def detect_stack_simple(app_path: Path) -> dict:
    stack = detect_stack(app_path)

    return {
        "framework": stack.framework.value,
        "language": stack.language.value,
        "type": stack.app_type.value,
        "framework_version": stack.framework_version,
        "language_version": stack.language_version,
        "package_manager": stack.package_manager,
        "build_tool": stack.build_tool,
        "has_auth": stack.has_auth,
        "auth_provider": stack.auth_provider,
        "has_api": stack.has_api,
        "has_database": stack.has_database,
        "database": stack.database,
        "has_payments": stack.has_payments,
        "has_file_upload": stack.has_file_upload,
        "has_real_time": stack.has_real_time,
        "has_i18n": stack.has_i18n,
        "has_dark_mode": stack.has_dark_mode,
        "has_offline_support": stack.has_offline_support,
        "has_unit_tests": stack.has_unit_tests,
        "has_e2e_tests": stack.has_e2e_tests,
        "state_management": stack.state_management,
        "router_library": stack.router_library,
        "http_client": stack.http_client,
        "css_framework": stack.css_framework,
        "bundler": stack.bundler,
        "test_framework": stack.test_framework,
        "detected_files": stack.detected_files,
        "raw_dependencies": stack.raw_dependencies,
        "confidence": stack.confidence_score,
    }


# ─── CLI ────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pprint import pprint

    if len(sys.argv) < 2:
        print("Usage: python detect_stack.py /path/to/app")
        sys.exit(1)

    app_path = Path(sys.argv[1]).expanduser().resolve()
    result = detect_stack_simple(app_path)

    pprint(result)