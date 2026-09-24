# Replay and Tracing

QA-AI captures execution traces and compares runs to detect regressions in runtime behavior.

## Capture

1. `TraceRecorder` records step/browser/api/scenario/network events.
2. `NetworkCapture` records request/response timing and status summaries.
3. Both write contract artifacts through `ArtifactStore`.

## Replay

`ReplayEngine` compares current and previous traces and reports:

1. timing regressions
2. status regressions
3. navigation changes
4. response changes
5. added/removed steps

Output is stored as `replay_analysis.json`.

## Contract model

Runtime contracts are defined in `qa_ai.schemas.runtime_schema`:

1. `ExecutionTraceArtifact`
2. `NetworkTraceArtifact`
3. `ReplayAnalysisArtifact`
