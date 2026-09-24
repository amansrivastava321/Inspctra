"""
llm_router.py - Production-grade multi-model LLM router.
Features: health checks, fallback chains, circuit breakers,
retry logic, token management, embedding cache, async support.
"""

from __future__ import annotations

import asyncio
import json
import time
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache

from qa_ai.ai.ollama_client import OllamaClient as OllamaClient
from qa_ai.ai.model_profiles import RoutingComponent
from qa_ai.ai.model_router import ModelRouter
from qa_ai.config.settings import get_settings as _get_settings

logger = logging.getLogger(__name__)


def _default_timeout() -> int:
    return _get_settings().llm_timeout_seconds


def _long_timeout() -> int:
    return _get_settings().llm_long_timeout_seconds


# ─── Data Models ───────────────────────────────────────

class ModelCapability(Enum):
    FAST_CLASSIFICATION = "fast_classification"
    QA_REASONING = "qa_reasoning"
    CODE_ANALYSIS = "code_analysis"
    DEEP_REASONING = "deep_reasoning"
    VISION = "vision"
    REPORT_WRITING = "report_writing"
    EMBEDDING = "embedding"
    BACKUP = "backup"


@dataclass
class ModelConfig:
    name: str
    capability: ModelCapability
    max_context_tokens: int = 4096      # Used for prompt truncation
    max_output_tokens: int = 2048       # Passed to Ollama as num_predict
    temperature: float = 0.2
    timeout: int = 120
    max_retries: int = 3
    retry_delay: float = 1.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_cooldown: int = 60  # seconds


@dataclass
class ModelHealth:
    is_available: bool = True           # Start optimistic
    last_checked: float = 0.0
    failure_count: int = 0
    circuit_open: bool = False
    circuit_opened_at: float = 0.0
    last_failure_at: Optional[float] = None
    next_retry_at: Optional[float] = None
    total_calls: int = 0
    total_failures: int = 0
    avg_latency_ms: float = 0.0

    @property
    def current_state(self) -> str:
        if getattr(self, "_half_open", False):
            return "half_open"
        if not self.circuit_open:
            return "closed"
        return "open"


@dataclass
class CallResult:
    success: bool
    content: str = ""
    model_used: str = ""
    latency_ms: float = 0.0
    tokens_used: int = 0
    retries: int = 0
    error: Optional[str] = None


# ─── Prompt Templates ──────────────────────────────────

PROMPT_TEMPLATES = {
    "version": "1.0.0",
    "templates": {
        "classify_task": {
            "system": "You are a fast classification model for an autonomous QA platform. Classify the input into one of: test_plan_generation, code_analysis, failure_analysis, report_writing, or general_qa.",
            "temperature": 0.1,
            "max_output_tokens": 200,
        },
        "test_plan_generation": {
            "system": "You are a senior QA architect. Generate precise, structured, executable QA plans. Output valid JSON only.",
            "temperature": 0.2,
            "max_output_tokens": 4096,
        },
        "code_analysis": {
            "system": "You are a senior software engineer and code auditor. Identify root causes, security vulnerabilities, and provide practical fixes with code examples.",
            "temperature": 0.1,
            "max_output_tokens": 8192,
        },
        "failure_analysis": {
            "system": "You are a deep debugging and root-cause analysis agent. Analyze the failure, trace it to source, and explain the exact fix needed.",
            "temperature": 0.1,
            "max_output_tokens": 8192,
        },
        "report_writing": {
            "system": "You are a QA report writer. Write clear, actionable, developer-ready audit reports with reproduction steps, severity ratings, and fix suggestions.",
            "temperature": 0.2,
            "max_output_tokens": 16384,
        },
        "embedding": {
            "system": "",
            "temperature": 0.0,
            "max_output_tokens": 0,
        },
    }
}


# ─── Main Router ───────────────────────────────────────

