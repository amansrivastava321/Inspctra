"""
live_benchmark_runner.py - Runtime-lab integration for live benchmark execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import uuid

from qa_ai.benchmarking.benchmark_runner import BenchmarkRunner
from qa_ai.benchmarking.detection_metrics import DetectionMetrics
from qa_ai.runtime.artifact_store import ArtifactStore
from qa_ai.runtime_lab.app_launcher import AppLauncher
from qa_ai.runtime_lab.browser_pool import BrowserPool
from qa_ai.runtime_lab.cleanup_manager import CleanupManager
from qa_ai.runtime_lab.process_manager import ProcessManager
from qa_ai.runtime_lab.runtime_monitor import RuntimeMonitor
from qa_ai.runtime_lab.service_discovery import ServiceDiscovery


class LiveBenchmarkRunner:
    """Launches sample apps, discovers live services, runs benchmark flow, and cleans up."""

    def __init__(self, artifact_store: ArtifactStore):
        self.store = artifact_store

    def run(
        self,
        sample_root: str,
        output_dir: str = "artifacts",
        dry_run: bool = True,
        headless: bool = True,
    ) -> Dict[str, Any]:
        root = Path(sample_root).expanduser().resolve()
        output_root = Path(output_dir).expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        runtime_dir = output_root / "runtime_lab" / f"live_{uuid.uuid4().hex[:8]}"
        runtime_dir.mkdir(parents=True, exist_ok=True)

        process_manager = ProcessManager(runtime_dir=runtime_dir / "processes")
        launcher = AppLauncher(process_manager)
        discovery = ServiceDiscovery()
        monitor = RuntimeMonitor(self.store, process_manager)
        browser_pool = BrowserPool(self.store)
        cleanup = CleanupManager(self.store)
        benchmark_runner = BenchmarkRunner()

        app_paths = benchmark_runner.discover_sample_apps(root)
        app_results: List[Dict[str, Any]] = []

        for index, app_path in enumerate(app_paths):
            launch = launcher.launch(
                str(app_path),
                dry_run=dry_run,
                port=8200 + index,
                timeout_seconds=60.0,
            )
            process_id = ((launch.get("process") or {}).get("process_id")) if isinstance(launch.get("process"), dict) else None
            readiness = {
                "ready": False,
                "base_url": launch.get("base_url", ""),
                "error": "dry_run" if dry_run else "not_launched",
            }
            if not dry_run and process_id and launch.get("base_url"):
                host = "127.0.0.1"
                port = int(str(launch["base_url"]).rsplit(":", 1)[-1])
                readiness = discovery.wait_for_service(host=host, port=port, timeout_seconds=10.0)

            benchmark_summary = benchmark_runner.run(
                sample_root=str(app_path),
                output_dir=str(output_root / "live_benchmarks"),
                execute=not dry_run,
                app_urls={app_path.name: readiness.get("base_url")} if readiness.get("ready") else None,
            )
            benchmark_app_result = next(
                (item for item in benchmark_summary.get("apps", []) if item.get("app_name") == app_path.name),
                {},
            )
            monitor_report: Dict[str, Any] = {}
            if not dry_run and process_id:
                monitor_report = monitor.monitor(
                    process_id=process_id,
                    app_name=app_path.name,
                    duration_seconds=0.6,
                    poll_interval=0.1,
                    expect_running=False,
                )

            # Browser session is optional and non-fatal.
            browser_session = browser_pool.create_session(headless=headless) if not dry_run else {"status": "planned"}
            if browser_session.get("session_id"):
                browser_pool.close_session(browser_session["session_id"])

            cleanup_report = cleanup.cleanup(
                process_manager=process_manager,
                browser_pool=browser_pool,
                temp_paths=[str(runtime_dir / "tmp")],
            )

            merged = {
                **benchmark_app_result,
                "launch": launch,
                "service_discovery": readiness,
                "runtime_monitor": monitor_report,
                "cleanup": cleanup_report,
                "live_mode": True,
                "dry_run": dry_run,
            }
            app_results.append(merged)

        summary = {
            "benchmark_root": str(root),
            "dry_run": dry_run,
            "apps": app_results,
            "totals": self._aggregate(app_results),
        }
        metrics = DetectionMetrics().run(summary)
        self.store.save_artifact("live_benchmark_summary", summary, agent="LiveBenchmarkRunner")
        self.store.save_artifact("live_benchmark_metrics", metrics, agent="LiveBenchmarkRunner")
        return {
            "status": "ok",
            "benchmark_root": str(root),
            "apps_benchmarked": summary["totals"]["apps_total"],
            "findings_total": summary["totals"]["findings_total"],
            "dry_run": dry_run,
            "artifacts": {
                "live_benchmark_summary": "live_benchmark_summary.json",
                "live_benchmark_metrics": "live_benchmark_metrics.json",
            },
        }

    def _aggregate(self, apps: List[Dict[str, Any]]) -> Dict[str, Any]:
        findings_total = 0
        regressions = 0
        runtime_failures = 0
        for app in apps:
            findings_total += self._safe_int(app.get("findings_count"))
            runtime_failures += self._safe_int(app.get("runtime_failures"))
            if app.get("regression_detected"):
                regressions += 1
        return {
            "apps_total": len(apps),
            "findings_total": findings_total,
            "runtime_failures_total": runtime_failures,
            "apps_with_regressions": regressions,
        }

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
