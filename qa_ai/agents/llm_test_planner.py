"""
llm_test_planner.py - Production-grade LLM-powered test planner.
Fixed: app_map access, f-string bugs, enum safety, deterministic generators.
"""

from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

from qa_ai.ai.ollama_client import OllamaClient
from qa_ai.runtime.artifact_store import ArtifactStore


# ─── Data Models ───────────────────────────────────────

class TestType(str, Enum):
    SMOKE = "smoke"
    FUNCTIONAL = "functional"
    SECURITY = "security"
    PERFORMANCE = "performance"
    ACCESSIBILITY = "accessibility"
    NEGATIVE = "negative"
    EDGE_CASE = "edge_case"
    REGRESSION = "regression"


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TestCase:
    id: str
    title: str
    type: TestType
    priority: Priority
    risk: RiskLevel
    target: Dict[str, Optional[str]] = field(default_factory=dict)
    preconditions: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    expected_result: str = ""
    reasoning: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type.value,
            "priority": self.priority.value,
            "risk": self.risk.value,
            "target": self.target,
            "preconditions": self.preconditions,
            "steps": self.steps,
            "expected_result": self.expected_result,
            "reasoning": self.reasoning,
            "tags": self.tags,
        }


# ─── Safe Enum Parsers ─────────────────────────────────

def _safe_priority(value: Any, default: Priority = Priority.P1) -> Priority:
    try:
        cleaned = str(value).upper().strip().replace(" ", "")
        return Priority(cleaned)
    except (ValueError, KeyError):
        return default


def _safe_risk(value: Any, default: RiskLevel = RiskLevel.MEDIUM) -> RiskLevel:
    try:
        cleaned = str(value).lower().strip().replace(" ", "_")
        return RiskLevel(cleaned)
    except (ValueError, KeyError):
        return default


# ─── App Map Access Helpers ────────────────────────────

def _get_stack(app_map: dict) -> dict:
    return app_map.get("stack", {})


def _get_capabilities(app_map: dict) -> dict:
    return _get_stack(app_map).get("capabilities", {})


def _has_auth(app_map: dict) -> bool:
    return _get_capabilities(app_map).get("has_auth", False)


def _has_payments(app_map: dict) -> bool:
    return _get_capabilities(app_map).get("has_payments", False)


def _has_database(app_map: dict) -> bool:
    return _get_capabilities(app_map).get("has_database", False)


def _has_file_upload(app_map: dict) -> bool:
    return _get_capabilities(app_map).get("has_file_upload", False)


def _has_offline_support(app_map: dict) -> bool:
    return _get_capabilities(app_map).get("has_offline_support", False)


# ─── System Prompts ────────────────────────────────────

SYSTEM_PROMPT_BASE = """You are an expert QA architect testing a mission-critical application.
Your job is to find bugs before users do. Be thorough, adversarial, and precise.

Output ONLY valid JSON. No explanations outside the JSON structure.
Use lowercase for risk levels: critical, high, medium, low.
Use uppercase for priorities: P0, P1, P2."""

FUNCTIONAL_TEST_PROMPT = """Generate functional test cases for this application screen.

Screen details:
{context}

Output JSON:
{{"test_cases": [{{"title": "...", "steps": ["step1", "step2"], "expected_result": "...", "priority": "P0", "risk": "high"}}]}}"""

SECURITY_TEST_PROMPT = """Generate security test cases for this API endpoint.

API details:
{context}

Output JSON:
{{"test_cases": [{{"title": "...", "steps": ["step1", "step2"], "expected_result": "...", "priority": "P0", "risk": "critical"}}]}}"""

PERFORMANCE_TEST_PROMPT = """Generate performance test cases.

Context:
{context}

Output JSON:
{{"test_cases": [{{"title": "...", "steps": ["step1", "step2"], "expected_result": "...", "priority": "P2"}}]}}"""

ACCESSIBILITY_TEST_PROMPT = """Generate accessibility test cases for this screen.

{context}

Output JSON:
{{"test_cases": [{{"title": "...", "steps": ["step1", "step2"], "expected_result": "...", "priority": "P2"}}]}}"""


