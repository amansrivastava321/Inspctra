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

## Watching a run, and running a test case as one flow

Automated pack runs have two opt-in options. Both are off by default, so an ordinary run is unchanged: an
invisible browser, and every step starting from a clean page.

| Option | API field | What it does |
|---|---|---|
| Watch it run | `watch: true` (and `slow_mo_ms`, default 350, 0-5000) | Opens a **visible** Chromium window on the machine running Inspectra and pauses between browser actions so a person can follow along. |
| Run each test case as one flow | `continuous: true` | Keeps the page and session (typed text, cookies, logins) between the steps of one test case. The first step of every test case still starts from a clean page. |

Both are choices in the "Start live run" dialog for automated runs, and are rejected for manual runs.

### What "watch" does and does not do

- It is a visible browser driven through Playwright. It does **not** move the operating system's mouse or
  keyboard, and it cannot drive other applications. Controlling native or desktop apps is a separate runtime
  (`qa_ai.interactive_runtime`, `python -m qa_ai.cli interactive-test`) that pack runs do not use yet.
- The window opens on the machine running the Inspectra backend. Run the backend on the machine you are
  sitting at (the normal local setup).
- With no screen available (for example a Linux server with no `DISPLAY`), or if the window cannot be opened,
  the run continues with a hidden browser and says why: a `notice` event is stored with the run (so it is
  still there after the run finishes) and also shown in the live log. It never fails just because watching
  was requested.
- Scheduled runs and retests always use the hidden browser.

### Continuous flows

Without `continuous`, each step opens a fresh browser context, so a flow such as "type a name, click Go,
check the greeting" cannot work: the typed name is gone by the time the next step runs. With `continuous`,
those steps share one page. Steps of different test cases never share a page, an API step in the middle of a
case does not disturb the browser, and a step that cannot continue falls back to a fresh page.

A step failing does not stop the rest of its test case; later steps still run and may fail as a result.
