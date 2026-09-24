from qa_ai.cicd_runtime.baseline_comparison_engine import BaselineComparisonEngine


def test_baseline_comparison_engine_detects_regressions_and_instability(artifact_store):
    current = {
        "regression_guard_report": {"summary": {"new_findings": 3, "resolved_findings": 1, "worsened_findings": 2}},
        "evidence_graph": {"summary": {"total_evidence": 2}},
        "replay_analysis": {"comparison": {"total_regressions": 4}},
    }
    baseline = {
        "regression_guard_report": {"summary": {"new_findings": 1, "resolved_findings": 0, "worsened_findings": 0}},
        "evidence_graph": {"summary": {"total_evidence": 5}},
        "replay_analysis": {"comparison": {"total_regressions": 1}},
    }

    result = BaselineComparisonEngine(artifact_store).run(current=current, baseline=baseline)

    assert result["regressions"]["new_regressions"] == 2
    assert result["regressions"]["evidence_quality_degradation"] is True
    assert result["regressions"]["runtime_instability_increase"] is True
