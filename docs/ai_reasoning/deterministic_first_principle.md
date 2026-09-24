# Deterministic-First Principle

QA-AI treats deterministic engines and validated artifacts as source-of-truth.

## Principle

1. deterministic audit/runtime/improvement outputs are canonical
2. AI reasoning augments but does not replace deterministic outputs
3. AI-produced plans remain advisory unless separately approved by remediation controls

## Implementation notes

1. `AIReasoningOrchestrator` computes `use_model` only when enabled, model is available, and not in dry-run.
2. Semantic and planning reasoners can run in deterministic fallback mode with no model dependency.
3. AI outputs are persisted as artifacts with contract metadata and references.
