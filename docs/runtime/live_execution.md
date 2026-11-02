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

## Scheduled runs (background testing)

A run you start with the default options already happens in the background: no window opens and you can keep
using the machine. A **schedule** repeats that automatically. Set it on the pack page ("Schedule" panel) or with
`PATCH /api/validation-packs/{id}`.

| `schedule` | Runs |
| --- | --- |
| `hourly` | every hour at :00 |
| `every_<N>m` | every N minutes, 5 to 720 (for example `every_15m`) |
| `every_<N>h` | every N hours, 1 to 168 (for example `every_6h`) |
| `daily` / `nightly` | every day at 02:00 in the pack's timezone |
| `weekdays` | Monday to Friday at 09:00 in the pack's timezone |
| `none` | not scheduled |

- `schedule_timezone` is an IANA name (default `UTC`) and only affects `daily`, `nightly` and `weekdays`; daylight
  saving time is followed. An unknown schedule or timezone is rejected with a 400.
- `continuous: true` makes the pack's scheduled runs run each test case as one flow (see above). It is off by
  default, as it is for runs started by hand.
- A scheduled run executes exactly the steps a run started by hand would, and never opens a window.
- If a pack's previous run is still going when its next slot arrives, that slot is skipped. At most three
  scheduled runs are in flight at once.
- `notify_webhook_url` (optional): when a scheduled run **fails**, one JSON `POST` is sent there with the pack,
  the run and up to five failed steps (event `scheduled_run_failed`). Only http(s) URLs are accepted, redirects
  are not followed, the request times out after 5 seconds, and failure text is redacted for secrets. The API
  returns only the origin of a saved URL (`https://host/***`) because the path usually carries a token; send an
  empty string to remove it. Runs started by hand never send this message.

Limits to be aware of: the scheduler lives inside the Inspectra backend process, so schedules only run while
Inspectra is running and the machine is awake. If it was off at a slot, the pack runs once as soon as Inspectra starts again
(missed slots are not replayed one by one), then carries on from there. There is no email or in-app inbox yet, only the webhook.
