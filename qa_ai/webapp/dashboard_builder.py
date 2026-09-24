"""
dashboard_builder.py - Builds the HTML string for the root dashboard page.

Reads from ArtifactAPI (which reads from ArtifactStore) and renders a
single-page HTML dashboard. No business logic — purely presentational.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from qa_ai.webapp.artifact_api import ArtifactAPI


class DashboardBuilder:
    """Generate the HTML dashboard from current artifacts."""

    def __init__(self, api: ArtifactAPI):
        self.api = api

    def build(self) -> str:
        summary = self.api.get_summary() or {}
        findings = self.api.get_findings()
        stats = self.api.get_store_stats()
        risk = self.api.get_risk() or {}

        status = summary.get("status", "—")
        target = summary.get("target_path", summary.get("target", "—"))
        profile = summary.get("profile", "—")
        phases = summary.get("phases_executed", [])
        artifacts = stats.get("artifact_count", 0)
        evidence = stats.get("evidence_count", 0)

        # Severity counts
        sev_counts: Dict[str, int] = {}
        for f in findings:
            sev = str(f.get("severity", "unknown")).lower()
            sev_counts[sev] = sev_counts.get(sev, 0) + 1

        status_color = {
            "completed": "#22c55e", "ok": "#22c55e",
            "partial": "#f59e0b",
            "failed": "#ef4444", "error": "#ef4444",
        }.get(status, "#64748b")

        findings_rows = "\n".join(
            f"<tr>"
            f"<td>{_esc(str(f.get('id',''))[:8])}</td>"
            f"<td>{_esc(str(f.get('title',''))[:80])}</td>"
            f"<td><span class='sev sev-{_sev(f)}'>{_esc(str(f.get('severity','?')).upper())}</span></td>"
            f"<td>{_esc(str(f.get('category','')))}</td>"
            f"<td>{'✓' if f.get('evidence') else '—'}</td>"
            f"</tr>"
            for f in findings[:50]
        ) or "<tr><td colspan='5' style='color:#94a3b8'>No findings in current artifacts.</td></tr>"

        phases_html = " ".join(
            f"<span class='tag'>{_esc(str(p))}</span>" for p in phases[:20]
        ) or "<span style='color:#94a3b8'>—</span>"

        artifact_list = "\n".join(
            f"<li><a href='/api/artifacts/{_esc(a['name'])}'>{_esc(a['name'])}</a></li>"
            for a in self.api.list_artifacts()[:40]
        )

        risk_score = risk.get("overall_score", risk.get("score", "—"))
        risk_level = str(risk.get("risk_level", risk.get("level", "—")))

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inspectra — Dashboard</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:system-ui,-apple-system,sans-serif; background:#0f172a; color:#e2e8f0;
        font-size:14px; line-height:1.5; }}
header {{ background:#1e293b; border-bottom:1px solid #334155; padding:1rem 2rem;
          display:flex; align-items:center; gap:1rem; }}
header h1 {{ font-size:1.2rem; font-weight:700; color:#fff; }}
header .badge {{ background:#0ea5e9; color:#fff; font-size:0.7rem; font-weight:700;
                 padding:0.1rem 0.5rem; border-radius:4px; letter-spacing:.05em; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr));
         gap:1rem; padding:2rem; }}
.card {{ background:#1e293b; border:1px solid #334155; border-radius:8px;
         padding:1rem 1.25rem; }}
.card-label {{ font-size:0.7rem; color:#64748b; text-transform:uppercase;
               letter-spacing:.06em; margin-bottom:.3rem; }}
.card-value {{ font-size:1.6rem; font-weight:700; }}
section {{ padding:0 2rem 2rem; }}
h2 {{ font-size:1rem; font-weight:600; color:#94a3b8; margin-bottom:.75rem;
      text-transform:uppercase; letter-spacing:.05em; }}
table {{ width:100%; border-collapse:collapse; background:#1e293b;
         border:1px solid #334155; border-radius:8px; overflow:hidden; }}
th {{ background:#0f172a; padding:.5rem .75rem; text-align:left; font-size:0.75rem;
      font-weight:600; color:#64748b; border-bottom:1px solid #334155; }}
td {{ padding:.45rem .75rem; border-bottom:1px solid #1e293b; font-size:.85rem; }}
tr:last-child td {{ border-bottom:none; }}
.sev {{ display:inline-block; padding:.1rem .4rem; border-radius:3px;
        font-size:.7rem; font-weight:700; }}
.sev-critical {{ background:#450a0a; color:#fca5a5; }}
.sev-high {{ background:#431407; color:#fed7aa; }}
.sev-medium {{ background:#422006; color:#fef08a; }}
.sev-low {{ background:#052e16; color:#86efac; }}
.sev-info, .sev-unknown {{ background:#1e293b; color:#94a3b8; }}
.tag {{ display:inline-block; background:#0f172a; border:1px solid #334155;
        border-radius:4px; padding:.1rem .4rem; font-size:.75rem; color:#94a3b8;
        margin:.1rem; }}
ul {{ list-style:none; padding-left:0; }}
li {{ padding:.2rem 0; border-bottom:1px solid #1e293b; font-size:.85rem; }}
li a {{ color:#38bdf8; text-decoration:none; }}
li a:hover {{ color:#7dd3fc; }}
nav {{ display:flex; gap:1rem; margin-left:auto; }}
nav a {{ color:#94a3b8; text-decoration:none; font-size:.85rem; }}
nav a:hover {{ color:#e2e8f0; }}
</style>
</head>
<body>
<header>
  <h1>Inspectra</h1>
  <span class="badge">LOCAL</span>
  <nav>
    <a href="/">Dashboard</a>
    <a href="/settings/integrations/corpus">Corpus Integration</a>
    <a href="/api/findings">Findings JSON</a>
    <a href="/api/artifacts">Artifacts</a>
    <a href="/health">Health</a>
  </nav>
</header>

<div class="grid">
  <div class="card">
    <div class="card-label">Status</div>
    <div class="card-value" style="color:{status_color}">{_esc(status.upper())}</div>
  </div>
  <div class="card">
    <div class="card-label">Findings</div>
    <div class="card-value" style="color:#f87171">{len(findings)}</div>
  </div>
  <div class="card">
    <div class="card-label">Artifacts</div>
    <div class="card-value" style="color:#38bdf8">{artifacts}</div>
  </div>
  <div class="card">
    <div class="card-label">Evidence</div>
    <div class="card-value" style="color:#a78bfa">{evidence}</div>
  </div>
  <div class="card">
    <div class="card-label">Risk Level</div>
    <div class="card-value" style="color:#fb923c">{_esc(str(risk_level))}</div>
  </div>
  <div class="card">
    <div class="card-label">Risk Score</div>
    <div class="card-value">{risk_score}</div>
  </div>
  <div class="card">
    <div class="card-label">Profile</div>
    <div class="card-value" style="font-size:1rem;padding-top:.3rem">{_esc(str(profile))}</div>
  </div>
  <div class="card">
    <div class="card-label">Target</div>
    <div class="card-value" style="font-size:.8rem;word-break:break-all">{_esc(str(target)[-40:])}</div>
  </div>
</div>

<section>
  <h2>Phases Executed</h2>
  <div style="padding:.5rem 0">{phases_html}</div>
</section>

<section>
  <h2>Findings ({len(findings)})</h2>
  <table>
    <thead><tr><th>ID</th><th>Title</th><th>Severity</th><th>Category</th><th>Evidence</th></tr></thead>
    <tbody>{findings_rows}</tbody>
  </table>
</section>

<section>
  <h2>Artifacts</h2>
  <ul>{artifact_list}</ul>
</section>

<footer style="padding:1rem 2rem;color:#334155;font-size:.75rem">
  Inspectra QA-AI &mdash; read-only local dashboard &mdash; {stats.get('artifacts_dir','')}
</footer>
</body>
</html>"""


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _sev(f: dict) -> str:
    return str(f.get("severity", "unknown")).lower()
