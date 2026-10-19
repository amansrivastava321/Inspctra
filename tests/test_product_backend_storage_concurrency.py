"""ProductStorage shares one SQLite connection across request threads.

Reads must be atomic with respect to other threads: a row that exists must never
come back as ``None`` (surfacing as a spurious 404) or raise because another
thread was using the same connection at the same time.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from qa_ai.product_backend.storage import ProductStorage

NOW = "2026-01-01T00:00:00Z"


def _storage(tmp_path: Path) -> ProductStorage:
    storage = ProductStorage(str(tmp_path / "concurrency.db"))
    storage.create_project({"id": "project-1", "name": "P", "created_at": NOW, "updated_at": NOW})
    storage.create_validation_pack(
        {"id": "pack-1", "project_id": "project-1", "name": "K", "created_at": NOW, "updated_at": NOW}
    )
    return storage


def _hammer(workers: list[threading.Thread]) -> None:
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()


def test_concurrent_reads_never_miss_an_existing_row(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    deadline = time.monotonic() + 1.5
    misses: list[str] = []
    errors: list[str] = []

    def reader() -> None:
        while time.monotonic() < deadline:
            try:
                if storage.get_validation_pack("pack-1") is None:
                    misses.append("pack-1")
            except Exception as exc:  # noqa: BLE001 - any error is the failure being asserted
                errors.append(repr(exc))

    _hammer([threading.Thread(target=reader) for _ in range(6)])

    assert errors == []
    assert misses == []


def test_reads_survive_concurrent_snapshot_transactions(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    deadline = time.monotonic() + 1.5
    misses: list[str] = []
    errors: list[str] = []

    def reader() -> None:
        while time.monotonic() < deadline:
            try:
                if storage.get_validation_pack("pack-1") is None:
                    misses.append("pack-1")
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))

    def snapshotter() -> None:
        # BEGIN ... ROLLBACK on the shared connection, as the comparison endpoint does.
        while time.monotonic() < deadline:
            storage.load_run_comparison_snapshot("missing-a", "missing-b")

    _hammer(
        [threading.Thread(target=reader) for _ in range(6)]
        + [threading.Thread(target=snapshotter) for _ in range(2)]
    )

    assert errors == []
    assert misses == []


def test_write_results_expose_rowcount_and_lastrowid(tmp_path: Path) -> None:
    storage = _storage(tmp_path)

    assert storage.delete_validation_pack("pack-1") is True
    assert storage.delete_validation_pack("pack-1") is False
    assert storage.get_validation_pack("pack-1") is None
