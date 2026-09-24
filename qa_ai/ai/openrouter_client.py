"""
openrouter_client.py - OpenAI-compatible client for OpenRouter.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Dict, Optional

import requests


@dataclass
class OpenRouterResult:
    success: bool
    content: str
    model: str
    provider: str
    latency_ms: float
    error_type: str = ""
    fallback_reason: str = ""


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout_seconds: int = 45,
        long_timeout_seconds: int = 180,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
    ):
        self.api_key = api_key or ""
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = int(timeout_seconds)
        self.long_timeout_seconds = int(long_timeout_seconds)
        self.max_retries = max(1, int(max_retries))
        self.retry_backoff_seconds = float(retry_backoff_seconds)

    def chat(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
    ) -> OpenRouterResult:
        return self._chat_impl(
            model=model,
            prompt=prompt,
            system=system,
            temperature=temperature,
            require_json=False,
            schema_hint=None,
        )

    def chat_json(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
        schema_hint: Optional[Dict[str, Any]] = None,
    ) -> OpenRouterResult:
        result = self._chat_impl(
            model=model,
            prompt=prompt,
            system=system,
            temperature=temperature,
            require_json=True,
            schema_hint=schema_hint,
        )
        if not result.success:
            return result
        try:
            json.loads(result.content)
            return result
        except json.JSONDecodeError:
            return OpenRouterResult(
                success=False,
                content="",
                model=model,
                provider="openrouter",
                latency_ms=result.latency_ms,
                error_type="invalid_response",
                fallback_reason="invalid_json",
            )

    def _chat_impl(
        self,
        model: str,
        prompt: str,
        system: Optional[str],
        temperature: float,
        require_json: bool,
        schema_hint: Optional[Dict[str, Any]],
    ) -> OpenRouterResult:
        if not self.api_key:
            return OpenRouterResult(
                success=False,
                content="",
                model=model,
                provider="openrouter",
                latency_ms=0.0,
                error_type="auth",
                fallback_reason="missing_api_key",
            )

        timeout = self.long_timeout_seconds if "thinking" in model else self.timeout_seconds
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if require_json:
            payload["response_format"] = {"type": "json_object"}
            if schema_hint:
                payload["schema_hint"] = schema_hint

        for attempt in range(self.max_retries):
            start = time.time()
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=timeout)
                status = response.status_code

                if status == 429:
                    return OpenRouterResult(
                        success=False,
                        content="",
                        model=model,
                        provider="openrouter",
                        latency_ms=(time.time() - start) * 1000,
                        error_type="rate_limited",
                        fallback_reason="rate_limited",
                    )
                if status in (502, 503, 504):
                    return OpenRouterResult(
                        success=False,
                        content="",
                        model=model,
                        provider="openrouter",
                        latency_ms=(time.time() - start) * 1000,
                        error_type="provider_unavailable",
                        fallback_reason="provider_unavailable",
                    )

                response.raise_for_status()
                data = response.json()
                content = self._extract_content(data)
                if not content:
                    return OpenRouterResult(
                        success=False,
                        content="",
                        model=model,
                        provider="openrouter",
                        latency_ms=(time.time() - start) * 1000,
                        error_type="invalid_response",
                        fallback_reason="invalid_response",
                    )

                return OpenRouterResult(
                    success=True,
                    content=content,
                    model=str(data.get("model") or model),
                    provider="openrouter",
                    latency_ms=(time.time() - start) * 1000,
                )
            except requests.Timeout:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                return OpenRouterResult(
                    success=False,
                    content="",
                    model=model,
                    provider="openrouter",
                    latency_ms=(time.time() - start) * 1000,
                    error_type="timeout",
                    fallback_reason="timeout",
                )
            except requests.RequestException:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                return OpenRouterResult(
                    success=False,
                    content="",
                    model=model,
                    provider="openrouter",
                    latency_ms=(time.time() - start) * 1000,
                    error_type="http_error",
                    fallback_reason="http_error",
                )
            except (ValueError, KeyError, TypeError):
                return OpenRouterResult(
                    success=False,
                    content="",
                    model=model,
                    provider="openrouter",
                    latency_ms=(time.time() - start) * 1000,
                    error_type="invalid_response",
                    fallback_reason="invalid_response",
                )

        return OpenRouterResult(
            success=False,
            content="",
            model=model,
            provider="openrouter",
            latency_ms=0.0,
            error_type="unknown",
            fallback_reason="unknown",
        )

    def _extract_content(self, payload: Dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message", {}) if isinstance(first, dict) else {}
        if isinstance(message, dict):
            content = message.get("content", "")
            return str(content or "")
        return ""
