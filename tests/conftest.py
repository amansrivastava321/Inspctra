"""
conftest.py - Shared test fixtures for the QA platform test suite.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from qa_ai.runtime.artifact_store import ArtifactStore, reset_artifact_store


@pytest.fixture
def tmp_dir():
    """Provide a temporary directory that is cleaned up after the test."""
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def artifact_store(tmp_dir):
    """Provide a fresh ArtifactStore in a temp directory."""
    reset_artifact_store()
    store = ArtifactStore(base_dir=tmp_dir / "artifacts")
    yield store
    reset_artifact_store()


@pytest.fixture
def sample_app_map():
    """Provide a minimal app_map dict for testing."""
    return {
        "metadata": {
            "app_name": "test-app",
            "app_path": "/tmp/test-app",
            "discovered_at": "2026-01-01T00:00:00+00:00",
            "discovery_version": "1.0.0",
            "generated_by": "DiscoveryAgent",
        },
        "stack": {
            "framework": "fastapi",
            "language": "python",
            "app_type": "backend",
            "capabilities": {
                "has_auth": True,
                "has_api": True,
                "has_database": False,
                "has_payments": False,
            },
            "confidence": 0.9,
        },
        "screens": [
            {"name": "Home", "path": "/", "auth_required": False},
            {"name": "Dashboard", "path": "/dashboard", "auth_required": True},
        ],
        "api_endpoints": [
            {
                "method": "GET",
                "path": "/users",
                "auth_required": False,
                "confidence": 0.8,
                "risk": {"risk_level": "low", "mutates_data": False},
            },
            {
                "method": "POST",
                "path": "/users",
                "auth_required": True,
                "confidence": 0.9,
                "risk": {"risk_level": "high", "mutates_data": True},
            },
        ],
        "critical_flows": [
            {
                "name": "auth_flow",
                "priority": "critical",
                "type": "auth",
                "steps": ["login", "access dashboard"],
                "expected_outcome": "User reaches dashboard",
            },
        ],
        "security_surfaces": {
            "public_endpoints": [],
            "auth_endpoints": [],
            "payment_endpoints": [],
            "admin_endpoints": [],
        },
        "testability": {
            "has_unit_tests": True,
            "has_e2e_tests": False,
            "test_framework": "pytest",
        },
    }


@pytest.fixture
def sample_test_plan():
    """Provide a minimal test_plan dict for testing."""
    return {
        "metadata": {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "plan_version": "2.0.0",
            "generated_by": "LLMTestPlanner",
            "model": "test-model",
        },
        "summary": {
            "total_tests": 3,
            "by_suite": {"smoke": 1, "functional": 1, "security": 1},
            "by_priority": {"P0": 1, "P1": 1, "P2": 1},
        },
        "test_suites": {
            "smoke": [
                {
                    "id": "TEST-0001",
                    "title": "Smoke: App loads",
                    "type": "smoke",
                    "priority": "P0",
                    "risk": "critical",
                    "steps": ["Launch app"],
                    "expected_result": "App loads",
                },
            ],
            "functional": [
                {
                    "id": "TEST-0002",
                    "title": "GET /users returns 200",
                    "type": "functional",
                    "priority": "P1",
                    "risk": "medium",
                    "steps": ["Call GET /users"],
                    "expected_result": "200 OK",
                },
            ],
            "security": [
                {
                    "id": "TEST-0003",
                    "title": "Public endpoint no PII leak",
                    "type": "security",
                    "priority": "P2",
                    "risk": "high",
                    "steps": ["Call without auth"],
                    "expected_result": "No PII leaked",
                },
            ],
            "performance": [],
            "accessibility": [],
            "negative": [],
            "edge_case": [],
            "regression": [],
        },
    }
