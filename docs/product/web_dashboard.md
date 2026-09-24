# Web Dashboard

Inspectra ships a read-only local web dashboard powered by FastAPI. It surfaces audit artifacts as a browser UI and a JSON API. No data is ever written through the web layer.

## Starting the Dashboard

```bash
python -m qa_ai.cli dashboard artifacts/ --port 8765
# or directly:
uvicorn "qa_ai.webapp.server:create_app('artifacts/')" --host 127.0.0.1 --port 8765
```

## Routes

| Path | Description |
|---|---|
| `GET /` | Dark-themed HTML dashboard |
| `GET /health` | JSON health check `{"status": "ok", ...}` |
| `GET /api/summary` | Audit summary artifact |
| `GET /api/findings` | Findings list |
| `GET /api/risk` | Risk report artifact |
| `GET /api/remediation` | Remediation summary artifact |
| `GET /api/benchmarks` | Benchmark intelligence artifact |
| `GET /api/cicd` | CI/CD release gate artifact |
| `GET /api/self-optimization` | Self-optimization plan artifact |
| `GET /api/artifacts` | List all artifact files with metadata |
| `GET /api/artifacts/{name}` | Load a specific artifact by name |
| `GET /api/reports` | List report filenames |
| `GET /api/evidence` | List evidence filenames |
| `GET /api/docs` | OpenAPI (Swagger) interactive docs |

## Architecture

```
FastAPI app (create_app)
├── CORS middleware (localhost only, GET only)
├── APIRouter (build_router)
│   └── all route handlers
├── ArtifactAPI (read-only adapter)
│   └── ArtifactStore (filesystem source of truth)
└── DashboardBuilder (HTML generator)
    └── reads from ArtifactAPI
```

Data flow: `Browser → FastAPI route → ArtifactAPI.get_*() → ArtifactStore.load_artifact()`

The web layer never writes to or deletes from the artifact store.

## Dashboard UI

The HTML dashboard is generated inline by `DashboardBuilder.build()`. It renders:

- **Status card** — color-coded (green=completed, amber=partial, red=failed)
- **Findings / Artifacts / Evidence count cards**
- **Risk Level and Risk Score cards**
- **Profile and Target cards**
- **Phases Executed** — tag pills
- **Findings table** — ID, Title, Severity badge, Category, Evidence indicator (first 50 findings)
- **Artifact list** — linked to `/api/artifacts/{name}`

## Session Artifact

On startup, the server writes `webapp_session.json` to the artifacts directory. This records:
- `session_id` (UUID)
- `started_at` (ISO timestamp)
- `routes_registered`
- `host` / `port` (from configuration)

## Running in Tests

```python
from fastapi.testclient import TestClient
from qa_ai.webapp.server import create_app

app = create_app("path/to/artifacts")
client = TestClient(app)
resp = client.get("/api/findings")
```
