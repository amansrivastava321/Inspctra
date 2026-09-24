# Live Execution

Live execution in QA-AI runs scenario flows against real browser sessions when environment support is present.

## Main flow

1. `LiveScenarioRunner` initializes `PlaywrightEngine`, `NetworkCapture`, and `TraceRecorder`.
2. Scenario steps execute with concrete actions (`navigate`, `click`, `fill`, `verify`).
3. Runtime artifacts are persisted for downstream replay/correlation/reporting.

## Runtime artifacts

1. `live_scenario_results.json`
2. `execution_trace.json`
3. `network_trace.json`

## Environment dependency

Live browser availability depends on local Playwright setup and reachable target URLs. If unavailable, QA-AI can continue in deterministic/planning-oriented paths rather than forcing unsafe execution.
