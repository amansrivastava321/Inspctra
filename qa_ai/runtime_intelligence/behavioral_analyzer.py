"""
behavioral_analyzer.py - Analyzes execution traces for behavioral anomalies.
Detects retry loops, repeated failures, navigation loops, excessive API failures,
inconsistent workflow states, timeout clusters, and flaky behavior.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
import logging
import time
from collections import Counter

from qa_ai.runtime.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class BehavioralAnalyzer:
    """
    Analyzes execution traces to detect behavioral anomalies.

    Detects:
    - Retry loops (same action repeated N+ times)
    - Repeated failures (same test failing consistently)
    - Navigation loops (URL visited N+ times)
    - Excessive API failures (failure rate above threshold)
    - Inconsistent workflow states
    - Timeout clusters (multiple timeouts in sequence)
    - Flaky behavior (test passes sometimes, fails sometimes)
    """

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        execution_results: Optional[Dict[str, Any]] = None,
        execution_traces: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run behavioral analysis on execution data."""
        start_time = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        if execution_results is None:
            execution_results = self.store.load_artifact("execution_results") or {}

        if execution_traces is None:
            execution_traces = self.store.load_artifact("execution_traces") or []

        anomalies: List[Dict[str, Any]] = []

        # Analyze execution results
        anomalies.extend(self._detect_repeated_failures(execution_results))
        anomalies.extend(self._detect_flaky_behavior(execution_results))
        anomalies.extend(self._detect_excessive_failures(execution_results))

        # Analyze execution traces
        anomalies.extend(self._detect_retry_loops(execution_traces))
        anomalies.extend(self._detect_navigation_loops(execution_traces))
        anomalies.extend(self._detect_timeout_clusters(execution_traces))
        anomalies.extend(self._detect_inconsistent_states(execution_traces))

        duration = time.time() - start_time

        result = {
            "metadata": {
                "analysis_type": "behavioral_analysis",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": duration,
                "generated_by": "BehavioralAnalyzer",
                "total_anomalies": len(anomalies),
            },
            "anomalies": anomalies,
            "summary": self._build_summary(anomalies),
        }

        self.store.save_artifact("behavioral_analysis", result, agent="BehavioralAnalyzer")
        logger.info(f"Behavioral analysis complete: {len(anomalies)} anomalies detected")
        return result

    def _detect_repeated_failures(self, execution_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect tests that fail consistently."""
        anomalies: List[Dict[str, Any]] = []
        suites = execution_results.get("suites", [])

        failure_counts: Counter = Counter()
        test_titles: Dict[str, str] = {}

        for suite in suites:
            for test in suite.get("tests", []):
                tid = test.get("test_id", "")
                outcome = test.get("outcome", "")
                test_titles[tid] = test.get("test_title", tid)
                if outcome in ("failed", "error"):
                    failure_counts[tid] += 1

        for tid, count in failure_counts.items():
            if count >= 2:
                anomalies.append({
                    "type": "repeated_failure",
                    "severity": "high",
                    "test_id": tid,
                    "test_title": test_titles.get(tid, tid),
                    "failure_count": count,
                    "description": f"Test '{test_titles.get(tid, tid)}' failed {count} times",
                })

        return anomalies

    def _detect_flaky_behavior(self, execution_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect tests that sometimes pass and sometimes fail."""
        anomalies: List[Dict[str, Any]] = []
        suites = execution_results.get("suites", [])

        test_outcomes: Dict[str, List[str]] = {}

        for suite in suites:
            for test in suite.get("tests", []):
                tid = test.get("test_id", "")
                outcome = test.get("outcome", "")
                if tid not in test_outcomes:
                    test_outcomes[tid] = []
                test_outcomes[tid].append(outcome)

        for tid, outcomes in test_outcomes.items():
            if len(outcomes) >= 2:
                unique_outcomes = set(outcomes)
                if "passed" in unique_outcomes and ("failed" in unique_outcomes or "error" in unique_outcomes):
                    anomalies.append({
                        "type": "flaky_behavior",
                        "severity": "medium",
                        "test_id": tid,
                        "outcomes": outcomes,
                        "description": f"Test '{tid}' shows flaky behavior: {list(unique_outcomes)}",
                    })

        return anomalies

    def _detect_excessive_failures(self, execution_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect suites with excessive failure rates."""
        anomalies: List[Dict[str, Any]] = []
        suites = execution_results.get("suites", [])

        for suite in suites:
            total = suite.get("total", 0)
            failed = suite.get("failed", 0)
            errors = suite.get("errors", 0)

            if total > 0:
                failure_rate = (failed + errors) / total
                if failure_rate > 0.5:
                    anomalies.append({
                        "type": "excessive_failures",
                        "severity": "high",
                        "suite_name": suite.get("suite_name", ""),
                        "failure_rate": round(failure_rate, 2),
                        "total": total,
                        "failed": failed,
                        "errors": errors,
                        "description": f"Suite '{suite.get('suite_name', '')}' has {failure_rate:.0%} failure rate",
                    })

        return anomalies

    def _detect_retry_loops(self, traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect retry loops in execution traces."""
        anomalies: List[Dict[str, Any]] = []

        action_sequences: List[str] = []
        for trace in traces:
            action = trace.get("action", trace.get("type", ""))
            action_sequences.append(action)

        # Look for repeated consecutive actions
        consecutive_count = 1
        for i in range(1, len(action_sequences)):
            if action_sequences[i] == action_sequences[i - 1] and action_sequences[i]:
                consecutive_count += 1
            else:
                if consecutive_count >= 3:
                    anomalies.append({
                        "type": "retry_loop",
                        "severity": "medium",
                        "action": action_sequences[i - 1],
                        "repeat_count": consecutive_count,
                        "description": f"Action '{action_sequences[i - 1]}' repeated {consecutive_count} times consecutively",
                    })
                consecutive_count = 1

        # Check final sequence
        if consecutive_count >= 3 and action_sequences:
            anomalies.append({
                "type": "retry_loop",
                "severity": "medium",
                "action": action_sequences[-1],
                "repeat_count": consecutive_count,
                "description": f"Action '{action_sequences[-1]}' repeated {consecutive_count} times consecutively",
            })

        return anomalies

    def _detect_navigation_loops(self, traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect navigation loops (same URL visited multiple times)."""
        anomalies: List[Dict[str, Any]] = []

        url_visits: Counter = Counter()
        for trace in traces:
            url = trace.get("url", trace.get("destination", ""))
            if url:
                url_visits[url] += 1

        for url, count in url_visits.items():
            if count >= 3:
                anomalies.append({
                    "type": "navigation_loop",
                    "severity": "medium",
                    "url": url,
                    "visit_count": count,
                    "description": f"URL '{url}' visited {count} times - possible navigation loop",
                })

        return anomalies

    def _detect_timeout_clusters(self, traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect clusters of timeouts."""
        anomalies: List[Dict[str, Any]] = []

        timeout_indices: List[int] = []
        for i, trace in enumerate(traces):
            if trace.get("type") == "timeout" or trace.get("error", "").lower().find("timeout") >= 0:
                timeout_indices.append(i)

        # Check for consecutive timeouts
        if len(timeout_indices) >= 2:
            consecutive = 1
            for i in range(1, len(timeout_indices)):
                if timeout_indices[i] - timeout_indices[i - 1] <= 2:
                    consecutive += 1
                else:
                    if consecutive >= 2:
                        anomalies.append({
                            "type": "timeout_cluster",
                            "severity": "high",
                            "timeout_count": consecutive,
                            "description": f"Cluster of {consecutive} timeouts detected",
                        })
                    consecutive = 1

            if consecutive >= 2:
                anomalies.append({
                    "type": "timeout_cluster",
                    "severity": "high",
                    "timeout_count": consecutive,
                    "description": f"Cluster of {consecutive} timeouts detected",
                })

        return anomalies

    def _detect_inconsistent_states(self, traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect inconsistent workflow states."""
        anomalies: List[Dict[str, Any]] = []

        states: List[str] = []
        for trace in traces:
            state = trace.get("state", trace.get("workflow_state", ""))
            if state:
                states.append(state)

        # Check for state going backwards
        state_order = {"init": 0, "started": 1, "running": 2, "completed": 3, "failed": -1}
        for i in range(1, len(states)):
            prev = state_order.get(states[i - 1], -2)
            curr = state_order.get(states[i], -2)
            if prev > 0 and curr > 0 and curr < prev:
                anomalies.append({
                    "type": "inconsistent_state",
                    "severity": "high",
                    "from_state": states[i - 1],
                    "to_state": states[i],
                    "description": f"Workflow went from '{states[i - 1]}' back to '{states[i]}'",
                })

        return anomalies

    def _build_summary(self, anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build a summary of detected anomalies."""
        by_type: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}

        for a in anomalies:
            t = a.get("type", "unknown")
            s = a.get("severity", "unknown")
            by_type[t] = by_type.get(t, 0) + 1
            by_severity[s] = by_severity.get(s, 0) + 1

        return {
            "total_anomalies": len(anomalies),
            "by_type": by_type,
            "by_severity": by_severity,
            "has_critical": by_severity.get("critical", 0) > 0,
            "has_high": by_severity.get("high", 0) > 0,
        }
