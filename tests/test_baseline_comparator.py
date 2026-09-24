from qa_ai.cicd.baseline_comparator import BaselineComparator


def test_baseline_comparator_detects_regression_increase(artifact_store):
    current = {
        "findings": {"critical": 2, "high": 4},
        "coverage_percent": 68.0,
        "evidence": {"count": 2},
    }
    baseline = {
        "findings": {"critical": 1, "high": 3},
        "coverage_percent": 75.0,
        "evidence": {"count": 5},
    }

    result = BaselineComparator(artifact_store).run(current=current, baseline=baseline)

    assert result["deltas"]["critical_findings_delta"] == 1
    assert result["regressions"]["critical_findings_increased"] is True
    assert result["regressions"]["coverage_dropped"] is True

