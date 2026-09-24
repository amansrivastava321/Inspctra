# Permission Model

QA-AI uses permission-gated execution for operations that can cause side effects.

## Current enforcement points

1. remediation actions are blocked until explicit approval (`RemediationEngine`).
2. disruptive chaos actions require explicit permission (`ChaosEngine`).
3. emulator/simulator lifecycle operations require explicit permission when not dry-run.
4. network real-control requests are blocked without explicit permission in distributed/mobile controllers.

## Design intent

Keep autonomous analysis capability high while ensuring potentially impactful changes/actions are explicitly authorized.

## Cloud Model Privacy Controls

Specialist cloud-first routing is guarded by explicit controls:

1. `QA_AI_ALLOW_CLOUD_MODELS=false` forces local-only routing.
2. `QA_AI_PRIVATE_CODE_MODE=true` marks prompts/contexts as private-sensitive.
3. `QA_AI_REQUIRE_CLOUD_PERMISSION_FOR_PRIVATE_CODE=true` requires explicit cloud permission for private code paths.
4. `QA_AI_REDACT_CLOUD_CONTEXT=true` allows sending only redacted/summary context to cloud providers.
5. On cloud failure, timeout, provider-unavailable, rate-limit, or invalid JSON, routing falls back to local models, then deterministic logic.
