from qa_ai.ai.model_usage_logger import ModelUsageLogger


def test_model_usage_logger_writes_artifacts(artifact_store):
    logger = ModelUsageLogger(artifact_store=artifact_store)
    logger.log(
        component="master_orchestration",
        model="nousresearch/hermes-3-llama-3.1-405b:free",
        provider="openrouter",
        latency_ms=100.0,
        fallback_used=False,
        fallback_reason="",
        privacy_mode="standard",
        success=True,
    )
    logger.flush(routing_mode="specialist_cloud_first")
    assert artifact_store.artifact_exists("model_usage_log")
    assert artifact_store.artifact_exists("model_routing_report")
