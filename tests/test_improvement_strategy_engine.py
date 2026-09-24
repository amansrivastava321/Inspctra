from qa_ai.ai_orchestration.improvement_strategy_engine import ImprovementStrategyEngine


def test_improvement_strategy_uses_validated_findings(artifact_store):
    artifact_store.save_artifact(
        "verified_findings",
        {
            "findings": [
                {
                    "id": "F-1",
                    "title": "Auth bypass",
                    "severity": "critical",
                    "category": "security",
                    "evidence_refs": ["trace-1"],
                }
            ]
        },
        agent="test",
    )

    result = ImprovementStrategyEngine(artifact_store).run()
    assert result["summary"]["uses_validated_findings_only"] is True
    assert result["summary"]["improvement_count"] == 1
    assert result["improvements"][0]["source_finding_id"] == "F-1"