class LLMRouter:
    """
    Production-grade LLM router with:
    - Multi-model routing with capability matching
    - Automatic fallback chains
    - Circuit breakers
    - Retry with exponential backoff
    - Token management
    - Embedding caching
    - Async support with concurrency limits
    - Full observability
    """

    def __init__(
        self,
        client: Optional[OllamaClient] = None,
        max_concurrent: int = 3,
        cache_embeddings: bool = True,
    ):
        self.client = client or OllamaClient()
        self.specialist_router = ModelRouter(ollama_client=self.client)
        self.max_concurrent = max_concurrent
        self.cache_embeddings = cache_embeddings
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Model registry: capability → [primary, fallback1, fallback2]
        self.model_registry: Dict[ModelCapability, List[ModelConfig]] = {
            ModelCapability.FAST_CLASSIFICATION: [
                ModelConfig(
                    "phi4-mini:latest",
                    ModelCapability.FAST_CLASSIFICATION,
                    max_context_tokens=4096,
                    max_output_tokens=256,
                    timeout=60,
                ),
                ModelConfig(
                    "dolphin-mistral:7b",
                    ModelCapability.FAST_CLASSIFICATION,
                    max_context_tokens=4096,
                    max_output_tokens=256,
                    timeout=60,
                ),
            ],
            ModelCapability.QA_REASONING: [
                ModelConfig(
                    "qwen3.5:9b",
                    ModelCapability.QA_REASONING,
                    max_context_tokens=8192,
                    max_output_tokens=4096,
                    temperature=0.2,
                    timeout=_default_timeout(),
                ),
                ModelConfig(
                    "deepseek-r1:7b",
                    ModelCapability.QA_REASONING,
                    max_context_tokens=8192,
                    max_output_tokens=4096,
                    temperature=0.2,
                    timeout=_default_timeout(),
                ),
                ModelConfig(
                    "dolphin-mistral:7b",
                    ModelCapability.QA_REASONING,
                    max_context_tokens=4096,
                    max_output_tokens=2048,
                    temperature=0.2,
                    timeout=_default_timeout(),
                ),
            ],
            ModelCapability.CODE_ANALYSIS: [
                ModelConfig(
                    "dolphincoder:7b",
                    ModelCapability.CODE_ANALYSIS,
                    max_context_tokens=8192,
                    max_output_tokens=4096,
                    temperature=0.1,
                    timeout=_default_timeout(),
                ),
                ModelConfig(
                    "deepseek-r1:7b",
                    ModelCapability.CODE_ANALYSIS,
                    max_context_tokens=8192,
                    max_output_tokens=4096,
                    temperature=0.1,
                    timeout=_default_timeout(),
                ),
                ModelConfig(
                    "qwen3.5:9b",
                    ModelCapability.CODE_ANALYSIS,
                    max_context_tokens=8192,
                    max_output_tokens=4096,
                    temperature=0.1,
                    timeout=_default_timeout(),
                ),
            ],
            ModelCapability.DEEP_REASONING: [
                ModelConfig(
                    "deepseek-r1:7b",
                    ModelCapability.DEEP_REASONING,
                    max_context_tokens=16384,
                    max_output_tokens=8192,
                    temperature=0.1,
                    timeout=_long_timeout(),
                ),
                ModelConfig(
                    "qwen3.5:9b",
                    ModelCapability.DEEP_REASONING,
                    max_context_tokens=8192,
                    max_output_tokens=4096,
                    temperature=0.1,
                    timeout=_default_timeout(),
                ),
                ModelConfig(
                    "dolphin-mistral:7b",
                    ModelCapability.DEEP_REASONING,
                    max_context_tokens=4096,
                    max_output_tokens=2048,
                    temperature=0.1,
                    timeout=_default_timeout(),
                ),
            ],
            ModelCapability.VISION: [
                ModelConfig(
                    "qwen2.5vl:7b",
                    ModelCapability.VISION,
                    max_context_tokens=4096,
                    max_output_tokens=2048,
                    timeout=_default_timeout(),
                ),
                ModelConfig(
                    "dolphin-mistral:7b",
                    ModelCapability.VISION,
                    max_context_tokens=4096,
                    max_output_tokens=1024,
                    timeout=_default_timeout(),
                ),
            ],
            ModelCapability.REPORT_WRITING: [
                ModelConfig(
                    "gemma4:e4b",
                    ModelCapability.REPORT_WRITING,
                    max_context_tokens=16384,
                    max_output_tokens=8192,
                    temperature=0.2,
                    timeout=_default_timeout(),
                ),
                ModelConfig(
                    "qwen3.5:9b",
                    ModelCapability.REPORT_WRITING,
                    max_context_tokens=8192,
                    max_output_tokens=4096,
                    temperature=0.2,
                    timeout=_default_timeout(),
                ),
                ModelConfig(
                    "dolphin-mistral:7b",
                    ModelCapability.REPORT_WRITING,
                    max_context_tokens=4096,
                    max_output_tokens=2048,
                    temperature=0.2,
                    timeout=_default_timeout(),
                ),
            ],
            ModelCapability.EMBEDDING: [
                ModelConfig(
                    "bge-m3:latest",
                    ModelCapability.EMBEDDING,
                    max_context_tokens=8192,
                    max_output_tokens=0,
                    temperature=0.0,
                    timeout=_default_timeout(),
                ),
            ],
            ModelCapability.BACKUP: [
                ModelConfig(
                    "dolphin-mistral:7b",
                    ModelCapability.BACKUP,
                    max_context_tokens=4096,
                    max_output_tokens=2048,
                    timeout=_default_timeout(),
                ),
                ModelConfig(
                    "phi4-mini:latest",
                    ModelCapability.BACKUP,
                    max_context_tokens=4096,
                    max_output_tokens=1024,
                    timeout=_default_timeout(),
                ),
            ],
        }

        # Health tracking
        self.health: Dict[str, ModelHealth] = {}
        self._init_health()

    def _init_health(self):
        """Initialize health tracking for all configured models."""
        for configs in self.model_registry.values():
            for config in configs:
                if config.name not in self.health:
                    self.health[config.name] = ModelHealth()

    # ─── Public API ────────────────────────────────────

    def classify(self, prompt: str) -> str:
        """Fast classification with minimal output."""
        return self._call_with_fallback(
            capability=ModelCapability.FAST_CLASSIFICATION,
            prompt=prompt,
            system=PROMPT_TEMPLATES["templates"]["classify_task"]["system"],
            temperature=0.1,
            max_output_tokens=200,
        )

    def generate_test_plan(self, prompt: str) -> str:
        """Generate structured QA test plan."""
        result = self.specialist_router.route(
            component=RoutingComponent.MASTER_ORCHESTRATION,
            prompt=prompt,
            context={},
            require_json=True,
            deterministic_fallback=lambda: self._call_with_fallback(
                capability=ModelCapability.QA_REASONING,
                prompt=prompt,
                system=PROMPT_TEMPLATES["templates"]["test_plan_generation"]["system"],
                temperature=0.2,
                max_output_tokens=4096,
                require_json=True,
            ),
        )
        if result.success:
            return result.content
        raise RuntimeError(result.error_type or result.fallback_reason or "generate_test_plan failed")

    def analyze_code(self, prompt: str) -> str:
        """Analyze code for bugs, security, quality issues."""
        result = self.specialist_router.route(
            component=RoutingComponent.STRUCTURED_REASONING,
            prompt=prompt,
            context={},
            require_json=False,
            deterministic_fallback=lambda: self._call_with_fallback(
                capability=ModelCapability.CODE_ANALYSIS,
                prompt=prompt,
                system=PROMPT_TEMPLATES["templates"]["code_analysis"]["system"],
                temperature=0.1,
                max_output_tokens=8192,
            ),
        )
        if result.success:
            return result.content
        raise RuntimeError(result.error_type or result.fallback_reason or "analyze_code failed")

    def deep_analyze_failure(self, prompt: str) -> str:
        """Deep root-cause analysis of test failures."""
        result = self.specialist_router.route(
            component=RoutingComponent.HUGE_REPO_REASONING,
            prompt=prompt,
            context={},
            require_json=False,
            deterministic_fallback=lambda: self._call_with_fallback(
                capability=ModelCapability.DEEP_REASONING,
                prompt=prompt,
                system=PROMPT_TEMPLATES["templates"]["failure_analysis"]["system"],
                temperature=0.1,
                max_output_tokens=8192,
            ),
        )
        if result.success:
            return result.content
        raise RuntimeError(result.error_type or result.fallback_reason or "deep_analyze_failure failed")

    def write_report(self, prompt: str) -> str:
        """Generate developer-ready QA audit report."""
        result = self.specialist_router.route(
            component=RoutingComponent.REPORT_SYNTHESIS,
            prompt=prompt,
            context={},
            require_json=False,
            deterministic_fallback=lambda: self._call_with_fallback(
                capability=ModelCapability.REPORT_WRITING,
                prompt=prompt,
                system=PROMPT_TEMPLATES["templates"]["report_writing"]["system"],
                temperature=0.2,
                max_output_tokens=16384,
            ),
        )
        if result.success:
            return result.content
        raise RuntimeError(result.error_type or result.fallback_reason or "write_report failed")

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding with caching."""
        if self.cache_embeddings:
            return list(self._embed_cached(text))
        return self.specialist_router.route_embedding([text])[0]

    # ─── Core Call Logic ───────────────────────────────

    def _call_with_fallback(
        self,
        capability: ModelCapability,
        prompt: str,
        system: str,
        temperature: float = 0.2,
        max_output_tokens: int = 4096,
        require_json: bool = False,
    ) -> str:
        """Try models in order with fallback and circuit breaker."""

        models = self.model_registry.get(capability, [])
        if not models:
            raise ValueError(f"No models configured for capability: {capability.value}")

        last_error = None
        errors = []

        for config in models:
            # Check circuit breaker
            if self._is_circuit_open(config.name):
                msg = f"Circuit breaker open for {config.name}, skipping"
                logger.warning(msg)
                errors.append(msg)
                continue

            # Check health
            if not self._is_healthy(config.name):
                msg = f"Model {config.name} marked unhealthy, skipping"
                logger.warning(msg)
                errors.append(msg)
                continue

            # Try with retries
            result = self._call_with_retry(
                config=config,
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                require_json=require_json,
            )

            if result.success:
                # Record success
                self._record_success(config.name, result.latency_ms)
                logger.info(
                    f"✓ {config.name} succeeded in {result.latency_ms:.0f}ms "
                    f"(retries: {result.retries})"
                )
                return result.content
            else:
                # Record failure
                self._record_failure(config.name)
                last_error = result.error
                logger.warning(
                    f"✗ {config.name} failed: {result.error[:100] if result.error else 'unknown'} "
                    f"(retries: {result.retries}), trying next fallback..."
                )
                errors.append(f"{config.name}: {result.error}")

        # All models failed
        error_summary = "; ".join(errors[-3:])  # Last 3 errors
        raise RuntimeError(
            f"All models failed for capability '{capability.value}'. "
            f"Last errors: {error_summary}"
        )

    def _call_with_retry(
        self,
        config: ModelConfig,
        prompt: str,
        system: str,
        temperature: float,
        max_output_tokens: int,
        require_json: bool = False,
    ) -> CallResult:
        """Call a single model with retry logic."""

        last_error = None

        for attempt in range(config.max_retries):
            start_time = time.time()

            try:
                # Truncate prompt if needed
                safe_prompt = self._truncate_prompt(prompt, config.max_context_tokens)

                # Cooler temperature on retries for more deterministic output
                adjusted_temp = temperature * (0.8 ** attempt)

                # Make the API call
                response = self.client.chat(
                    model=config.name,
                    prompt=safe_prompt,
                    system=system,
                    temperature=adjusted_temp,
                )

                latency = (time.time() - start_time) * 1000

                # Validate JSON if required
                if require_json:
                    parsed = self._extract_json(response)
                    if parsed is None:
                        if attempt < config.max_retries - 1:
                            logger.warning(
                                f"Invalid JSON from {config.name}, "
                                f"retrying with lower temperature..."
                            )
                            last_error = "Invalid JSON response"
                            continue
                        else:
                            return CallResult(
                                success=False,
                                error="Failed to get valid JSON after all retries",
                                model_used=config.name,
                                latency_ms=latency,
                                retries=attempt + 1,
                            )
                    response = json.dumps(parsed)

                return CallResult(
                    success=True,
                    content=response,
                    model_used=config.name,
                    latency_ms=latency,
                    retries=attempt + 1,
                )

            except Exception as e:
                latency = (time.time() - start_time) * 1000
                last_error = str(e)
                logger.error(
                    f"Call to {config.name} failed "
                    f"(attempt {attempt+1}/{config.max_retries}): {e}"
                )

                if attempt < config.max_retries - 1:
                    delay = config.retry_delay * (2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                    logger.info(f"Retrying {config.name} in {delay:.1f}s...")
                    time.sleep(delay)
                    continue

                return CallResult(
                    success=False,
                    error=str(e),
                    model_used=config.name,
                    latency_ms=latency,
                    retries=attempt + 1,
                )

        return CallResult(
            success=False,
            error=last_error or "Max retries exceeded",
            model_used=config.name,
            retries=config.max_retries,
        )

    # ─── Health Management ─────────────────────────────

    def _is_circuit_open(self, model_name: str) -> bool:
        """Check if circuit breaker is open for this model."""
        health = self.health.get(model_name)
        if not health or not health.circuit_open:
            return False

        # Check if cooldown has elapsed
        config = self._get_config(model_name)
        if not config:
            return True  # Unknown model, stay safe

        cooldown_elapsed = (
            time.time() - health.circuit_opened_at
        ) > config.circuit_breaker_cooldown

        if cooldown_elapsed:
            # Reset circuit to half-open (allow one try)
            health.circuit_open = False
            health.failure_count = 0
            health.is_available = True
            health._half_open = True
            logger.info("Circuit breaker HALF-OPEN for %s (cooldown elapsed)", model_name)
            return False

        return True

    def _is_healthy(self, model_name: str) -> bool:
        """Check if model is considered healthy."""
        health = self.health.get(model_name)
        if not health:
            return True  # Unknown models assumed healthy
        return health.is_available

    def _record_success(self, model_name: str, latency_ms: float):
        """Record a successful call."""
        if model_name not in self.health:
            self.health[model_name] = ModelHealth()

        health = self.health[model_name]
        health.total_calls += 1
        health.failure_count = 0  # Reset consecutive failure count

        # Exponential moving average of latency
        if health.avg_latency_ms > 0:
            health.avg_latency_ms = 0.9 * health.avg_latency_ms + 0.1 * latency_ms
        else:
            health.avg_latency_ms = latency_ms

        health.is_available = True
        health.next_retry_at = None
        if getattr(health, "_half_open", False):
            health._half_open = False
            logger.info("Circuit breaker CLOSED for %s (recovered after half-open)", model_name)

    def _record_failure(self, model_name: str):
        """Record a failed call and potentially open circuit breaker."""
        if model_name not in self.health:
            self.health[model_name] = ModelHealth()

        health = self.health[model_name]
        health.total_calls += 1
        health.total_failures += 1
        health.failure_count += 1
        health.last_failure_at = time.time()

        config = self._get_config(model_name)
        if config and health.failure_count >= config.circuit_breaker_threshold:
            health.circuit_open = True
            health.circuit_opened_at = time.time()
            health.next_retry_at = time.time() + config.circuit_breaker_cooldown
            health.is_available = False
            logger.warning(
                f"🔴 Circuit breaker OPEN for {model_name} "
                f"({health.failure_count} consecutive failures). "
                f"Cooldown: {config.circuit_breaker_cooldown}s"
            )

    def _get_config(self, model_name: str) -> Optional[ModelConfig]:
        """Find config for a model name."""
        for configs in self.model_registry.values():
            for config in configs:
                if config.name == model_name:
                    return config
        return None

    # ─── Token Management ──────────────────────────────

    def _truncate_prompt(self, prompt: str, max_context_tokens: int) -> str:
        """
        Truncate prompt to fit within model's context window.
        Rough estimate: 1 token ≈ 4 characters.
        """
        if max_context_tokens <= 0 or max_context_tokens >= 100000:
            return prompt  # No limit

        # Reserve tokens for system prompt and response
        available_tokens = max_context_tokens - 1000  # Reserve for system + response
        if available_tokens <= 0:
            available_tokens = max_context_tokens // 2

        max_chars = available_tokens * 4  # Rough estimate

        if len(prompt) <= max_chars:
            return prompt

        # Smart truncation: keep beginning and end
        head_size = int(max_chars * 0.7)
        tail_size = int(max_chars * 0.3)

        truncated = (
            prompt[:head_size]
            + f"\n\n... [truncated {len(prompt) - max_chars} characters to fit {max_context_tokens} token context] ...\n\n"
            + prompt[-tail_size:]
        )

        logger.warning(
            f"Prompt truncated from {len(prompt)} to {len(truncated)} chars "
            f"(max_context_tokens={max_context_tokens})"
        )
        return truncated

    # ─── JSON Extraction ────────────────────────────────

    def _extract_json(self, text: str) -> Optional[dict]:
        """Extract valid JSON from LLM response (handles markdown wrapping)."""
        import re

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON in markdown code block
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON object anywhere in text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # Try to find JSON array
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None

    # ─── Embedding with Caching ────────────────────────

    @lru_cache(maxsize=1000)
    def _embed_cached(self, text: str) -> tuple:
        """
        Cached embedding. Returns tuple because lists are unhashable for lru_cache.
        """
        result = self._embed_uncached(text)
        return tuple(result)

    def _embed_uncached(self, text: str) -> List[float]:
        """Direct embedding call without caching."""
        try:
            return self.specialist_router.route_embedding([text])[0]
        except Exception as e:
            config = self.model_registry[ModelCapability.EMBEDDING][0]
            logger.error(f"Embedding failed for model {config.name}: {e}")
            raise

    # ─── Async Support ─────────────────────────────────

    async def classify_async(self, prompt: str) -> str:
        """Async classification."""
        async with self._semaphore:
            return await asyncio.to_thread(self.classify, prompt)

    async def generate_test_plan_async(self, prompt: str) -> str:
        """Async test plan generation."""
        async with self._semaphore:
            return await asyncio.to_thread(self.generate_test_plan, prompt)

    async def analyze_code_async(self, prompt: str) -> str:
        """Async code analysis."""
        async with self._semaphore:
            return await asyncio.to_thread(self.analyze_code, prompt)

    async def deep_analyze_failure_async(self, prompt: str) -> str:
        """Async deep failure analysis."""
        async with self._semaphore:
            return await asyncio.to_thread(self.deep_analyze_failure, prompt)

    async def write_report_async(self, prompt: str) -> str:
        """Async report writing."""
        async with self._semaphore:
            return await asyncio.to_thread(self.write_report, prompt)

    async def embed_text_async(self, text: str) -> List[float]:
        """Async embedding."""
        async with self._semaphore:
            return await asyncio.to_thread(self.embed_text, text)

    # ─── Health Check & Monitoring ─────────────────────

    def check_all_models(self) -> Dict[str, bool]:
        """
        Check availability of all configured models.
        Performs a quick ping test on each model.
        """
        results = {}
        all_models = set()

        for configs in self.model_registry.values():
            for config in configs:
                all_models.add(config.name)

        for model in sorted(all_models):
            try:
                self.client.chat(
                    model=model,
                    prompt="ping",
                    system="Reply with 'pong' only. No other text.",
                    temperature=0.0,
                )
                results[model] = True
                if model in self.health:
                    self.health[model].is_available = True
                    self.health[model].last_checked = time.time()
                else:
                    self.health[model] = ModelHealth(
                        is_available=True,
                        last_checked=time.time(),
                    )
                logger.info(f"✓ Model available: {model}")
            except Exception as e:
                results[model] = False
                if model in self.health:
                    self.health[model].is_available = False
                    self.health[model].last_checked = time.time()
                else:
                    self.health[model] = ModelHealth(
                        is_available=False,
                        last_checked=time.time(),
                    )
                logger.warning(f"✗ Model unavailable: {model} ({e})")

        available = sum(1 for v in results.values() if v)
        total = len(results)
        logger.info(f"Model health check complete: {available}/{total} available")
        return results

    def get_health_report(self) -> Dict[str, Any]:
        """Get full health report for monitoring and debugging."""
        report = {}
        for model_name, health in self.health.items():
            config = self._get_config(model_name)
            total = health.total_calls
            failures = health.total_failures
            success_rate = ((total - failures) / total * 100) if total > 0 else 100.0

            report[model_name] = {
                "available": health.is_available,
                "circuit_open": health.circuit_open,
                "consecutive_failures": health.failure_count,
                "total_calls": total,
                "total_failures": failures,
                "success_rate_percent": round(success_rate, 1),
                "avg_latency_ms": round(health.avg_latency_ms, 1),
                "last_checked": health.last_checked,
                "capability": config.capability.value if config else "unknown",
                "max_context_tokens": config.max_context_tokens if config else 0,
                "circuit_breaker_threshold": config.circuit_breaker_threshold if config else 0,
            }

        return report

    def reset_circuit_breakers(self):
        """Manually reset all circuit breakers (useful after fixing underlying issues)."""
        for health in self.health.values():
            health.circuit_open = False
            health.failure_count = 0
            health.is_available = True
        logger.info("All circuit breakers reset")

    def clear_embedding_cache(self):
        """Clear the embedding cache."""
        self._embed_cached.cache_clear()
        logger.info("Embedding cache cleared")


# ─── Global Instance ───────────────────────────────────

_default_router: Optional[LLMRouter] = None


def get_router(
    client: Optional[OllamaClient] = None,
    max_concurrent: int = 3,
) -> LLMRouter:
    """Get or create the global router instance."""
    global _default_router
    if _default_router is None:
        _default_router = LLMRouter(
            client=client,
            max_concurrent=max_concurrent,
        )
    return _default_router


# ─── CLI Test ──────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    print("=" * 60)
    print("LLM Router - Health Check & Smoke Test")
    print("=" * 60)

    router = get_router()

    # Check all models
    print("\n[1] Checking model availability...")
    health = router.check_all_models()
    for model, available in health.items():
        status = "✓ AVAILABLE" if available else "✗ UNAVAILABLE"
        print(f"  {status}: {model}")

    # Run classification test
    print("\n[2] Testing classification...")
    try:
        result = router.classify("login button does nothing when clicked")
        print(f"  Result: {result[:200]}")
    except Exception as e:
        print(f"  Failed: {e}")

    # Run code analysis test
    print("\n[3] Testing code analysis...")
    try:
        result = router.analyze_code("def divide(a, b): return a / b  # what's wrong?")
        print(f"  Result: {result[:200]}")
    except Exception as e:
        print(f"  Failed: {e}")

    # Show health report
    print("\n[4] Health Report:")
    report = router.get_health_report()
    for model, stats in report.items():
        print(f"  {model}:")
        print(f"    Available: {stats['available']}")
        print(f"    Success Rate: {stats['success_rate_percent']}%")
        print(f"    Avg Latency: {stats['avg_latency_ms']}ms")
        print(f"    Circuit Open: {stats['circuit_open']}")

    print("\n✓ Router test complete")
