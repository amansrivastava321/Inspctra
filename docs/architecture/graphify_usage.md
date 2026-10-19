# Graphify Usage

Graphify provides architecture-scale context for QA-AI planning and change impact analysis.

## Availability

`graphify-out/` is generated and gitignored, so it does not exist in a fresh checkout. Everything below
applies only when it has been built; QA-AI works without it (reports and reasoning simply have no graph
summary). `qa_ai doctor` lists the graph outputs as a check and reports a degraded environment when they
are absent.

## Development rule

When the graph exists, read these before major edits:

1. `graphify-out/GRAPH_REPORT.md`
2. `graphify-out/graph.json`

Use them to identify high-centrality abstractions, community boundaries, and dependency hotspots.

## Rebuild rule

Rebuilding needs the `graphify` Python package to be importable (`python -c "import graphify"`). If it is
not, skip rebuilding. There is no PyPI package named `graphify`, so do not install one by guessing.

After code changes, when it is importable:

```bash
python -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```

Use `python`, not `python3`, in the environment this project was developed in.

## Practical use in QA-AI

1. Use God Nodes and communities to assess blast radius before refactors.
2. Feed Graphify summaries into reporting (`AuditSummaryBuilder`) and AI reasoning context (`ReasoningContextBuilder`).
3. Treat Graphify as supporting evidence, not as a replacement for contract/runtime validation.
