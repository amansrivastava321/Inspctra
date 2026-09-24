import pytest
import sys
from unittest.mock import MagicMock
from qa_ai.live_execution.a11y_engine import A11yEngine
from qa_ai.live_execution.playwright_engine import PlaywrightEngine
from qa_ai.product_backend.routers.live_runs import _compute_report
from qa_ai.product_backend import models

def test_no_artifact_store_import_in_backend_a11y():
    # Verify product_backend does not import ArtifactStore
    for mod in list(sys.modules.keys()):
        if mod.startswith("qa_ai.product_backend"):
            assert "qa_ai.artifact_store" not in sys.modules

def test_a11y_engine_scan_page():
    mock_page = MagicMock()
    mock_page.evaluate.return_value = {
        "violations": [
            {"rule_id": "image-missing-alt", "severity": "critical", "selector": "img", "html": "<img>"},
            {"rule_id": "input-missing-label", "severity": "serious", "selector": "input", "html": "<input>"}
        ],
        "passed_count": 5
    }

    engine = A11yEngine()
    res = engine.scan_page(mock_page)

    assert res["total_violations"] == 2
    assert res["critical_violations"] == 1
    assert res["serious_violations"] == 1
    assert res["passed_count"] == 5
    assert len(res["violations"]) == 2

def test_playwright_engine_accessibility_scan():
    engine = PlaywrightEngine()
    engine._page = MagicMock()
    
    mock_a11y_result = {
        "violations": [
            {"rule_id": "image-missing-alt", "severity": "critical", "selector": "img", "html": "<img>"}
        ],
        "passed_count": 3
    }
    # a11y_engine.scan_page is called via page.evaluate mock
    engine._page.evaluate.return_value = mock_a11y_result
    
    res = engine.execute_action(
        action_type="accessibility_scan",
        target="http://example.com/a11y",
    )
    
    assert res["status"] == "passed"
    assert res["a11y_result"]["total_violations"] == 1
    assert res["warning"] is True

def test_playwright_engine_assert_no_critical_a11y_violations_pass():
    engine = PlaywrightEngine()
    engine._page = MagicMock()
    
    mock_a11y_result = {
        "violations": [
            {"rule_id": "link-missing-name", "severity": "serious", "selector": "a", "html": "<a>"}
        ],
        "passed_count": 4
    }
    engine._page.evaluate.return_value = mock_a11y_result
    
    res = engine.execute_action(
        action_type="assert_no_critical_a11y_violations",
        target="http://example.com/a11y",
    )
    
    assert res["status"] == "passed"
    assert res["a11y_result"]["total_violations"] == 1
    assert res["a11y_result"]["critical_violations"] == 0
    assert res["warning"] is True

def test_playwright_engine_assert_no_critical_a11y_violations_fail():
    engine = PlaywrightEngine()
    engine._page = MagicMock()
    
    mock_a11y_result = {
        "violations": [
            {"rule_id": "image-missing-alt", "severity": "critical", "selector": "img", "html": "<img>"}
        ],
        "passed_count": 4
    }
    engine._page.evaluate.return_value = mock_a11y_result
    
    res = engine.execute_action(
        action_type="assert_no_critical_a11y_violations",
        target="http://example.com/a11y",
    )
    
    assert res["status"] == "failed"
    assert "actual 1 critical violation(s)" in res["notes"]
    assert res["warning"] is True

def test_playwright_engine_assert_no_a11y_violations_fail():
    engine = PlaywrightEngine()
    engine._page = MagicMock()
    
    mock_a11y_result = {
        "violations": [
            {"rule_id": "link-missing-name", "severity": "serious", "selector": "a", "html": "<a>"}
        ],
        "passed_count": 4
    }
    engine._page.evaluate.return_value = mock_a11y_result
    
    res = engine.execute_action(
        action_type="assert_no_a11y_violations",
        target="http://example.com/a11y",
    )
    
    assert res["status"] == "failed"
    assert "actual 1 violation(s)" in res["notes"]
    assert res["warning"] is True
