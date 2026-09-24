"""
memory_models.py - Pydantic v2 models for the memory kernel.

No secrets. No raw prompts. No DB URLs. No API keys.
Reusable: no Inspectra/FlowBook/Videomation-specific fields.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Scope ──────────────────────────────────────────────────────────────────────

class ProjectMemoryScope(BaseModel):
    scope_id: str
    project_id: str
    app_id: str
    product_area: str = ""
    environment: str = "default"
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


# ── Baseline ───────────────────────────────────────────────────────────────────

class GoldenBaseline(BaseModel):
    baseline_id: str
    scope_id: str
    baseline_name: str
    baseline_type: str = "smoke"   # smoke|regression|release|platform|connector|custom
    app_type: str = ""
    run_id: str
    flow_ids: List[str] = Field(default_factory=list)
    workflow_fingerprint: str = ""
    screen_fingerprints: List[str] = Field(default_factory=list)
    api_fingerprints: List[str] = Field(default_factory=list)
    db_fingerprints: List[str] = Field(default_factory=list)
    connector_fingerprints: List[str] = Field(default_factory=list)
    evidence_manifest_hash: str = ""
    summary: str = ""
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    active: bool = True


# ── Run Delta ──────────────────────────────────────────────────────────────────

class RunDelta(BaseModel):
    delta_id: str
    scope_id: str
    baseline_id: str
    run_id: str
    run_type: str = "regression"
    verdict_change: Optional[str] = None   # "pass→fail" | "fail→pass" | None
    changed_steps: List[str] = Field(default_factory=list)
    new_failures: List[str] = Field(default_factory=list)
    resolved_failures: List[str] = Field(default_factory=list)
    new_unclear: List[str] = Field(default_factory=list)
    new_blocked: List[str] = Field(default_factory=list)
    timing_deltas: Dict[str, float] = Field(default_factory=dict)
    connector_deltas: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_deltas: List[Dict[str, Any]] = Field(default_factory=list)
    fingerprint_deltas: List[str] = Field(default_factory=list)
    summary_delta: str = ""
    storage_bytes: int = 0
    created_at: str = Field(default_factory=_now)


# ── Evidence Fingerprint ───────────────────────────────────────────────────────

class EvidenceFingerprint(BaseModel):
    fingerprint_id: str
    scope_id: str
    run_id: str
    step_id: str = ""
    evidence_type: str = "unknown"   # screenshot|log|api|db|trace|connector
    content_hash: str = ""
    perceptual_hash: str = ""
    semantic_hash: str = ""
    schema_hash: str = ""
    state_hash: str = ""
    workflow_hash: str = ""
    size_bytes: int = 0
    compact_size_bytes: int = 0
    duplicate_of: Optional[str] = None
    value_score: float = 0.5
    retention_class: str = "warm"   # hot|warm|cold|delete_candidate
    artifact_ref: str = ""
    created_at: str = Field(default_factory=_now)


# ── Compact Summary ────────────────────────────────────────────────────────────

class CompactSummary(BaseModel):
    summary_id: str
    scope_id: str
    source_type: str = "run"   # run|finding|pattern|trajectory|report
    source_id: str = ""
    summary_text: str
    summary_hash: str = ""
    entities: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    severity: str = "info"   # info|low|medium|high|critical
    confidence: float = 0.5
    utility_score: float = 0.5
    embedding_ref: Optional[str] = None
    created_at: str = Field(default_factory=_now)

    @field_validator("summary_text")
    @classmethod
    def summary_not_raw_prompt(cls, v: str) -> str:
        # Refuse to store obvious system-prompt-like text
        low = v.lower()
        if low.startswith("you are") or low.startswith("system:"):
            return "[REDACTED_PROMPT]"
        return v


# ── Finding Memory ─────────────────────────────────────────────────────────────

class FindingMemory(BaseModel):
    finding_id: str
    scope_id: str
    canonical_failure_hash: str
    title: str
    failure_type: str = "unknown"
    severity: str = "medium"
    confidence: float = 0.5
    first_seen: str = Field(default_factory=_now)
    last_seen: str = Field(default_factory=_now)
    frequency: int = 1
    affected_flows: List[str] = Field(default_factory=list)
    affected_components: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    status: str = "open"   # open|resolved|wont_fix|known_flake
    pattern_id: Optional[str] = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


# ── Fix Memory ─────────────────────────────────────────────────────────────────

class FixMemory(BaseModel):
    fix_id: str
    scope_id: str
    finding_id: str
    fix_attempt_id: str = ""
    commit_hash: str = ""
    change_summary: str = ""
    before_verdict: str = "fail"
    after_verdict: str = "unknown"
    retest_run_id: str = ""
    regression_status: str = "unknown"   # clean|regression|partial
    confidence: float = 0.5
    created_at: str = Field(default_factory=_now)


# ── Pattern Memory ─────────────────────────────────────────────────────────────

class PatternMemory(BaseModel):
    pattern_id: str
    scope_id: str
    pattern_type: str   # repeated_failure|flaky_flow|regression|capability_gap|performance_drift|connector_instability|ai_output_instability|permission_block|environment_drift
    canonical_template: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    frequency: int = 1
    confidence: float = 0.5
    impact_score: float = 0.5
    first_seen: str = Field(default_factory=_now)
    last_seen: str = Field(default_factory=_now)
    related_findings: List[str] = Field(default_factory=list)
    related_fixes: List[str] = Field(default_factory=list)
    embedding_ref: Optional[str] = None
    active: bool = True


# ── Reasoning Trajectory ───────────────────────────────────────────────────────

class ReasoningTrajectory(BaseModel):
    trajectory_id: str
    scope_id: str
    problem_signature: str
    reasoning_steps: List[str] = Field(default_factory=list)
    evidence_checked: List[str] = Field(default_factory=list)
    hypotheses: List[str] = Field(default_factory=list)
    action_taken: str = ""
    outcome: str = ""
    reusable_for: List[str] = Field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    utility_score: float = 0.5
    embedding_ref: Optional[str] = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)

    @field_validator("reasoning_steps")
    @classmethod
    def no_raw_chain_of_thought(cls, v: List[str]) -> List[str]:
        """Block hidden chain-of-thought — only safe summaries."""
        cleaned = []
        for step in v:
            low = step.lower()
            if any(kw in low for kw in ["<thinking>", "</thinking>", "chain-of-thought", "<cot>"]):
                cleaned.append("[COT_REDACTED]")
            else:
                cleaned.append(step)
        return cleaned


# ── Memory Embedding ───────────────────────────────────────────────────────────

class MemoryEmbedding(BaseModel):
    embedding_id: str
    scope_id: str
    source_type: str   # summary|pattern|trajectory|finding
    source_id: str
    model: str = "bge-m3:latest"
    dimensions: int = 1024
    quantization: str = "int8"
    vector_blob: bytes = b""   # int8 quantized
    vector_hash: str = ""
    created_at: str = Field(default_factory=_now)


# ── Retention Decision ─────────────────────────────────────────────────────────

class RetentionDecision(BaseModel):
    decision_id: str
    source_type: str
    source_id: str
    action: str   # keep|compress|delete|archive
    reason: str = ""
    utility_score: float = 0.0
    before_bytes: int = 0
    after_bytes: int = 0
    executed_at: Optional[str] = None


# ── Memory Stats ───────────────────────────────────────────────────────────────

class MemoryStats(BaseModel):
    scope_id: str
    raw_bytes_seen: int = 0
    retained_bytes: int = 0
    compacted_bytes: int = 0
    deduplicated_bytes_saved: int = 0
    compression_ratio: float = 1.0
    summaries_count: int = 0
    patterns_count: int = 0
    trajectories_count: int = 0
    embeddings_count: int = 0
