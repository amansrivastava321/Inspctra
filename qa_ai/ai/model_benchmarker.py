"""
model_benchmarker.py - Lightweight latency benchmark for local Ollama models.

Rules:
- Never runs without explicit approval (approved=True parameter).
- Dry-run safe: skips actual calls when dry_run=True.
- Uses minimal prompts to avoid wasting tokens.
- Does NOT benchmark heavy models (gemma4:e4b, qwen3.5:9b) unless --quick=False.
- Returns structured BenchmarkReport.
- No shell. No subprocess. No eval.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from qa_ai.ai.task_profiles import MAC_M4_16GB, ModelTask, get_default_task_routes

logger = logging.getLogger(__name__)

_QUICK_PROMPT = "Reply with exactly: ok"
_QUICK_TIMEOUT = 30


@dataclass
class ModelBenchmarkEntry:
    model: str
    task: str
    latency_ms: float
    status: str        # "ok" | "timeout" | "error" | "skipped" | "dry_run"
    error: Optional[str]
    recommendation: str


@dataclass
class BenchmarkReport:
    generated_at: str
    approved: bool
    dry_run: bool
    quick_mode: bool
    entries: List[ModelBenchmarkEntry]
    summary: str


def run_benchmark(
    *,
    approved: bool = False,
    dry_run: bool = True,
    quick: bool = True,
    ollama_base_url: str = "http://127.0.0.1:11434",
) -> BenchmarkReport:
    """
    Run latency benchmark for configured models.

    MUST pass approved=True to run real calls.
    dry_run=True returns stub results without calling any model.
    quick=True only tests light + medium models.
    """
    now = datetime.now(timezone.utc).isoformat()

    if not approved:
        return BenchmarkReport(
            generated_at=now,
            approved=False,
            dry_run=dry_run,
            quick_mode=quick,
            entries=[],
            summary="Benchmark requires explicit approval. Pass approved=True to proceed.",
        )

    routes = get_default_task_routes()
    profile = MAC_M4_16GB

    # Determine which models to test
    tested_models: set[str] = set()
    entries: List[ModelBenchmarkEntry] = []

    for task, route in routes.items():
        model = route.model
        if model in tested_models:
            continue
        tested_models.add(model)

        tier = profile.tier(model)

        # Skip heavy models in quick mode (they take 20+ seconds to load)
        if quick and tier == "heavy":
            entries.append(ModelBenchmarkEntry(
                model=model,
                task=task.value,
                latency_ms=0.0,
                status="skipped",
                error=None,
                recommendation=f"Skipped in quick mode (heavy model). Run without --quick to test.",
            ))
            continue

        # Skip embeddings in quick mode (different API)
        if quick and task == ModelTask.EMBEDDINGS:
            entries.append(ModelBenchmarkEntry(
                model=model,
                task=task.value,
                latency_ms=0.0,
                status="skipped",
                error=None,
                recommendation="Embedding benchmark skipped in quick mode.",
            ))
            continue

        if dry_run:
            entries.append(ModelBenchmarkEntry(
                model=model,
                task=task.value,
                latency_ms=0.0,
                status="dry_run",
                error=None,
                recommendation="Dry run — no actual call made.",
            ))
            continue

        # Real call
        start = time.time()
        try:
            payload = json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": _QUICK_PROMPT}],
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 8},
            }).encode()
            req = urllib.request.Request(
                f"{ollama_base_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=_QUICK_TIMEOUT) as resp:
                resp.read()

            latency_ms = (time.time() - start) * 1000
            rec = _recommend(latency_ms, tier)
            entries.append(ModelBenchmarkEntry(
                model=model,
                task=task.value,
                latency_ms=round(latency_ms, 1),
                status="ok",
                error=None,
                recommendation=rec,
            ))

        except urllib.error.URLError as exc:
            entries.append(ModelBenchmarkEntry(
                model=model,
                task=task.value,
                latency_ms=(time.time() - start) * 1000,
                status="error",
                error=f"Connection failed: {exc}",
                recommendation=f"Ollama not reachable. Start with: ollama serve",
            ))
        except Exception as exc:
            entries.append(ModelBenchmarkEntry(
                model=model,
                task=task.value,
                latency_ms=(time.time() - start) * 1000,
                status="error",
                error=str(exc),
                recommendation=f"Check if model is installed: ollama pull {model}",
            ))

    ok_count = sum(1 for e in entries if e.status == "ok")
    total_tested = sum(1 for e in entries if e.status not in ("skipped", "dry_run"))
    summary = (
        f"Benchmark complete: {ok_count}/{total_tested} models responded. "
        f"Quick mode={quick}. Dry run={dry_run}."
    ) if approved else "Not approved."

    return BenchmarkReport(
        generated_at=now,
        approved=approved,
        dry_run=dry_run,
        quick_mode=quick,
        entries=entries,
        summary=summary,
    )


def _recommend(latency_ms: float, tier: str) -> str:
    if tier == "light":
        if latency_ms < 2000:
            return "Fast. Good for step narration."
        return f"Slow ({latency_ms:.0f}ms). May impact live narration."
    if tier == "medium":
        if latency_ms < 10000:
            return f"Acceptable ({latency_ms:.0f}ms) for background reasoning."
        return f"Slow ({latency_ms:.0f}ms). Consider lighter fallback."
    return f"Latency {latency_ms:.0f}ms (heavy model — expected to be slow)."
