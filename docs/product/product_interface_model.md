# Product Interface Model

`qa_ai/schemas/product_interface_schema.py` defines the three Pydantic models that represent product-level interactions with the Inspectra platform. These are artifacts — they get written to the artifact store so cross-session analysis can reconstruct what a user did.

## Models

### `CLIRunSummaryArtifact`

Written at the end of every `inspectra audit` invocation.

| Field | Type | Description |
|---|---|---|
| `artifact_type` | `str` | Always `"cli_run_summary"` |
| `run_id` | `str` | UUID for this run |
| `command` | `str` | CLI command (`"audit"`) |
| `subcommand` | `Optional[str]` | Subcommand if applicable |
| `target_path` | `Optional[str]` | Path that was audited |
| `profile` | `Optional[str]` | Audit profile used |
| `status` | `str` | `"ok"` \| `"failed"` \| `"error"` |
| `exit_code` | `int` | Process exit code |
| `started_at` | `str` | ISO timestamp |
| `completed_at` | `Optional[str]` | ISO timestamp |
| `duration_seconds` | `Optional[float]` | Wall-clock time |
| `phases_executed` | `List[str]` | Phases that ran |
| `artifacts_generated` | `List[str]` | Artifact names written |
| `errors` | `List[str]` | Error messages |
| `warnings` | `List[str]` | Warning messages |
| `dry_run` | `bool` | Whether this was a dry run |
| `cli_version` | `str` | Inspectra version string |

### `WebAppSessionArtifact`

Written when the dashboard server starts (`on_event("startup")`).

| Field | Type | Description |
|---|---|---|
| `artifact_type` | `str` | Always `"webapp_session"` |
| `session_id` | `str` | UUID for this session |
| `host` | `str` | Bound host |
| `port` | `int` | Bound port |
| `artifacts_dir` | `str` | Absolute path to artifacts dir |
| `started_at` | `str` | ISO timestamp |
| `read_only` | `bool` | Always `True` — the dashboard never writes |
| `routes_registered` | `List[str]` | All registered route paths |

### `ProductInterfaceSummaryArtifact`

Cross-session summary that can be computed over multiple `cli_run_summary` and `webapp_session` artifacts to understand usage patterns.

| Field | Type | Description |
|---|---|---|
| `artifact_type` | `str` | Always `"product_interface_summary"` |
| `generated_at` | `str` | ISO timestamp |
| `total_cli_runs` | `int` | Count of CLI runs |
| `total_dashboard_sessions` | `int` | Count of dashboard sessions |
| `commands_used` | `List[str]` | Distinct commands invoked |
| `profiles_used` | `List[str]` | Distinct profiles run |
| `last_audit_target` | `Optional[str]` | Most recent target path |
| `last_audit_status` | `Optional[str]` | Most recent audit status |
| `platform_version` | `str` | Inspectra version |

## Usage

```python
from qa_ai.schemas.product_interface_schema import CLIRunSummaryArtifact
from qa_ai.runtime.artifact_store import ArtifactStore

summary = CLIRunSummaryArtifact(
    command="audit",
    target_path="src/",
    status="completed",
    phases_executed=["discovery", "analysis"],
)
store = ArtifactStore(base_dir="artifacts/")
store.save_artifact("cli_run_summary", summary.model_dump())
```
