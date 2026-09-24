# AI Reasoning Overview

AI reasoning in QA-AI is an advisory layer that runs after deterministic artifacts are produced.

## Orchestrator flow

`AIReasoningOrchestrator` runs:

1. `ReasoningContextBuilder`
2. `SemanticRCAEngine`
3. `AdaptiveAuditPlanner`
4. `EvidenceSynthesizer`
5. `RiskReasoner`
6. `ScenarioGenerator`
7. `FixReasoner`
8. `LearningOptimizer`

and writes `ai_reasoning_summary`.

## Safety semantics

1. advisory-only for fix reasoning
2. deterministic-first
3. no invented evidence
4. model fallback mode supported

## Specialist Cloud-First Routing

AI cognitive paths use component-first routing (not task-size routing):

1. specialist OpenRouter model by component
2. local Ollama fallback
3. deterministic fallback

Privacy controls:

- private code mode can force local-only execution
- optional redacted Graphify summary can be sent to cloud instead of raw private code
- embeddings remain local-only (`bge-m3`)
