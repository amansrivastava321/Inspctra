"""Scripted stand-ins for platform tools, so the native engines can be tested on any OS."""
from __future__ import annotations

from typing import Any, Callable, List, Optional, Sequence, Tuple, Union

from qa_ai.native_execution.base import CommandResult, CommandRunner

Response = Union[CommandResult, Callable[[List[str]], CommandResult]]

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True


class FakeRunner(CommandRunner):
    """Answers commands by the first rule whose text appears in the joined command line."""

    def __init__(self, rules: Sequence[Tuple[str, Response]] = (), tools: Sequence[str] = ()) -> None:
        self.rules: List[Tuple[str, Response]] = list(rules)
        self.tools = set(tools)
        self.calls: List[List[str]] = []
        self.spawned: List[List[str]] = []
        self.processes: List[FakeProcess] = []
        self.clock = 0.0

    def which(self, name: str) -> Optional[str]:
        return f"/tools/{name}" if name in self.tools else None

    def run(self, args: Sequence[str], timeout: float = 60.0) -> CommandResult:
        args = [str(a) for a in args]
        self.calls.append(args)
        line = " ".join(args)
        for needle, response in self.rules:
            if needle in line:
                return response(args) if callable(response) else response
        return CommandResult(0, b"", b"")

    def spawn(self, args: Sequence[str]) -> Any:
        self.spawned.append([str(a) for a in args])
        process = FakeProcess()
        self.processes.append(process)
        return process

    def sleep(self, seconds: float) -> None:
        self.clock += seconds

    def now(self) -> float:
        return self.clock

    def ran(self, needle: str) -> bool:
        return any(needle in " ".join(call) for call in self.calls)


def ok(out: Union[str, bytes] = b"", err: Union[str, bytes] = b"") -> CommandResult:
    return CommandResult(0, out.encode() if isinstance(out, str) else out, err.encode() if isinstance(err, str) else err)


def fail(err: str = "boom", out: str = "") -> CommandResult:
    return CommandResult(1, out.encode(), err.encode())
