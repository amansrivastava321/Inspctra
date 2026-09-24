import pytest
import sys
from unittest.mock import MagicMock
from qa_ai.live_execution.security_engine import SecurityEngine
from qa_ai.live_execution.playwright_engine import PlaywrightEngine
from qa_ai.product_backend.routers.live_runs import _compute_report
from qa_ai.product_backend import models

def test_no_artifact_store_import_in_backend_security():
    # Verify product_backend does not import ArtifactStore
    for mod in list(sys.modules.keys()):
        if mod.startswith("qa_ai.product_backend"):
            assert "qa_ai.artifact_store" not in sys.modules

def test_security_engine_analyze_response():
    # 1. Insecure http URL warning
    findings = SecurityEngine.analyze_response(
        headers={"Content-Security-Policy": "default-src 'self'"},
        url="http://example.com"
    )
    assert any(f["id"] == "insecure-http" for f in findings)

    # 2. Redirect downgrade warning
    findings = SecurityEngine.analyze_response(
        headers={"Content-Security-Policy": "default-src 'self'"},
        url="http://example.com",
        original_url="https://example.com"
    )
    assert any(f["id"] == "https-to-http-redirect" for f in findings)

    # 3. Missing security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy)
    findings = SecurityEngine.analyze_response(
        headers={},
        url="https://example.com"
    )
    finding_ids = [f["id"] for f in findings]
    assert "missing-csp" in finding_ids
    assert "missing-hsts" in finding_ids
    assert "missing-x-frame-options" in finding_ids
    assert "missing-x-content-type-options" in finding_ids
    assert "missing-referrer-policy" in finding_ids
    assert "missing-permissions-policy" in finding_ids

    # 4. Exposed server & powering headers
    findings = SecurityEngine.analyze_response(
        headers={
            "Server": "nginx/1.18.0",
            "X-Powered-By": "PHP/7.4.3",
            "X-AspNet-Version": "4.0.30319"
        },
        url="https://example.com"
    )
    finding_ids = [f["id"] for f in findings]
    assert "exposed-server" in finding_ids
    assert "exposed-x-powered-by" in finding_ids
    assert "exposed-x-aspnet-version" in finding_ids

def test_security_engine_analyze_cookies():
    # Test insecure cookie attributes
    cookie_headers = [
        "session=123; HttpOnly; SameSite=Lax", # Missing Secure
        "token=abc; Secure; SameSite=Strict", # Missing HttpOnly
        "pref=xyz; Secure; HttpOnly",         # Missing SameSite
        "good=123; Secure; HttpOnly; SameSite=Strict" # Good
    ]
    findings = SecurityEngine.analyze_cookies(cookie_headers)
    finding_ids = [f["id"] for f in findings]
    assert "cookie-missing-secure-session" in finding_ids
    assert "cookie-missing-httponly-token" in finding_ids
    assert "cookie-missing-samesite-pref" in finding_ids
    assert not any("good" in fid for fid in finding_ids)

def test_security_engine_analyze_network():
    # Test mixed content detection
    network_requests = [
        {"url": "https://example.com/logo.png"},
        {"url": "http://example.com/style.css"},
        {"url": "data:image/png;base64,abc"}
    ]
    findings = SecurityEngine.analyze_network(network_requests, "https://example.com")
    assert len(findings) == 1
    assert findings[0]["id"] == "mixed-content"

def test_playwright_engine_redacted_response_headers():
    engine = PlaywrightEngine()
    engine._page = MagicMock()
    
    # Mock playwright response object
    mock_response = MagicMock()
    mock_response.url = "https://example.com"
    mock_response.status = 200
    mock_response.request.method = "GET"
    mock_response.headers = {
        "Content-Security-Policy": "default-src 'self'",
        "Cookie": "session=123",
        "Set-Cookie": "token=abc",
        "Authorization": "Bearer secret",
        "X-Api-Key": "my-secret-key"
    }

    engine._on_response(mock_response)

    # Check unredacted headers cache
    raw_headers = engine.raw_response_headers["https://example.com"]
    assert raw_headers["Authorization"] == "Bearer secret"
    assert raw_headers["Cookie"] == "session=123"

    # Check redacted network summary
    network_item = engine._network_summary[0]
    assert network_item["headers"]["Content-Security-Policy"] == "default-src 'self'"
    assert network_item["headers"]["Authorization"] == "[REDACTED]"
    assert network_item["headers"]["Cookie"] == "[REDACTED]"
    assert network_item["headers"]["Set-Cookie"] == "[REDACTED]"
    assert network_item["headers"]["X-Api-Key"] == "[REDACTED]"

def test_playwright_engine_security_actions():
    engine = PlaywrightEngine()
    engine._page = MagicMock()

    res = engine.execute_action(
        action_type="passive_security_check",
        target="http://example.com",
    )
    assert res["status"] == "passed"
    assert "passive_security_check" in res["notes"]
