# QA-AI Unified Summary

- Health Score: 95.0 (excellent)
- Risk Level: high
- Regression Detected: False

## Raw Summary
```json
{
  "health": {
    "overall_score": 95.0,
    "health_level": "excellent",
    "dimensions": {
      "security": {
        "score": 85.0,
        "weight": 0.2,
        "weighted_score": 17.0
      },
      "code_quality": {
        "score": 100.0,
        "weight": 0.15,
        "weighted_score": 15.0
      },
      "runtime": {
        "score": 100.0,
        "weight": 0.15,
        "weighted_score": 15.0
      },
      "release": {
        "score": 100.0,
        "weight": 0.1,
        "weighted_score": 10.0
      },
      "sync": {
        "score": 100.0,
        "weight": 0.1,
        "weighted_score": 10.0
      },
      "database": {
        "score": 100.0,
        "weight": 0.1,
        "weighted_score": 10.0
      },
      "evidence": {
        "score": 75.0,
        "weight": 0.08,
        "weighted_score": 6.0
      },
      "regression": {
        "score": 100.0,
        "weight": 0.12,
        "weighted_score": 12.0
      }
    }
  },
  "risk": {
    "risk_level": "high",
    "overall_risk_score": 55,
    "top_risks": [
      {
        "id": "F1",
        "title": "Missing auth on GET /users",
        "severity": "high",
        "category": "security",
        "file_path": "qa_ai/audit/api_audit.py",
        "api_endpoint": "GET /users"
      }
    ],
    "risk_distribution": {}
  },
  "regressions": {
    "regression_detected": false,
    "summary": {
      "new_findings": 0,
      "resolved_findings": 0,
      "worsened_findings": 0,
      "new_test_failures": 0
    }
  },
  "improvements": {
    "fix_plan_summary": {
      "total_fixes": 1,
      "low_risk": 0,
      "medium_risk": 0,
      "high_risk": 1
    },
    "backlog_summary": {
      "total_items": 1,
      "top_priority": "IMP-001",
      "health_score": 95.0,
      "health_level": "excellent"
    }
  },
  "evidence": {
    "graph_summary": {},
    "index_summary": {}
  },
  "runtime": {
    "trace_summary": {},
    "network_summary": {},
    "replay_summary": {}
  },
  "workflow": {
    "status": null,
    "phases": []
  },
  "graphify": {
    "report_preview": "# Graph Report - .  (2026-05-14)\n\n## Corpus Check\n- 187 files \u00b7 ~92,600 words\n- Verdict: corpus is large enough that graph structure adds value.\n\n## Summary\n- 2738 nodes \u00b7 9392 edges \u00b7 82 communities detected\n- Extraction: 38% EXTRACTED \u00b7 62% INFERRED \u00b7 0% AMBIGUOUS \u00b7 INFERRED: 5848 edges (avg confidence: 0.5)\n- Token cost: 0 input \u00b7 0 output\n\n## God Nodes (most connected - your core abstractions)",
    "graph_nodes": 2738,
    "graph_edges": 9392
  },
  "release_readiness": {},
  "artifact_metadata": {
    "schema_version": "1.0",
    "generated_by": "AuditSummaryBuilder",
    "generated_at": "2026-05-14T11:05:52.287948+00:00",
    "artifact_type": "audit_summary"
  },
  "created_at": "2026-05-14T11:05:52.287948+00:00",
  "metadata": {}
}
```