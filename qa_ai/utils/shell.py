"""
shell.py - Shell command execution utilities.
Provides subprocess wrappers with timeout, output capture, and error handling.
"""

from typing import Optional, List, Tuple
import subprocess
import logging
import shlex

logger = logging.getLogger(__name__)


def run_command(
    cmd: List[str],
    timeout: int = 30,
    cwd: Optional[str] = None,
    capture_output: bool = True,
    check: bool = False,
) -> Tuple[int, str, str]:
    """
    Run a shell command with timeout and output capture.

    Args:
        cmd: Command and arguments as a list
        timeout: Timeout in seconds
        cwd: Working directory
        capture_output: Whether to capture stdout/stderr
        check: If True, raise on non-zero exit

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        if check and result.returncode != 0:
            logger.error(
                f"Command failed (rc={result.returncode}): "
                f"{' '.join(shlex.quote(c) for c in cmd)}\n{result.stderr}"
            )
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s: {' '.join(cmd)}")
        return -1, "", f"Timeout after {timeout}s"
    except FileNotFoundError:
        logger.error(f"Command not found: {cmd[0]}")
        return -1, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        logger.error(f"Command error: {e}")
        return -1, "", str(e)


def run_simple(cmd: List[str], timeout: int = 10) -> Optional[str]:
    """Run a command and return stripped stdout, or None on failure."""
    rc, stdout, _ = run_command(cmd, timeout=timeout)
    return stdout.strip() if rc == 0 and stdout else None


def which(name: str) -> Optional[str]:
    """Check if a command exists in PATH. Returns path or None."""
    import shutil as _shutil
    return _shutil.which(name)
