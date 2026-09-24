"""
task_router.py - Task-aware local-first model router for Inspectra.

Wraps the Ollama client with task profiles and resource management.
Routes each AI task to the correct local model.
Applies prompt safety before every call.
Falls back gracefully: primary model → fallback → capability_gap.
Never calls cloud unless explicitly enabled and approved.
No shell. No subprocess. No eval.
"""
from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from qa_ai.ai.prompt_safety import make_safe, redact_for_logging
from qa_ai.ai.resource_manager import ResourceManager, get_resource_manager
from qa_ai.ai.task_profiles import (
    ModelTask,
    ResourceProfile,
    TaskRoute,
    get_default_task_routes,
)

logger = logging.getLogger(__name__)

# ── Result ─────────────────────────────────────────────────────────────────────

@dataclass
class ModelCallResult:
    status: str          # "ok" | "fallback" | "capability_gap" | "error"
    provider_id: str
    model: str
    task: str
    output_text: str
    output_json: Optional[Dict[str, Any]] = None
    embeddings: Optional[List[float]] = None
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    error: Optional[str] = None
    fallback_used: bool = False
    fallback_from: Optional[str] = None
    redactions_applied: List[str] = field(default_factory=list)
    capability_gap: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status in ("ok", "fallback")


def _capability_gap(task: ModelTask, reason: str) -> ModelCallResult:
    return ModelCallResult(
        status="capability_gap",
        provider_id="none",
        model="none",
        task=task.value,
        output_text="",
        capability_gap=reason,
        error=reason,
    )


# ── TaskRouter ─────────────────────────────────────────────────────────────────

