# Evidence-Linked Reasoning

Reasoning outputs must remain tied to concrete artifacts.

## No invented evidence rule

Reasoners should only cite deterministic artifact data and explicit references. They must not fabricate supporting evidence.

## Current implementation signals

1. `EvidenceSynthesizer` emits deterministic references and explicit safety summary (`no_invented_evidence`).
2. `ReasoningContextBuilder` includes artifact references and Graphify context snapshots.
3. Semantic RCA/risk/scenario/fix outputs include deterministic reference fields in their payloads.

## Artifact linkage expectation

For each conclusion/recommendation:

1. include cited artifact filenames/paths
2. include rationale and confidence
3. preserve provenance through `artifact_metadata` fields
