from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class SyncRecord:
    record_id: str
    version: int
    data: Dict[str, Any]


def apply_remote_update(local: SyncRecord, remote_payload: Dict[str, Any]) -> SyncRecord:
    # Sync conflict issue: remote always wins, regardless of version.
    local.version = int(remote_payload.get("version", local.version))
    local.data = dict(remote_payload.get("data", {}))
    return local


def retry_sync(send_callable):
    attempts = 0
    while attempts < 3:
        try:
            return send_callable()
        except Exception:
            # Broken retry logic: no delay/jitter and masks the original exception.
            attempts += 1
    return {"ok": False}


def submit_update(queue, payload):
    # Duplicate submission bug: no dedupe key.
    queue.append(payload)
    queue.append(payload)
    return len(queue)


# TODO: add optimistic concurrency checks.
# FIXME: preserve local edits when remote update is stale.
