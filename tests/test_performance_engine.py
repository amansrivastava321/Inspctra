import pytest
import sys
from unittest.mock import MagicMock, patch
from qa_ai.live_execution.playwright_engine import PlaywrightEngine
from qa_ai.live_execution.api_engine import ApiEngine
from qa_ai.product_backend.routers.live_runs import _compute_report
from qa_ai.product_backend import models

def test_no_artifact_store_import_in_backend():
    # Verify product_backend does not import ArtifactStore
    # We check sys.modules
    for mod in list(sys.modules.keys()):
        if mod.startswith("qa_ai.product_backend"):
            # Ensure it hasn't imported artifact_store
            assert "qa_ai.artifact_store" not in sys.modules

def test_validation_step_model_validation():
    # Test step validation for budget and warn thresholds
    step = models.ValidationStep(
        description="Check page load time",
        action_type="measure_page_load",
        budget_ms=3000,
        warn_ms=1500,
        metric_name="dom_content_loaded_ms"
    )
    assert step.budget_ms == 3000
    assert step.warn_ms == 1500
    assert step.metric_name == "dom_content_loaded_ms"

    # Verify negative budget/timeout checks or model defaults
    create_step = models.TestCaseStepCreate(
        action_type="assert_page_load_under",
        budget_ms=1000,
        warn_ms=500
    )
    assert create_step.budget_ms == 1000
    assert create_step.warn_ms == 500

def test_playwright_engine_measure_page_load():
    engine = PlaywrightEngine()
    engine._page = MagicMock()
    
    mock_metrics = {
        "navigation_start": 0,
        "dom_content_loaded_ms": 200,
        "load_event_ms": 500,
        "first_byte_ms": 50,
        "total_load_ms": 600,
        "resource_count": 10,
        "total_transfer_size": 50000,
        "slow_resource_count": 1
    }
    engine._page.evaluate.return_value = mock_metrics
    
    res = engine.execute_action(
        action_type="measure_page_load",
        target="http://example.com/test",
        metric_name="total_load_ms"
    )
    
    assert res["status"] == "passed"
    assert res["metrics"] == mock_metrics
    assert "total_load_ms" in res["notes"]

def test_playwright_engine_assert_page_load_under_pass():
    engine = PlaywrightEngine()
    engine._page = MagicMock()
    
    mock_metrics = {
        "navigation_start": 0,
        "dom_content_loaded_ms": 100,
        "load_event_ms": 250,
        "first_byte_ms": 30,
        "total_load_ms": 300,
        "resource_count": 5,
        "total_transfer_size": 20000,
        "slow_resource_count": 0
    }
    engine._page.evaluate.return_value = mock_metrics
    
    res = engine.execute_action(
        action_type="assert_page_load_under",
        target="http://example.com/test",
        budget_ms=500,
        warn_ms=200,
        metric_name="total_load_ms"
    )
    
    assert res["status"] == "passed"
    assert res["warning"] is True  # 300ms actual > 200ms warning
    assert "budget 500ms" in res["notes"]

def test_playwright_engine_assert_page_load_under_fail():
    engine = PlaywrightEngine()
    engine._page = MagicMock()
    
    mock_metrics = {
        "navigation_start": 0,
        "dom_content_loaded_ms": 800,
        "load_event_ms": 1200,
        "first_byte_ms": 100,
        "total_load_ms": 1500,
        "resource_count": 15,
        "total_transfer_size": 80000,
        "slow_resource_count": 3
    }
    engine._page.evaluate.return_value = mock_metrics
    
    res = engine.execute_action(
        action_type="assert_page_load_under",
        target="http://example.com/test",
        budget_ms=1000,
        metric_name="total_load_ms"
    )
    
    assert res["status"] == "failed"
    assert "budget 1000ms" in res["notes"]
    assert res["metrics"] == mock_metrics

def test_api_engine_assert_response_time_under_pass():
    api_engine = ApiEngine()
    
    context = {
        "last_response": {
            "status_code": 200,
            "response_time_ms": 120.5,
            "body_preview": "ok"
        }
    }
    
    step = {
        "action_type": "assert_api_response_time_under",
        "budget_ms": 200,
        "warn_ms": 100
    }
    
    res = api_engine.execute_step(step, app_target={}, context=context)
    
    assert res["status"] == "passed"
    assert res["warning"] is True  # 120.5ms > 100ms warning
    assert "120.5ms <= 200.0ms" in res["notes"]

def test_api_engine_assert_response_time_under_fail():
    api_engine = ApiEngine()
    
    context = {
        "last_response": {
            "status_code": 200,
            "response_time_ms": 250.0,
            "body_preview": "ok"
        }
    }
    
    step = {
        "action_type": "assert_api_response_time_under",
        "budget_ms": 200
    }
    
    res = api_engine.execute_step(step, app_target={}, context=context)
    
    assert res["status"] == "failed"
    assert "Assertion failed" in res["notes"]

def test_report_includes_performance_summary():
    mock_storage = MagicMock()
    mock_storage.list_evidence.return_value = []
    mock_storage.get_validation_pack.return_value = {"name": "Test Pack"}
    mock_storage.get_app_target.return_value = {"name": "Test App"}

    run_row = {
        "pack_id": "pack-1",
        "app_target_id": "app-1",
        "execution_mode": "automated",
        "step_results": [
            {
                "action_type": "measure_page_load",
                "status": "passed",
                "metrics": {"total_load_ms": 800.0, "dom_content_loaded_ms": 300.0},
                "metric_name": "total_load_ms"
            },
            {
                "action_type": "assert_page_load_under",
                "status": "passed",
                "metrics": {"total_load_ms": 400.0},
                "metric_name": "total_load_ms"
            },
            {
                "action_type": "assert_api_response_time_under",
                "status": "failed",
                "response_time_ms": 350.0
            }
        ]
    }

    report = _compute_report("run-123", run_row, mock_storage)

    assert report["perf_total_checks"] == 3
    assert report["perf_passed_budgets"] == 1  # 2nd step (assertion passed)
    assert report["perf_failed_budgets"] == 1  # 3rd step (assertion failed)
    assert report["perf_avg_page_load_ms"] == 600.0  # (800 + 400) / 2
    assert report["perf_avg_api_response_time_ms"] == 350.0
    assert report["perf_slowest_check_ms"] == 800.0

    # Validate schema parsing
    record = models.ReportRecord(id="rep-123", run_id="run-123", name="Perf Report", **report)
    assert record.perf_total_checks == 3
    assert record.perf_avg_page_load_ms == 600.0
    assert record.perf_avg_api_response_time_ms == 350.0
