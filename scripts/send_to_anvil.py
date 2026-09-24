from integrations.corpus_client import InspectraCorpusClient
from integrations.corpus_connection import CorpusConnectionManager

manager = CorpusConnectionManager(
    app_name="inspectra",
    app_version="1.0.0",
    workspace_name="AI Engineering Workspace",
    capabilities=["EMIT_SIGNALS", "RECEIVE_SIGNALS", "RESPOND_CHECKPOINT"],
    permissions=["EMIT_SIGNALS", "RECEIVE_SIGNALS", "RESPOND_CHECKPOINT"],
)

status = manager.get_status()
if not status.connected:
    raise SystemExit(
        "Corpus is not approved yet. Open Settings > Integrations > Corpus and request connection first."
    )

client = InspectraCorpusClient(manager)
signal = client.send_interrupt(
    target="anvil",
    reason="Critical security issue found during auth.py pre-execution audit",
    severity="CRITICAL",
    evidence={
        "file": "auth.py",
        "finding": "Unsafe token validation risk",
        "risk_score": 9.4,
        "recommendation": "Block execution and reroute to security remediation",
    },
)

print("Signal sent to Anvil")
print({"signal_id": getattr(signal, "id", None), "type": "INTERRUPT"})
