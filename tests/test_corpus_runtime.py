from types import SimpleNamespace
from unittest.mock import patch

from integrations.corpus_runtime import CorpusRuntime


def test_runtime_detection_success() -> None:
    with patch("integrations.corpus_runtime.RuntimeDiscovery") as discovery_type:
        discovery_type.return_value.find_or_start_runtime.return_value = SimpleNamespace(
            base_url="http://corpus.local",
            source="scan",
        )
        runtime = CorpusRuntime(candidate_ports=[8123])
        with patch.object(runtime, "validate_runtime_health", return_value=True):
            status = runtime.detect_local_runtime()

    assert status.detected is True
    assert status.healthy is True
    assert status.base_url == "http://corpus.local"
    discovery_type.return_value.find_or_start_runtime.assert_called_once_with(
        start_if_missing=False,
        candidate_ports=[8123],
    )


def test_runtime_detection_failure() -> None:
    with patch("integrations.corpus_runtime.RuntimeDiscovery") as discovery_type:
        discovery_type.return_value.find_or_start_runtime.return_value = None
        runtime = CorpusRuntime(candidate_ports=[8123])
        status = runtime.detect_local_runtime()

    assert status.detected is False
    assert status.healthy is False
