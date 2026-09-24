"""
test_graph_visualizer.py - Tests for graph relationship visualization.
"""

import json

from qa_ai.reporting.graph_visualizer import GraphVisualizer


class TestGraphVisualizer:
    def test_visualizes_graph_relationships(self, artifact_store, tmp_dir, monkeypatch):
        graphify_out = tmp_dir / "graphify-out"
        graphify_out.mkdir(parents=True, exist_ok=True)
        (graphify_out / "graph.json").write_text(
            json.dumps(
                {
                    "nodes": [
                        {"id": "n1", "label": "WorkflowEngine", "source_file": "qa_ai/orchestration/workflow_engine.py", "community": 1},
                        {"id": "n2", "label": "APIAuditAgent", "source_file": "qa_ai/audit/api_audit.py", "community": 2},
                    ],
                    "edges": [{"source": "n1", "target": "n2"}],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_dir)
        artifact_store.save_artifact("evidence_graph", {"graph": {"nodes": [], "edges": []}, "summary": {}}, agent="test")

        result = GraphVisualizer(artifact_store).run()

        assert len(result["dependency_graph"]["nodes"]) == 2
        assert len(result["dependency_graph"]["edges"]) == 1
        assert len(result["workflow_graph"]["nodes"]) >= 1
        assert artifact_store.artifact_exists("graph_visualization")
