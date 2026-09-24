"""
model_catalog.py - Generic model knowledge base for adaptive routing.

Maps model names to capability profiles.
Supports unknown models via name-pattern inference.
Not hardcoded to one user's install — inference extends to any Ollama model.

No app-specific logic. No secrets. No network calls.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set


# ── Quality / speed tiers ─────────────────────────────────────────────────────

# quality: "high" | "medium" | "low" | "unknown"
# speed:   "fast" | "medium" | "slow" | "unknown"


@dataclass
class ModelCapability:
    model: str
    estimated_memory_gb: float
    tasks_supported: List[str]        # ModelTask.values this model suits
    quality_tier: str                 # "high" | "medium" | "low"
    speed_tier: str                   # "fast" | "medium" | "slow"
    vision: bool
    embeddings: bool
    code: bool
    reasoning: bool
    # profile_ids where this model is a reasonable choice
    recommended_profiles: List[str] = field(default_factory=list)
    inferred: bool = False            # True if capability was guessed from name


# ── Known model catalog ────────────────────────────────────────────────────────
# Primary user models (used as defaults on Mac M4 16GB).
# Additional models are inferred from naming patterns.

_KNOWN_MODELS: Dict[str, ModelCapability] = {
    "qwen2.5vl:7b": ModelCapability(
        model="qwen2.5vl:7b",
        estimated_memory_gb=6.0,
        tasks_supported=["vision_screen_analysis", "ui_action_planning", "fallback_chat"],
        quality_tier="medium",
        speed_tier="medium",
        vision=True,
        embeddings=False,
        code=False,
        reasoning=False,
        recommended_profiles=["mac_m4_16gb", "pro_32gb", "workstation_64gb", "remote_gpu"],
    ),
    "qwen3.5:9b": ModelCapability(
        model="qwen3.5:9b",
        estimated_memory_gb=6.6,
        tasks_supported=["ui_action_planning", "ai_oracle", "report_summary", "fallback_chat"],
        quality_tier="high",
        speed_tier="medium",
        vision=False,
        embeddings=False,
        code=False,
        reasoning=True,
        recommended_profiles=["mac_m4_16gb", "pro_32gb", "workstation_64gb", "remote_gpu"],
    ),
    "deepseek-r1:7b": ModelCapability(
        model="deepseek-r1:7b",
        estimated_memory_gb=4.7,
        tasks_supported=["ai_oracle", "root_cause_analysis", "code_log_analysis"],
        quality_tier="high",
        speed_tier="medium",
        vision=False,
        embeddings=False,
        code=True,
        reasoning=True,
        recommended_profiles=["mac_m4_16gb", "pro_32gb", "workstation_64gb", "remote_gpu"],
    ),
    "phi4-mini:latest": ModelCapability(
        model="phi4-mini:latest",
        estimated_memory_gb=2.5,
        tasks_supported=["step_narration", "fallback_chat", "ui_action_planning",
                         "ai_oracle", "report_summary"],
        quality_tier="medium",
        speed_tier="fast",
        vision=False,
        embeddings=False,
        code=False,
        reasoning=False,
        recommended_profiles=["low_ram_8gb", "mac_m4_16gb", "pro_32gb",
                              "workstation_64gb", "remote_gpu"],
    ),
    "gemma4:e4b": ModelCapability(
        model="gemma4:e4b",
        estimated_memory_gb=9.6,
        tasks_supported=["report_summary", "ui_action_planning"],
        quality_tier="high",
        speed_tier="slow",
        vision=False,
        embeddings=False,
        code=False,
        reasoning=False,
        recommended_profiles=["mac_m4_16gb", "pro_32gb", "workstation_64gb", "remote_gpu"],
    ),
    "dolphincoder:7b": ModelCapability(
        model="dolphincoder:7b",
        estimated_memory_gb=4.2,
        tasks_supported=["code_log_analysis", "root_cause_analysis"],
        quality_tier="medium",
        speed_tier="medium",
        vision=False,
        embeddings=False,
        code=True,
        reasoning=False,
        recommended_profiles=["mac_m4_16gb", "pro_32gb", "workstation_64gb", "remote_gpu"],
    ),
    "dolphin-mistral:7b": ModelCapability(
        model="dolphin-mistral:7b",
        estimated_memory_gb=4.1,
        tasks_supported=["fallback_chat", "step_narration", "code_log_analysis"],
        quality_tier="medium",
        speed_tier="medium",
        vision=False,
        embeddings=False,
        code=True,
        reasoning=False,
        recommended_profiles=["mac_m4_16gb", "pro_32gb", "workstation_64gb", "remote_gpu"],
    ),
    "bge-m3:latest": ModelCapability(
        model="bge-m3:latest",
        estimated_memory_gb=1.2,
        tasks_supported=["embeddings"],
        quality_tier="high",
        speed_tier="fast",
        vision=False,
        embeddings=True,
        code=False,
        reasoning=False,
        recommended_profiles=["low_ram_8gb", "mac_m4_16gb", "pro_32gb",
                              "workstation_64gb", "remote_gpu"],
    ),
    # Common alternative/additional models
    "llama3:8b": ModelCapability(
        model="llama3:8b",
        estimated_memory_gb=5.0,
        tasks_supported=["fallback_chat", "step_narration", "ai_oracle"],
        quality_tier="medium",
        speed_tier="medium",
        vision=False, embeddings=False, code=False, reasoning=False,
        recommended_profiles=["mac_m4_16gb", "pro_32gb", "workstation_64gb"],
    ),
    "llama3.1:8b": ModelCapability(
        model="llama3.1:8b",
        estimated_memory_gb=5.0,
        tasks_supported=["fallback_chat", "step_narration", "ai_oracle"],
        quality_tier="medium",
        speed_tier="medium",
        vision=False, embeddings=False, code=False, reasoning=False,
        recommended_profiles=["mac_m4_16gb", "pro_32gb", "workstation_64gb"],
    ),
    "mistral:7b": ModelCapability(
        model="mistral:7b",
        estimated_memory_gb=4.1,
        tasks_supported=["fallback_chat", "step_narration", "code_log_analysis"],
        quality_tier="medium",
        speed_tier="medium",
        vision=False, embeddings=False, code=True, reasoning=False,
        recommended_profiles=["mac_m4_16gb", "pro_32gb", "workstation_64gb"],
    ),
    "codellama:7b": ModelCapability(
        model="codellama:7b",
        estimated_memory_gb=4.0,
        tasks_supported=["code_log_analysis", "root_cause_analysis"],
        quality_tier="medium",
        speed_tier="medium",
        vision=False, embeddings=False, code=True, reasoning=False,
        recommended_profiles=["mac_m4_16gb", "pro_32gb", "workstation_64gb"],
    ),
    "phi3:mini": ModelCapability(
        model="phi3:mini",
        estimated_memory_gb=2.3,
        tasks_supported=["step_narration", "fallback_chat"],
        quality_tier="low",
        speed_tier="fast",
        vision=False, embeddings=False, code=False, reasoning=False,
        recommended_profiles=["low_ram_8gb", "mac_m4_16gb"],
    ),
    "nomic-embed-text:latest": ModelCapability(
        model="nomic-embed-text:latest",
        estimated_memory_gb=0.5,
        tasks_supported=["embeddings"],
        quality_tier="medium",
        speed_tier="fast",
        vision=False, embeddings=True, code=False, reasoning=False,
        recommended_profiles=["low_ram_8gb", "mac_m4_16gb", "pro_32gb",
                              "workstation_64gb", "remote_gpu"],
    ),
    "mxbai-embed-large:latest": ModelCapability(
        model="mxbai-embed-large:latest",
        estimated_memory_gb=0.7,
        tasks_supported=["embeddings"],
        quality_tier="high",
        speed_tier="fast",
        vision=False, embeddings=True, code=False, reasoning=False,
        recommended_profiles=["low_ram_8gb", "mac_m4_16gb", "pro_32gb",
                              "workstation_64gb", "remote_gpu"],
    ),
}


# ── Size → memory estimate ────────────────────────────────────────────────────

_SIZE_MEMORY_GB: Dict[str, float] = {
    "1b":  0.8,
    "2b":  1.5,
    "3b":  2.0,
    "4b":  2.5,
    "7b":  4.5,
    "8b":  5.0,
    "9b":  6.0,
    "11b": 7.0,
    "13b": 8.0,
    "14b": 9.0,
    "20b": 13.0,
    "27b": 17.0,
    "32b": 20.0,
    "34b": 22.0,
    "40b": 26.0,
    "70b": 45.0,
    "72b": 46.0,
}

_SIZE_RE = re.compile(r"[:\-_]?(\d+(?:\.\d+)?)[bB]\b")


# ── Inference from model name ─────────────────────────────────────────────────

def _infer_memory_gb(model: str) -> float:
    m = _SIZE_RE.search(model)
    if m:
        size_key = f"{m.group(1).rstrip('0').rstrip('.')}b"
        if size_key in _SIZE_MEMORY_GB:
            return _SIZE_MEMORY_GB[size_key]
        # Approximate: 0.65 GB per billion params at 4-bit
        try:
            return round(float(m.group(1)) * 0.65, 1)
        except ValueError:
            pass
    return 4.0  # safe default


def _infer_capabilities(model: str) -> ModelCapability:
    """
    Infer model capabilities from name patterns.

    Used for models not in the known catalog.
    """
    name = model.lower()
    mem_gb = _infer_memory_gb(name)

    # Vision
    vision = any(p in name for p in ("vl", "vision", "llava", "cogvlm", "moondream", "bakllava"))
    # Embeddings
    embeddings = any(p in name for p in ("embed", "bge", "e5-", "nomic", "mxbai"))
    # Code
    code = any(p in name for p in ("coder", "code", "codellama", "starcoder", "deepseek-coder",
                                    "codestral", "granite-code"))
    # Reasoning
    reasoning = any(p in name for p in ("r1", "reason", "think", "o1", "qwq",
                                         "deepseek-r", "reflection"))

    # Tasks
    tasks: List[str] = []
    if embeddings:
        tasks.append("embeddings")
    elif vision:
        tasks.extend(["vision_screen_analysis", "ui_action_planning"])
    elif code:
        tasks.extend(["code_log_analysis", "root_cause_analysis"])
    elif reasoning:
        tasks.extend(["ai_oracle", "root_cause_analysis", "ui_action_planning"])
    else:
        tasks.extend(["fallback_chat", "step_narration"])

    if not embeddings and not vision:
        tasks.extend(["fallback_chat"])

    # Quality tier by size
    if mem_gb >= 15.0:
        quality = "high"
        speed = "slow"
    elif mem_gb >= 6.0:
        quality = "medium"
        speed = "medium"
    elif mem_gb >= 3.0:
        quality = "medium"
        speed = "fast"
    else:
        quality = "low"
        speed = "fast"

    # Profiles
    profiles: List[str] = []
    if mem_gb <= 3.5:
        profiles.append("low_ram_8gb")
    if mem_gb <= 10.0:
        profiles.append("mac_m4_16gb")
    if mem_gb <= 20.0:
        profiles.append("pro_32gb")
    if mem_gb <= 64.0:
        profiles.extend(["workstation_64gb", "remote_gpu"])

    return ModelCapability(
        model=model,
        estimated_memory_gb=mem_gb,
        tasks_supported=list(dict.fromkeys(tasks)),
        quality_tier=quality,
        speed_tier=speed,
        vision=vision,
        embeddings=embeddings,
        code=code,
        reasoning=reasoning,
        recommended_profiles=profiles or ["mac_m4_16gb"],
        inferred=True,
    )


# ── ModelCatalog ──────────────────────────────────────────────────────────────

class ModelCatalog:
    """
    Lookup or infer model capabilities.

    Unknown models are inferred from name patterns.
    All lookups are read-only. No network calls.
    """

    def __init__(self, extra: Optional[Dict[str, ModelCapability]] = None) -> None:
        self._db: Dict[str, ModelCapability] = dict(_KNOWN_MODELS)
        if extra:
            self._db.update(extra)

    def get(self, model: str) -> ModelCapability:
        """Return capability for model. Infers if unknown."""
        # Exact match
        if model in self._db:
            return self._db[model]
        # Partial match: strip tag variant (e.g. "phi4-mini" matches "phi4-mini:latest")
        base = model.split(":")[0]
        for key in self._db:
            if key.split(":")[0] == base:
                return self._db[key]
        # Infer from name
        inferred = _infer_capabilities(model)
        return inferred

    def list_known(self) -> List[str]:
        return list(self._db.keys())

    def models_for_task(
        self,
        task: str,
        installed: Optional[List[str]] = None,
        max_memory_gb: float = 999.0,
    ) -> List[ModelCapability]:
        """
        Return models suitable for a task, optionally filtered by installed list
        and memory limit. Sorted by quality_tier (high first).
        """
        candidates: List[ModelCapability] = []
        pool = installed if installed is not None else list(self._db.keys())

        for m in pool:
            cap = self.get(m)
            if task in cap.tasks_supported and cap.estimated_memory_gb <= max_memory_gb:
                candidates.append(cap)

        _quality_order = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
        return sorted(candidates, key=lambda c: _quality_order.get(c.quality_tier, 3))


def get_default_catalog() -> ModelCatalog:
    return ModelCatalog()
