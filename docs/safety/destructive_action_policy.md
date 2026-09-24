# Destructive Action Policy

QA-AI avoids destructive actions by default.

## Policy

1. no automatic destructive host/system commands in normal workflow paths
2. disruptive simulations are blocked or downgraded to safe simulation without explicit permission
3. environment plans mark side-effecting steps as permission-required

## Operational expectation

When destructive operations are technically possible, the system should produce a plan and require explicit user authorization before execution.

## Subprocess Execution Policy

All subprocess calls within the QA platform must go through `qa_ai.utils.safe_subprocess.run_safe()`.

### Rules

1. **No `shell=True`** — All commands must be passed as a list of strings. Use `shlex.split()` if you need to convert a string command.

2. **Allowlist enforcement** — The `_BLOCKED_EXECUTABLES` set in `safe_subprocess.py` defines executables that are always blocked (e.g., `rm`, `dd`, `shutdown`). The platform will raise `CommandBlockedError` if a blocked executable is requested.

3. **Environment sanitization** — `run_safe()` automatically strips sensitive environment variables (API keys, passwords, tokens) before passing the environment to the subprocess. Add patterns to `_STRIP_ENV_KEYS` or `_STRIP_ENV_SUFFIXES` to extend coverage.

4. **Working directory validation** — If `cwd` is specified, it must exist. `InvalidCwdError` is raised otherwise.

5. **Audit logging** — Every `run_safe()` invocation logs at INFO level with the command, cwd, and timeout.

### How to use

```python
from qa_ai.utils.safe_subprocess import run_safe, CommandBlockedError, SubprocessTimeoutError

try:
    result = run_safe(
        ["pytest", "tests/", "-q"],
        cwd="/path/to/project",
        timeout=120,
        capture_output=True,
        text=True,
    )
except CommandBlockedError as e:
    logger.error("Blocked command: %s", e)
except SubprocessTimeoutError as e:
    logger.error("Command timed out: %s", e)
```

### Adding new allowed commands

To allow a command that is currently blocked, remove it from `_BLOCKED_EXECUTABLES` in `qa_ai/utils/safe_subprocess.py`. Document the reason in a comment. All changes to this list require a security review.