# ─── Main Planner ──────────────────────────────────────

class LLMTestPlanner:
    """Production-grade test planner with safe LLM integration."""

    def __init__(
        self,
        artifact_store: ArtifactStore,
        model: str = "phi4-mini:latest",
        max_retries: int = 3,
        batch_delay: float = 0.5,
    ):
        self.store = artifact_store
        self.llm = OllamaClient()
        self.model = model
        self.max_retries = max_retries
        self.batch_delay = batch_delay
        self.test_counter = 0
        self.all_tests: List[TestCase] = []

    def generate_plan(self, app_map: dict) -> dict:
        self.test_counter = 0
        self.all_tests = []

        screens = app_map.get("screens", [])
        apis = app_map.get("api_endpoints", [])
        critical_flows = app_map.get("critical_flows", [])
        testability = app_map.get("testability", {})

        # Deterministic tests always run
        self._generate_smoke_tests(screens, critical_flows)
        self._generate_auth_tests(app_map)
        self._generate_payment_tests(app_map)
        self._generate_public_endpoint_tests(app_map)
        self._generate_admin_access_tests(app_map)
        self._generate_file_upload_tests(app_map)
        self._generate_offline_sync_tests(app_map)
        self._generate_edge_case_tests(app_map)
        self._generate_regression_tests(app_map)

        # LLM-assisted tests
        for screen in screens:
            self._generate_screen_tests(screen)
            self._generate_accessibility_tests(screen)
            time.sleep(self.batch_delay)

        for api in apis:
            if ((api.get("method") or "GET") or "GET").upper() in ["POST", "PUT", "PATCH", "DELETE"]:
                self._generate_api_security_tests(api)
                self._generate_api_negative_tests(api)
            else:
                self._generate_api_basic_tests(api)
            time.sleep(self.batch_delay)

        self._generate_performance_tests(screens, apis, critical_flows, app_map)

        # Finalize
        self._deduplicate_tests()
        self._enforce_coverage(screens, apis)

        test_plan = self._assemble_plan()
        self.store.save_artifact("test_plan", test_plan, version="2.1.0", metadata={"source": "LLMTestPlanner"})
        return test_plan

    # ─── Deterministic Generators ──────────────────────

    def _generate_smoke_tests(self, screens, flows):
        if screens:
            s = screens[0]
            self.all_tests.append(TestCase(id=self._next_id(), title=f"Smoke: Launch to {s.get('name', 'home')}", type=TestType.SMOKE, priority=Priority.P0, risk=RiskLevel.CRITICAL, target={"screen": s.get("path") or s.get("name")}, steps=["Launch app"], expected_result="App loads without crash", tags=["smoke"]))
        for f in flows[:3]:
            self.all_tests.append(TestCase(id=self._next_id(), title=f"Smoke: {f.get('name', 'flow')}", type=TestType.SMOKE, priority=Priority.P0, risk=RiskLevel.CRITICAL, target={"flow": f.get("name")}, steps=[f"Execute {f.get('name')}"], expected_result=f.get("expected_outcome", "Completes"), tags=["smoke"]))

    def _generate_auth_tests(self, app_map):
        if not _has_auth(app_map):
            return
        for ep in app_map.get("security_surfaces", {}).get("auth_endpoints", []):
            self.all_tests.append(TestCase(id=self._next_id(), title=f"Brute force: {ep.get('method')} {ep.get('path')}", type=TestType.SECURITY, priority=Priority.P0, risk=RiskLevel.CRITICAL, target={"api": f"{ep.get('method')} {ep.get('path')}"}, steps=["Send 20 rapid invalid requests"], expected_result="Rate limited after 5-10 attempts", tags=["security", "auth"]))
        self.all_tests.append(TestCase(id=self._next_id(), title="Expired token rejection", type=TestType.SECURITY, priority=Priority.P0, risk=RiskLevel.CRITICAL, target={}, steps=["Use expired token on protected endpoint"], expected_result="401 Unauthorized", tags=["security", "token"]))

    def _generate_payment_tests(self, app_map):
        if not _has_payments(app_map):
            return
        for ep in app_map.get("security_surfaces", {}).get("payment_endpoints", []):
            self.all_tests.append(TestCase(id=self._next_id(), title=f"Idempotency: {ep.get('method')} {ep.get('path')}", type=TestType.SECURITY, priority=Priority.P0, risk=RiskLevel.CRITICAL, target={"api": f"{ep.get('method')} {ep.get('path')}"}, steps=["Send duplicate with same idempotency key"], expected_result="Only one charge processed", tags=["payment"]))
            self.all_tests.append(TestCase(id=self._next_id(), title=f"Negative amount: {ep.get('method')} {ep.get('path')}", type=TestType.NEGATIVE, priority=Priority.P0, risk=RiskLevel.CRITICAL, target={"api": f"{ep.get('method')} {ep.get('path')}"}, steps=["Send negative amount"], expected_result="Rejected with validation error", tags=["payment"]))

    def _generate_public_endpoint_tests(self, app_map):
        for ep in app_map.get("security_surfaces", {}).get("public_endpoints", []):
            self.all_tests.append(TestCase(id=self._next_id(), title=f"Public exposure: {ep.get('method')} {ep.get('path')}", type=TestType.SECURITY, priority=Priority.P0, risk=RiskLevel.HIGH, target={"api": f"{ep.get('method')} {ep.get('path')}"}, steps=["Call without auth", "Check response"], expected_result="No PII or internal data leaked", tags=["security"]))

    def _generate_admin_access_tests(self, app_map):
        for ep in app_map.get("security_surfaces", {}).get("admin_endpoints", []):
            self.all_tests.append(TestCase(id=self._next_id(), title=f"Admin bypass: {ep.get('method')} {ep.get('path')}", type=TestType.SECURITY, priority=Priority.P0, risk=RiskLevel.CRITICAL, target={"api": f"{ep.get('method')} {ep.get('path')}"}, steps=["Call as normal user"], expected_result="403 Forbidden", tags=["admin"]))

    def _generate_file_upload_tests(self, app_map):
        if not _has_file_upload(app_map):
            return
        for ep in app_map.get("security_surfaces", {}).get("file_upload_endpoints", []):
            self.all_tests.append(TestCase(id=self._next_id(), title=f"Oversized file: {ep.get('method')} {ep.get('path')}", type=TestType.NEGATIVE, priority=Priority.P1, risk=RiskLevel.HIGH, target={"api": f"{ep.get('method')} {ep.get('path')}"}, steps=["Upload 500MB file"], expected_result="Rejected with size limit", tags=["upload"]))
            self.all_tests.append(TestCase(id=self._next_id(), title=f"Malicious file: {ep.get('method')} {ep.get('path')}", type=TestType.SECURITY, priority=Priority.P0, risk=RiskLevel.CRITICAL, target={"api": f"{ep.get('method')} {ep.get('path')}"}, steps=["Upload .exe, .php, .pdf.exe"], expected_result="All rejected", tags=["upload"]))

    def _generate_offline_sync_tests(self, app_map):
        if not _has_offline_support(app_map):
            return
        self.all_tests.append(TestCase(id=self._next_id(), title="Offline then reconnect", type=TestType.EDGE_CASE, priority=Priority.P1, risk=RiskLevel.HIGH, target={}, steps=["Go offline", "Make changes", "Go online"], expected_result="Data syncs without loss", tags=["offline"]))

    def _generate_edge_case_tests(self, app_map):
        has_auth = _has_auth(app_map)
        cases = [
            ("Deep link protected route without auth", ["Kill app", "Open deep link"], "Redirect to login", True),
            ("Rapid double-click submit", ["Click submit rapidly"], "Only one submission", False),
            ("Back button during form", ["Fill partially", "Press back"], "Confirmation or autosave", False),
            ("Network disconnect during API call", ["Trigger API", "Disconnect"], "Graceful error", False),
            ("Concurrent sessions", ["Login on A", "Login on B", "Conflict"], "No corruption", True),
        ]
        for title, steps, expected, requires_auth in cases:
            if requires_auth and not has_auth:
                continue
            self.all_tests.append(TestCase(id=self._next_id(), title=f"Edge: {title}", type=TestType.EDGE_CASE, priority=Priority.P2, risk=RiskLevel.HIGH if requires_auth else RiskLevel.MEDIUM, target={}, steps=steps, expected_result=expected, tags=["edge_case"]))

    def _generate_regression_tests(self, app_map):
        if app_map.get("testability", {}).get("has_e2e_tests"):
            self.all_tests.append(TestCase(id=self._next_id(), title="Run existing E2E suite", type=TestType.REGRESSION, priority=Priority.P1, risk=RiskLevel.HIGH, target={}, steps=["Execute E2E runner"], expected_result="All pass", tags=["regression"]))

    # ─── LLM-Assisted Generators ────────────────────────

    def _generate_screen_tests(self, screen):
        context = json.dumps({"name": screen.get("name"), "path": screen.get("path")})
        resp = self._call_llm(FUNCTIONAL_TEST_PROMPT.format(context=context), ["test_cases"])
        for tc in resp.get("test_cases", []):
            self.all_tests.append(TestCase(id=self._next_id(), title=tc.get("title", f"Test {screen.get('name')}"), type=TestType.FUNCTIONAL, priority=_safe_priority(tc.get("priority")), risk=_safe_risk(tc.get("risk")), target={"screen": screen.get("path") or screen.get("name")}, steps=tc.get("steps", []), expected_result=tc.get("expected_result", ""), tags=["functional"]))

    def _generate_accessibility_tests(self, screen):
        context = json.dumps({"name": screen.get("name")})
        resp = self._call_llm(ACCESSIBILITY_TEST_PROMPT.format(context=context), ["test_cases"])
        for tc in resp.get("test_cases", []):
            self.all_tests.append(TestCase(id=self._next_id(), title=f"A11y: {tc.get('title', screen.get('name'))}", type=TestType.ACCESSIBILITY, priority=_safe_priority(tc.get("priority", "P2")), risk=RiskLevel.LOW, target={"screen": screen.get("path") or screen.get("name")}, steps=tc.get("steps", []), expected_result=tc.get("expected_result", ""), tags=["a11y"]))

    def _generate_api_security_tests(self, api):
        context = json.dumps({"method": (api.get("method") or "GET"), "path": api.get("path")})
        resp = self._call_llm(SECURITY_TEST_PROMPT.format(context=context), ["test_cases"])
        for tc in resp.get("test_cases", []):
            self.all_tests.append(TestCase(id=self._next_id(), title=f"Security: {tc.get('title', api.get('path'))}", type=TestType.SECURITY, priority=_safe_priority(tc.get("priority", "P0")), risk=_safe_risk(tc.get("risk", "critical")), target={"api": f"{api.get('method')} {api.get('path')}"}, steps=tc.get("steps", []), expected_result=tc.get("expected_result", ""), tags=["security"]))

    def _generate_api_negative_tests(self, api):
        self.all_tests.append(TestCase(id=self._next_id(), title=f"Invalid body: {api.get('method')} {api.get('path')}", type=TestType.NEGATIVE, priority=Priority.P1, risk=RiskLevel.MEDIUM, target={"api": f"{api.get('method')} {api.get('path')}"}, steps=["Send malformed JSON"], expected_result="400 Bad Request", tags=["negative"]))
        self.all_tests.append(TestCase(id=self._next_id(), title=f"Missing fields: {api.get('method')} {api.get('path')}", type=TestType.NEGATIVE, priority=Priority.P1, risk=RiskLevel.MEDIUM, target={"api": f"{api.get('method')} {api.get('path')}"}, steps=["Send empty body"], expected_result="422 Unprocessable", tags=["negative"]))

    def _generate_api_basic_tests(self, api):
        self.all_tests.append(TestCase(id=self._next_id(), title=f"API: {api.get('method')} {api.get('path')}", type=TestType.FUNCTIONAL, priority=Priority.P1, risk=RiskLevel.MEDIUM, target={"api": f"{api.get('method')} {api.get('path')}"}, steps=[f"Call {api.get('method')} {api.get('path')}"], expected_result="200 OK", tags=["functional"]))

    def _generate_performance_tests(self, screens, apis, flows, app_map):
        context = json.dumps({"screens": len(screens), "apis": len(apis), "has_db": _has_database(app_map)})
        resp = self._call_llm(PERFORMANCE_TEST_PROMPT.format(context=context), ["test_cases"])
        for tc in resp.get("test_cases", []):
            self.all_tests.append(TestCase(id=self._next_id(), title=f"Perf: {tc.get('title', 'test')}", type=TestType.PERFORMANCE, priority=_safe_priority(tc.get("priority", "P2")), risk=RiskLevel.MEDIUM, target={}, steps=tc.get("steps", []), expected_result=tc.get("expected_result", ""), tags=["performance"]))

    # ─── LLM Call ──────────────────────────────────────

    def _call_llm(self, prompt, expected_keys, retries=None):
        if retries is None:
            retries = self.max_retries
        for attempt in range(retries):
            try:
                resp = self.llm.chat_json(model=self.model, prompt=prompt, system=SYSTEM_PROMPT_BASE, temperature=0.2)
                if all(k in resp for k in expected_keys):
                    return resp
            except Exception as e:
                logger.debug("LLM call failed (attempt %d): %s", attempt + 1, e)
                time.sleep(1 * (attempt + 1))
        return {k: [] for k in expected_keys}

    # ─── Deduplication ──────────────────────────────────

    def _deduplicate_tests(self):
        seen, unique = set(), []
        for t in self.all_tests:
            n = t.title.lower().strip().rstrip(".!?")
            if n not in seen:
                seen.add(n)
                unique.append(t)
        self.all_tests = unique

    # ─── Coverage Enforcement ───────────────────────────

    def _enforce_coverage(self, screens, apis):
        covered_s = {t.target["screen"] for t in self.all_tests if t.target.get("screen")}
        covered_a = {t.target["api"] for t in self.all_tests if t.target.get("api")}
        for s in screens:
            sid = s.get("path") or s.get("name")
            if sid and sid not in covered_s:
                self.all_tests.append(TestCase(id=self._next_id(), title=f"Navigate to {sid}", type=TestType.FUNCTIONAL, priority=Priority.P1, risk=RiskLevel.MEDIUM, target={"screen": sid}, steps=[f"Navigate to {sid}"], expected_result="Screen renders", tags=["coverage"]))
        for a in apis:
            aid = f"{a.get('method')} {a.get('path')}"
            if aid and aid not in covered_a:
                self.all_tests.append(TestCase(id=self._next_id(), title=f"API: {aid}", type=TestType.FUNCTIONAL, priority=Priority.P1, risk=RiskLevel.MEDIUM, target={"api": aid}, steps=[f"Call {aid}"], expected_result="Valid response", tags=["coverage"]))

    # ─── Assembly ───────────────────────────────────────

    def _assemble_plan(self) -> dict:
        suites = {"smoke": [], "functional": [], "security": [], "performance": [], "accessibility": [], "negative": [], "edge_case": [], "regression": []}
        for t in self.all_tests:
            key = t.type.value
            if key in suites:
                suites[key].append(t.to_dict())
        total = len(self.all_tests)
        return {
            "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(), "plan_version": "2.1.0", "generated_by": "LLMTestPlanner", "model": self.model},
            "summary": {"total_tests": total, "by_suite": {k: len(v) for k, v in suites.items()}, "by_priority": {"P0": sum(1 for t in self.all_tests if t.priority == Priority.P0), "P1": sum(1 for t in self.all_tests if t.priority == Priority.P1), "P2": sum(1 for t in self.all_tests if t.priority == Priority.P2)}},
            "test_suites": suites,
        }

    def _next_id(self) -> str:
        self.test_counter += 1
        return f"TEST-{self.test_counter:04d}"