"""
provider_discovery.py - Detect locally running LLM providers.

Probes well-known localhost endpoints only.
External URLs blocked by default unless trust_external=True.
No cloud calls. No API key required for discovery.
Timeouts enforced. No shell. No subprocess. No eval.

Security:
- Only probes localhost (127.0.0.1 / [::1]).
- External URL probe requires explicit trust_external=True.
- All URLs validated before any HTTP call (scheme, host).
- No authentication headers sent during discovery.
- No sensitive data in returned DiscoveredProvider.

SSRF mitigation:
- Scheme must be http or https.
- Host must be loopback UNLESS trust_external=True.
- file://, javascript://, data://, ftp:// always blocked.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

_BLOCKED_SCHEMES = frozenset({"file", "javascript", "data", "ftp", "gopher", "ldap"})
_LOOPBACK_HOSTS  = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})

# Well-known local provider endpoints
_OLLAMA_DEFAULT     = "http://127.0.0.1:11434"
_LMSTUDIO_DEFAULT   = "http://127.0.0.1:1234"
_LLAMACPP_DEFAULT   = "http://127.0.0.1:8080"
_VLLM_DEFAULT       = "http://127.0.0.1:8000"

_DISCOVERY_TIMEOUT  = 2   # seconds — short to avoid blocking UI


@dataclass
class DiscoveredProvider:
    provider_id: str
    provider_type: str     # "ollama" | "lm_studio" | "llama_cpp" | "vllm" | "custom_openai"
    base_url: str
    reachable: bool
    models: List[str]
    local_only: bool
    warnings: List[str] = field(default_factory=list)


def _validate_url(url: str, trust_external: bool = False) -> Optional[str]:
    """
    Validate a provider URL before probing.
    Returns error string if invalid, None if OK.
    """
    try:
        p = urllib.parse.urlparse(url)
    except Exception as exc:
        return f"Invalid URL: {exc}"

    if p.scheme in _BLOCKED_SCHEMES:
        return f"Blocked URL scheme: {p.scheme!r}"
    if p.scheme not in ("http", "https"):
        return f"URL scheme must be http or https, got: {p.scheme!r}"
    if not p.netloc:
        return "URL missing host."

    host = p.hostname or ""
    if not trust_external and host not in _LOOPBACK_HOSTS:
        return (
            f"External host {host!r} blocked. "
            "Provider discovery only probes localhost. "
            "Set trust_external=True to allow."
        )
    return None


def _probe_url(url: str, timeout: int = _DISCOVERY_TIMEOUT) -> Optional[bytes]:
    """HTTP GET url. Returns body bytes or None on error."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (urllib.error.URLError, OSError, TimeoutError):
        return None
    except Exception as exc:
        logger.debug("Provider probe error at %s: %s", url, exc)
        return None


def _discover_ollama(
    base_url: str = _OLLAMA_DEFAULT,
    trust_external: bool = False,
) -> DiscoveredProvider:
    err = _validate_url(base_url, trust_external)
    if err:
        return DiscoveredProvider(
            provider_id="ollama",
            provider_type="ollama",
            base_url=base_url,
            reachable=False,
            models=[],
            local_only=True,
            warnings=[err],
        )

    data = _probe_url(f"{base_url.rstrip('/')}/api/tags")
    if data is None:
        return DiscoveredProvider(
            provider_id="ollama",
            provider_type="ollama",
            base_url=base_url,
            reachable=False,
            models=[],
            local_only=True,
            warnings=["Ollama not reachable at " + base_url],
        )
    try:
        parsed = json.loads(data)
        models = [m.get("name", "") for m in parsed.get("models", [])]
        models = [m for m in models if m]
    except (json.JSONDecodeError, KeyError):
        models = []

    return DiscoveredProvider(
        provider_id="ollama",
        provider_type="ollama",
        base_url=base_url,
        reachable=True,
        models=models,
        local_only=True,
    )


def _discover_openai_compatible(
    provider_id: str,
    provider_type: str,
    base_url: str,
    trust_external: bool = False,
) -> DiscoveredProvider:
    err = _validate_url(base_url, trust_external)
    if err:
        return DiscoveredProvider(
            provider_id=provider_id,
            provider_type=provider_type,
            base_url=base_url,
            reachable=False,
            models=[],
            local_only=not trust_external,
            warnings=[err],
        )

    url = f"{base_url.rstrip('/')}/v1/models"
    data = _probe_url(url)
    if data is None:
        # Some servers at /models directly
        url2 = f"{base_url.rstrip('/')}/models"
        data = _probe_url(url2)

    if data is None:
        return DiscoveredProvider(
            provider_id=provider_id,
            provider_type=provider_type,
            base_url=base_url,
            reachable=False,
            models=[],
            local_only=not trust_external,
            warnings=[f"{provider_type} not reachable at {base_url}"],
        )

    try:
        parsed = json.loads(data)
        raw = parsed.get("data", parsed.get("models", []))
        models = [m.get("id", m) if isinstance(m, dict) else str(m) for m in raw]
    except (json.JSONDecodeError, KeyError, TypeError):
        models = []

    return DiscoveredProvider(
        provider_id=provider_id,
        provider_type=provider_type,
        base_url=base_url,
        reachable=True,
        models=models,
        local_only=not trust_external,
    )


def discover_providers(
    ollama_url: str = _OLLAMA_DEFAULT,
    lmstudio_url: str = _LMSTUDIO_DEFAULT,
    llamacpp_url: str = _LLAMACPP_DEFAULT,
    vllm_url: str = _VLLM_DEFAULT,
    custom_urls: Optional[List[str]] = None,
    trust_external: bool = False,
    probe_lmstudio: bool = True,
    probe_llamacpp: bool = True,
    probe_vllm: bool = False,  # Disabled by default — less common
) -> List[DiscoveredProvider]:
    """
    Discover locally running LLM providers.

    Always probes Ollama.
    LM Studio, llama.cpp, vLLM probed if probe_* flags set.
    External URLs blocked unless trust_external=True.

    Returns list of DiscoveredProvider (reachable or not).
    """
    results: List[DiscoveredProvider] = []

    # Always probe Ollama
    results.append(_discover_ollama(ollama_url, trust_external))

    if probe_lmstudio:
        results.append(_discover_openai_compatible(
            "lm_studio", "lm_studio", lmstudio_url, trust_external
        ))

    if probe_llamacpp:
        results.append(_discover_openai_compatible(
            "llama_cpp", "llama_cpp", llamacpp_url, trust_external
        ))

    if probe_vllm:
        results.append(_discover_openai_compatible(
            "vllm", "vllm", vllm_url, trust_external
        ))

    # Custom local endpoints from config
    if custom_urls:
        for idx, url in enumerate(custom_urls):
            results.append(_discover_openai_compatible(
                f"custom_{idx}", "custom_http", url, trust_external
            ))

    return results


def get_installed_models(ollama_url: str = _OLLAMA_DEFAULT) -> List[str]:
    """
    Return list of model names installed in Ollama.
    Returns empty list if Ollama unreachable.
    """
    p = _discover_ollama(ollama_url)
    return p.models if p.reachable else []
