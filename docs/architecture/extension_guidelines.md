# Extension Guidelines

These guidelines keep QA-AI extensible without breaking deterministic behavior or safety boundaries.

## Design principles

1. Prefer deterministic-first behavior.
2. Treat artifacts as stable interfaces.
3. Keep orchestration explicit (phase methods + phase enum + mapping).
4. Keep risky operations permission-gated and dry-run by default.

## Adding new modules

1. Define clear input artifacts and output artifacts.
2. Add schema contract in `qa_ai/schemas`.
3. Register contract in `ArtifactValidator.MODEL_MAP`.
4. Ensure outputs include contract metadata and deterministic references when advisory.
5. Add focused tests before wiring into default workflows.

## Adding runtime capabilities

1. Start with planning/simulation mode.
2. Mark real side effects with explicit permission requirements.
3. Keep destructive/system-level actions blocked by default.
4. Persist traceable artifacts for every planned/executed action.

## AI reasoning extensions

1. Keep AI outputs advisory.
2. Never invent evidence.
3. Keep deterministic fallback path available when models are unavailable.
4. Link recommendations back to concrete artifacts.
5. Route models by QA-AI component/function (for example `master_orchestration`, `structured_reasoning`) rather than generic size tiers.
6. Reuse `ModelRouter` + `ModelRoutingPolicy`; do not create duplicate routing abstractions.

## Reporting extensions

1. Read from validated artifacts, not ad-hoc in-memory state.
2. Preserve `audit_summary` compatibility.
3. Keep executive and technical views synchronized on shared source artifacts.

## Error Handling Guidelines

All exception handlers in the QA platform must log the exception. Silent exception handlers (`except Exception: pass`) are prohibited.

### Preferred pattern: `log_and_fallback`

Use `log_and_fallback()` from `qa_ai.utils.error_handling` when a function can safely return a default value on failure:

```python
from qa_ai.utils.error_handling import log_and_fallback

result = log_and_fallback(
    lambda: parse_config(raw_data),
    default={},
    logger_name=__name__,
    context="parse_config",
)
```

### Preferred pattern: `@safe_fallback` decorator

For methods where the whole function should silently return a default on error:

```python
from qa_ai.utils.error_handling import safe_fallback

@safe_fallback(default=[], logger_name=__name__)
def get_available_tools(self) -> list:
    return self._registry.list_all()
```

### What NOT to do

```python
# BAD: silent, invisible failures
try:
    result = risky_operation()
except Exception:
    pass

# BAD: catches but ignores
try:
    result = risky_operation()
except Exception as e:
    result = None  # No log!
```

---

## Configuration Guidelines

All runtime configuration must use environment variables via the `Settings` dataclass.

### Adding a new configuration value

1. Add a field to `qa_ai/config/settings.py`:
   ```python
   my_new_setting: int = field(
       default_factory=lambda: _int_env("QA_AI_MY_NEW_SETTING", 42)
   )
   ```

2. Access it via `get_settings()`:
   ```python
   from qa_ai.config.settings import get_settings
   value = get_settings().my_new_setting
   ```

3. Document it in the env vars table in `README.md`.

### Supported env var types

| Helper | Use for |
|--------|---------|
| `_int_env(key, default)` | Integer settings |
| `_float_env(key, default)` | Float settings |
| `_bool_env(key, default)` | Boolean flags (accepts `true/1/yes` and `false/0/no`) |
| `os.environ.get(key, default)` | String settings |

### Never hardcode localhost URLs

Any URL that points to a local service (Ollama, the app under test, the API server) must be read from settings:

```python
# BAD
url = "http://localhost:11434/api/tags"

# GOOD
from qa_ai.config.settings import get_settings
url = get_settings().ollama_base_url + "/api/tags"
```
