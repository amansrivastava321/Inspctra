## graphify

`graphify-out/` is an optional, generated code knowledge graph. It is gitignored, so it does not
exist in a fresh checkout. Check before relying on it.

Rules:
- If `graphify-out/GRAPH_REPORT.md` exists, read it before answering architecture or codebase questions (god nodes and community structure)
- If `graphify-out/wiki/index.md` exists, navigate it instead of reading raw files
- If the `graphify` Python package is importable (`python -c "import graphify"` succeeds), then after modifying code files in this session run `python -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current. If it is not importable, skip this step. There is no package named `graphify` on PyPI, so do not try to install one by guessing.
- The graph is supporting context, never the source of truth: confirm anything important against the code.