class TaskRouter:
    """
    Main entry point for all AI task calls in Inspectra.

    Usage:
        router = TaskRouter()
        result = router.call(ModelTask.AI_ORACLE, prompt="Did this action succeed?")

    Resource management:
        Sequential calls enforced (max 1 model at a time on 16 GB Mac).
        Heavy models defer if another call is active.

    Cloud policy:
        Cloud disabled by default.
        Set allow_cloud=True + provide api_key_env to enable.
        Cloud calls require explicit approval per session.
    """

    def __init__(
        self,
        routes: Optional[Dict[ModelTask, TaskRoute]] = None,
        resource_manager: Optional[ResourceManager] = None,
        ollama_base_url: str = "http://127.0.0.1:11434",
        allow_cloud: bool = False,
        private_mode: bool = True,
        persist_prompts: bool = False,
    ) -> None:
        self._routes = routes or get_default_task_routes()
        self._rm = resource_manager or get_resource_manager()
        self._ollama_base_url = ollama_base_url
        self._allow_cloud = allow_cloud
        self._private_mode = private_mode
        self._persist_prompts = persist_prompts

    # ── Public API ─────────────────────────────────────────────────────────────

    def call(
        self,
        task: ModelTask,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        images: Optional[List[str]] = None,   # list of file paths
        json_mode: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ModelCallResult:
        """
        Route a prompt to the correct model for the given task.

        Returns ModelCallResult. Never raises — errors are captured in result.
        """
        route = self._routes.get(task)
        if not route:
            return _capability_gap(task, f"No route configured for task: {task.value}")

        # Apply prompt safety
        safety = make_safe(
            prompt,
            private_mode=self._private_mode,
            cloud_target=False,  # local only by default
        )
        if safety.blocked_reason:
            return _capability_gap(task, safety.blocked_reason)

        safe_prompt = safety.safe_prompt
        redactions = safety.redactions_applied

        # Try primary model, then fallbacks
        models_to_try = [route.model] + list(route.fallback_models)
        fallback_used = False
        fallback_from: Optional[str] = None

        for idx, model in enumerate(models_to_try):
            if idx > 0:
                fallback_used = True
                fallback_from = models_to_try[idx - 1]
                logger.info(
                    "TaskRouter: fallback from %s to %s for task %s",
                    fallback_from, model, task.value,
                )

            # Resource check
            if not self._rm.can_run(model):
                lighter = self._rm.route_to_lighter_model_if_needed(task)
                if lighter and lighter not in models_to_try[idx:]:
                    models_to_try.insert(idx, lighter)
                    continue

            # Acquire slot
            if not self._rm.acquire_model_slot(task, model):
                logger.warning(
                    "TaskRouter: could not acquire slot for %s/%s — slot busy",
                    task.value, model,
                )
                continue

            start = time.time()
            try:
                result = self._call_ollama(
                    task=task,
                    model=model,
                    prompt=safe_prompt,
                    system_prompt=system_prompt,
                    images=images,
                    json_mode=json_mode,
                    route=route,
                )
                latency_ms = (time.time() - start) * 1000

                if result.ok:
                    result.latency_ms = latency_ms
                    result.fallback_used = fallback_used
                    result.fallback_from = fallback_from
                    result.redactions_applied = redactions
                    return result

            except Exception as exc:
                logger.warning(
                    "TaskRouter: model call failed for %s/%s: %s",
                    task.value, model, exc,
                )
            finally:
                self._rm.release_model_slot(task, model)

        # All models exhausted
        tried = ", ".join(models_to_try)
        return _capability_gap(
            task,
            f"All models failed or unavailable for task {task.value}. Tried: {tried}",
        )

    def embed(self, texts: List[str]) -> ModelCallResult:
        """
        Generate embeddings using bge-m3:latest.

        Returns ModelCallResult with embeddings list.
        """
        route = self._routes.get(ModelTask.EMBEDDINGS)
        if not route:
            return _capability_gap(ModelTask.EMBEDDINGS, "No embeddings route configured.")

        if not texts:
            return ModelCallResult(
                status="ok",
                provider_id="ollama",
                model=route.model,
                task=ModelTask.EMBEDDINGS.value,
                output_text="",
                embeddings=[],
            )

        model = route.model
        if not self._rm.acquire_model_slot(ModelTask.EMBEDDINGS, model):
            return _capability_gap(ModelTask.EMBEDDINGS, "Resource slot busy.")

        start = time.time()
        try:
            import urllib.request
            all_embeddings: List[List[float]] = []
            for text in texts:
                payload = json.dumps({"model": model, "input": text}).encode()
                req = urllib.request.Request(
                    f"{self._ollama_base_url}/api/embed",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=route.timeout_seconds) as resp:
                    data = json.loads(resp.read())
                    if "embeddings" in data:
                        all_embeddings.append(data["embeddings"][0])
                    elif "embedding" in data:
                        all_embeddings.append(data["embedding"])

            latency_ms = (time.time() - start) * 1000
            # Return first embedding in flat list; caller can iterate for batch
            flat = all_embeddings[0] if all_embeddings else []
            return ModelCallResult(
                status="ok",
                provider_id="ollama",
                model=model,
                task=ModelTask.EMBEDDINGS.value,
                output_text="",
                embeddings=flat,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            return ModelCallResult(
                status="error",
                provider_id="ollama",
                model=model,
                task=ModelTask.EMBEDDINGS.value,
                output_text="",
                error=str(exc),
                latency_ms=(time.time() - start) * 1000,
            )
        finally:
            self._rm.release_model_slot(ModelTask.EMBEDDINGS, model)

    # ── Private ────────────────────────────────────────────────────────────────

    def _call_ollama(
        self,
        task: ModelTask,
        model: str,
        prompt: str,
        system_prompt: Optional[str],
        images: Optional[List[str]],
        json_mode: bool,
        route: TaskRoute,
    ) -> ModelCallResult:
        """
        Call Ollama /api/chat or /api/generate.
        Returns ModelCallResult (status may be "error" on failure).
        """
        import urllib.request

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if images:
            # Vision call — encode images as base64
            encoded_images = []
            for img_path in images:
                p = Path(img_path)
                if p.exists():
                    with open(p, "rb") as f:
                        encoded_images.append(base64.b64encode(f.read()).decode())
                else:
                    logger.warning("TaskRouter: vision image not found: %s", img_path)

            if encoded_images:
                messages.append({
                    "role": "user",
                    "content": prompt,
                    "images": encoded_images,
                })
            else:
                messages.append({"role": "user", "content": prompt})
        else:
            messages.append({"role": "user", "content": prompt})

        call_payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": route.temperature,
                "num_predict": route.max_tokens or -1,
            },
        }
        if json_mode:
            call_payload["format"] = "json"

        payload_bytes = json.dumps(call_payload).encode()
        req = urllib.request.Request(
            f"{self._ollama_base_url}/api/chat",
            data=payload_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=route.timeout_seconds) as resp:
            raw = json.loads(resp.read())

        content = raw.get("message", {}).get("content", "")
        tokens_in = raw.get("prompt_eval_count", 0) or 0
        tokens_out = raw.get("eval_count", 0) or 0

        output_json: Optional[Dict[str, Any]] = None
        if json_mode and content:
            try:
                output_json = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                # Try extracting JSON block from text
                import re
                m = re.search(r"\{.*\}", content, re.DOTALL)
                if m:
                    try:
                        output_json = json.loads(m.group())
                    except (json.JSONDecodeError, ValueError):
                        pass

        return ModelCallResult(
            status="ok",
            provider_id="ollama",
            model=model,
            task=task.value,
            output_text=content,
            output_json=output_json,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )


# ── Process-level singleton ────────────────────────────────────────────────────

_singleton: Optional[TaskRouter] = None
import threading
_singleton_lock = threading.Lock()


def get_task_router(
    ollama_base_url: str = "http://127.0.0.1:11434",
    allow_cloud: bool = False,
    private_mode: bool = True,
) -> TaskRouter:
    """Return the process-wide TaskRouter singleton."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = TaskRouter(
                    ollama_base_url=ollama_base_url,
                    allow_cloud=allow_cloud,
                    private_mode=private_mode,
                )
    return _singleton
