"""
runtime_context - RuntimeContext deep wiring for the interactive test loop.

Converts raw connector state (RuntimeContext) into normalized, secret-free
context models that drive test execution, verification, evidence collection,
and safety policy enforcement.

Exports:
    ContextAdapter              RuntimeContext → RuntimeTestContext
    ContextCapabilityMapper     RuntimeTestContext → RuntimeCapabilityPlan
    ContextVerificationPlanner  plan per-action verification checks
    ContextEvidenceCollector    aggregate evidence from all sources
    ContextSafetyPolicy         context-level safety rules
    ContextReporter             write JSON report artifacts

    RuntimeTestContext          normalized context for test loop
    RuntimeCapabilityPlan       available methods given context
    ContextEvidenceBundle       per-step aggregated evidence
    ContextVerificationPlan     per-action check plan
    ContextSafetyDecision       safety policy result
    UITestMethod                enum: playwright_web, appium_android, ...
    VerificationMethod          enum: backend_api, database_read, ...
    EvidenceSource              enum: backend_health, screenshot, ...
"""
from qa_ai.interactive_runtime.runtime_context.context_models import (
    ContextEvidenceBundle,
    ContextVerificationPlan,
    EvidenceSource,
    RuntimeCapabilityPlan,
    RuntimeTestContext,
    UITestMethod,
    VerificationMethod,
)
from qa_ai.interactive_runtime.runtime_context.context_adapter import ContextAdapter
from qa_ai.interactive_runtime.runtime_context.context_capability_mapper import (
    ContextCapabilityMapper,
)
from qa_ai.interactive_runtime.runtime_context.context_verification_planner import (
    ContextVerificationPlanner,
)
from qa_ai.interactive_runtime.runtime_context.context_evidence_collector import (
    ContextEvidenceCollector,
)
from qa_ai.interactive_runtime.runtime_context.context_safety_policy import (
    ContextSafetyDecision,
    ContextSafetyPolicy,
)
from qa_ai.interactive_runtime.runtime_context.context_reporter import ContextReporter

__all__ = [
    "ContextAdapter",
    "ContextCapabilityMapper",
    "ContextEvidenceBundle",
    "ContextEvidenceCollector",
    "ContextReporter",
    "ContextSafetyDecision",
    "ContextSafetyPolicy",
    "ContextVerificationPlan",
    "ContextVerificationPlanner",
    "EvidenceSource",
    "RuntimeCapabilityPlan",
    "RuntimeTestContext",
    "UITestMethod",
    "VerificationMethod",
]
