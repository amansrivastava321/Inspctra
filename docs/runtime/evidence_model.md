# Evidence Model

Evidence in QA-AI is represented as structured artifacts, not ad-hoc logs.

## Primary contracts

1. `EvidenceGraphArtifact` (`qa_ai.schemas.evidence_schema`)
2. execution/network trace artifacts (`qa_ai.schemas.runtime_schema`)
3. distributed/mobile evidence graph artifacts in their schema modules

## Evidence graph role

Evidence graphs link findings, traces, sessions, devices, anomalies, and workflow context so reporting and reasoning can reference concrete, traceable sources.

## Evidence-linked reasoning

AI reasoning modules (for example `EvidenceSynthesizer`, `RiskReasoner`) are required to cite deterministic references and follow a no invented evidence rule.

## Limitation note

Evidence density depends on whether live execution paths run in the current environment. Planning-only runs still emit structural artifacts, but may not include rich live telemetry.
