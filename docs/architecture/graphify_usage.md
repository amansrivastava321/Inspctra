# Graphify Usage

Graphify provides architecture-scale context for QA-AI planning and change impact analysis.

## Development rule

Before major edits, read:

1. `graphify-out/GRAPH_REPORT.md`
2. `graphify-out/graph.json`

Use them to identify high-centrality abstractions, community boundaries, and dependency hotspots.

## Rebuild rule

After code changes, rebuild Graphify with:

```bash
python -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```

Important: use `python`, not `python3`, in this environment.

## Practical use in QA-AI

1. Use God Nodes and communities to assess blast radius before refactors.
2. Feed Graphify summaries into reporting (`AuditSummaryBuilder`) and AI reasoning context (`ReasoningContextBuilder`).
3. Treat Graphify as supporting evidence, not as a replacement for contract/runtime validation.
