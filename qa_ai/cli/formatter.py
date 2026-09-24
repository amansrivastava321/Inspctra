"""
formatter.py - Rich-based CLI output formatter for QA-AI.

Renders audit results, doctor reports, and run summaries as human-readable
terminal output instead of raw JSON. Falls back to plain text if rich is
unavailable.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box
    _RICH = True
except ImportError:
    _RICH = False

_console = None


def _get_console() -> Any:
    global _console
    if _console is None and _RICH:
        from rich.console import Console
        _console = Console()
    return _console


# ── version banner ────────────────────────────────────────────────────────────

def print_version(version: str) -> None:
    if _RICH:
        c = _get_console()
        c.print(f"\n[bold cyan]Inspectra QA-AI[/bold cyan]  [dim]v{version}[/dim]\n")
    else:
        print(f"Inspectra QA-AI v{version}")


# ── init ───────────────────────────────────────────────────────────────────────

def print_init_result(result: Dict[str, Any]) -> None:
    if not _RICH:
        print(json.dumps(result, indent=2, default=str))
        return
    c = _get_console()
    status = result.get("status", "ok")
    color = "green" if status == "ok" else "red"
    c.print(f"\n[{color}]✓[/{color}] Project initialised — [bold]{result.get('project_dir', '.')}[/bold]")
    for item in result.get("created", []):
        c.print(f"  [dim]+[/dim] {item}")
    c.print()


# ── audit run summary ─────────────────────────────────────────────────────────

def print_audit_summary(result: Dict[str, Any]) -> None:
    if not _RICH:
        print(json.dumps(result, indent=2, default=str))
        return
    c = _get_console()
    status = result.get("status", "unknown")
    color = {"completed": "green", "ok": "green", "partial": "yellow",
             "failed": "red", "error": "red"}.get(status, "blue")

    # Header
    c.print()
    c.print(Panel(
        f"[bold]Audit Complete[/bold]  [{color}]{status.upper()}[/{color}]",
        border_style=color, expand=False,
    ))

    # Phases table
    phases = result.get("phases_executed", [])
    if phases:
        t = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
        t.add_column("Phase", style="cyan")
        t.add_column("Status")
        for phase in phases:
            t.add_row(str(phase), "[green]✓[/green]")
        c.print(t)

    # Stats row
    artifacts = result.get("artifacts_generated", [])
    c.print(f"  Artifacts: [cyan]{len(artifacts)}[/cyan]   "
            f"Target: [dim]{result.get('target_path', '-')}[/dim]   "
            f"Profile: [dim]{result.get('profile', '-')}[/dim]")

    # Warnings
    for w in result.get("warnings", []):
        c.print(f"  [yellow]⚠[/yellow]  {w}")

    # Errors
    for e in result.get("errors", []):
        c.print(f"  [red]✗[/red]  {e}")

    c.print()


# ── doctor report ─────────────────────────────────────────────────────────────

def print_doctor_report(result: Dict[str, Any]) -> None:
    if not _RICH:
        print(json.dumps(result, indent=2, default=str))
        return
    c = _get_console()
    status = result.get("status", "ok")
    color = "green" if status == "ok" else "yellow"

    c.print()
    c.print(Panel(
        f"[bold]Doctor Report[/bold]  [{color}]{status.upper()}[/{color}]",
        border_style=color, expand=False,
    ))

    checks = result.get("checks", result.get("tools", {}))
    if isinstance(checks, dict):
        t = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
        t.add_column("Check")
        t.add_column("Status")
        t.add_column("Detail", style="dim")
        for name, info in checks.items():
            if isinstance(info, dict):
                ok = info.get("available", info.get("ok", True))
                detail = str(info.get("version", info.get("path", info.get("message", ""))))
                icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
            else:
                icon = "[green]✓[/green]" if info else "[red]✗[/red]"
                detail = ""
            t.add_row(name, icon, detail)
        c.print(t)
    elif isinstance(checks, list):
        for item in checks:
            c.print(f"  [green]✓[/green] {item}")

    for w in result.get("warnings", []):
        c.print(f"  [yellow]⚠[/yellow]  {w}")
    c.print()


# ── generic fallback ──────────────────────────────────────────────────────────

def print_result(result: Dict[str, Any], command: str = "") -> None:
    """Pretty-print any result dict. Falls back to JSON for unknown shapes."""
    if not _RICH:
        print(json.dumps(result, indent=2, default=str))
        return
    c = _get_console()
    status = result.get("status", "")
    color = "green" if status in ("ok", "completed") else ("red" if status in ("failed", "error") else "blue")
    label = command.upper() if command else "RESULT"
    c.print()
    if status:
        c.print(f"[{color}]● {label}[/{color}]  status=[bold]{status}[/bold]")
    # Print key scalar fields, skip large nested ones
    for key, val in result.items():
        if key in ("status",):
            continue
        if isinstance(val, (str, int, float, bool)):
            c.print(f"  [dim]{key}:[/dim] {val}")
    c.print()


# ── dashboard launch notice ───────────────────────────────────────────────────

def print_dashboard_starting(host: str, port: int, artifacts_dir: str) -> None:
    if _RICH:
        c = _get_console()
        c.print()
        c.print(Panel(
            f"[bold cyan]Inspectra Dashboard[/bold cyan]\n"
            f"  [link=http://{host}:{port}]http://{host}:{port}[/link]\n"
            f"  Artifacts: [dim]{artifacts_dir}[/dim]\n"
            f"  [dim]Press Ctrl+C to stop[/dim]",
            border_style="cyan", expand=False,
        ))
        c.print()
    else:
        print(f"Dashboard starting at http://{host}:{port}  (artifacts: {artifacts_dir})")
