"""On-demand run report exporters.

All formats share one persisted run/evidence context. Exports are never stored in
SQLite or on disk, and artifact reads remain confined by :class:`ArtifactIndex`.
"""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, Iterable, List, Mapping, Optional
from xml.etree import ElementTree as ET

from jinja2 import Environment
from markupsafe import Markup
from PIL import Image

from qa_ai.product_backend.artifact_index import ArtifactIndex
from qa_ai.product_backend.storage import ProductStorage


TERMINAL_RUN_STATUSES = frozenset({"completed", "failed", "cancelled"})
REPORT_FORMATS = ["html", "pdf", "junit", "sarif"]
SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/"
    "Schemata/sarif-schema-2.1.0.json"
)


class ReportExportError(RuntimeError):
    """An exporter failure that maps directly to an HTTP response."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


_HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Inspectra run {{ report.run_id }}</title>
  <style>
    :root { color-scheme: dark light; --bg:#0b0d12; --panel:#151923; --panel2:#1b2130; --text:#eef1f7; --muted:#9aa4b5; --border:#2a3447; --accent:#7c9cff; --pass:#45cf8a; --fail:#ff6b75; --warn:#f2b84b; --code:#0a0c11; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font:14px/1.55 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    main { max-width:1120px; margin:0 auto; padding:40px 28px 64px; }
    h1,h2,h3,p { margin-top:0; }
    h1 { font-size:30px; margin-bottom:8px; }
    h2 { font-size:20px; }
    .eyebrow { color:var(--accent); text-transform:uppercase; letter-spacing:.12em; font-size:11px; font-weight:700; }
    .muted { color:var(--muted); }
    .summary,.step { background:var(--panel); border:1px solid var(--border); border-radius:14px; padding:24px; margin:18px 0; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; }
    .metric { padding:13px 14px; background:var(--panel2); border:1px solid var(--border); border-radius:9px; }
    .metric > span { display:block; color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:.08em; }
    .metric strong { display:block; margin-top:4px; overflow-wrap:anywhere; }
    .step-head { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; }
    .badges { display:flex; flex-wrap:wrap; gap:7px; justify-content:flex-end; }
    .badge { display:inline-flex; align-items:center; border:1px solid var(--border); border-radius:999px; padding:3px 9px; font-size:11px; font-weight:700; white-space:nowrap; }
    .badge-pass { color:var(--pass); } .badge-failed,.badge-error { color:var(--fail); } .badge-warning { color:var(--warn); }
    .provenance::before { content:""; width:6px; height:6px; margin-right:6px; border-radius:50%; background:currentColor; }
    .detail-grid { width:calc(100% + 12px); margin:6px -6px 0; border-collapse:separate; border-spacing:6px; table-layout:fixed; }
    .detail { background:var(--panel2); border-radius:9px; padding:12px 14px; min-width:0; }
    .detail .label { color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:.08em; }
    .detail pre { margin:6px 0 0; }
    .detail pre,.error,details pre { white-space:pre-wrap; overflow-wrap:anywhere; }
    .error { margin-top:14px; border-left:3px solid var(--fail); background:rgba(255,107,117,.09); padding:12px 14px; color:#ffadb3; }
    figure { margin:18px 0 0; }
    img { display:block; max-width:100%; max-height:720px; object-fit:contain; border:1px solid var(--border); border-radius:10px; background:#050609; }
    figcaption { margin-top:7px; color:var(--muted); font-size:11px; }
    details { margin-top:12px; border:1px solid var(--border); border-radius:9px; padding:10px 12px; background:var(--panel2); }
    summary { cursor:pointer; font-weight:650; }
    details pre { margin:10px 0 0; padding:12px; border-radius:7px; background:var(--code); color:#d9e2f2; font:11px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    footer { margin-top:34px; padding-top:18px; border-top:1px solid var(--border); color:var(--muted); font-size:11px; text-align:center; }
    @media (prefers-color-scheme: light) {
      :root { --bg:#f5f7fb; --panel:#fff; --panel2:#f1f4f9; --text:#182033; --muted:#657087; --border:#d8deea; --accent:#375bd2; --pass:#16754a; --fail:#b72836; --warn:#8a5b00; --code:#eef1f6; }
      .error { color:#9c2330; }
    }
    @page { size:A4; margin:20mm 16mm 18mm; @top-center { content:{{ report.print_header_css }}; color:#5e6675; font-size:9pt; border-bottom:1px solid #d8dce4; } @bottom-left { content:{{ report.print_footer_css }}; color:#657087; font-size:9pt; } @bottom-right { content:"Page " counter(page) " of " counter(pages); color:#657087; font-size:9pt; } }
    @media print {
      :root { --bg:#fff; --panel:#fff; --panel2:#f5f6f8; --text:#161a23; --muted:#5e6675; --border:#d8dce4; --accent:#304fb4; --pass:#16754a; --fail:#a52230; --warn:#805600; --code:#f1f2f5; }
      body { background:#fff; }
      main { max-width:none; padding:0; }
      .summary,.step { box-shadow:none; }
      .step { break-before:page; border:0; border-radius:0; padding:0; background:transparent; }
      .detail { break-inside:avoid; }
      details { break-inside:avoid; }
      details > * { display:block; }
      details pre { color:#202533; }
      .error { color:var(--fail); }
      footer { display:none; }
    }
  </style>
</head>
<body>
  <main>
    <div class="eyebrow">Inspectra run report</div>
    <h1>{{ report.pack_name }}</h1>
    <p class="muted">{{ report.app_name }} · Run {{ report.run_id }}</p>
    <section class="summary">
      <div class="grid">
        <div class="metric"><span>Status</span><strong>{{ report.status|upper }}</strong></div>
        <div class="metric"><span>Provenance</span><strong><span class="badge provenance" aria-label="Overall provenance: {{ report.provenance }}">{{ report.provenance }}</span></strong></div>
        <div class="metric"><span>Started</span><strong>{{ report.started_at or "Unavailable" }}</strong></div>
        <div class="metric"><span>Completed</span><strong>{{ report.completed_at or "Unavailable" }}</strong></div>
        <div class="metric"><span>Duration</span><strong>{{ report.duration_label }}</strong></div>
        <div class="metric"><span>Steps</span><strong>{{ report.steps_total }} total · {{ report.steps_passed }} passed · {{ report.steps_failed }} failed · {{ report.steps_error }} errors</strong></div>
      </div>
    </section>
    {% for step in report.steps %}
    <section class="step" id="step-{{ step.index }}">
      <div class="step-head">
        <div><div class="eyebrow">Step {{ step.index }}</div><h2>{{ step.name }}</h2><div class="muted">{{ step.action_type }}</div></div>
        <div class="badges"><span class="badge badge-{{ step.status }}">{{ step.status|upper }}</span><span class="badge provenance">{{ step.provenance }}</span></div>
      </div>
      <table class="detail-grid"><tbody>
        <tr>
          <td class="detail"><div class="label">Duration</div><pre>{{ step.duration_label }}</pre></td>
          <td class="detail"><div class="label">Expected</div><pre>{{ step.expected or "Not recorded" }}</pre></td>
        </tr>
        <tr>
          <td class="detail"><div class="label">Actual</div><pre>{{ step.actual or "Not recorded" }}</pre></td>
          <td class="detail"><div class="label">Step ID</div><pre>{{ step.id }}</pre></td>
        </tr>
      </tbody></table>
      {% if step.error %}<div class="error"><strong>Error details</strong><br>{{ step.error }}</div>{% endif %}
      {% for screenshot in step.screenshots %}<figure><img src="{{ screenshot.data_uri }}" alt="{{ screenshot.name }}"><figcaption>{{ screenshot.name }} · {{ screenshot.provenance }}</figcaption></figure>{% endfor %}
      {% for item in step.text_evidence %}<details><summary>{{ item.label }} · {{ item.provenance }}</summary><pre>{{ item.content }}</pre></details>{% endfor %}
    </section>
    {% endfor %}
    <footer>Generated by Inspectra · {{ report.generated_at }}</footer>
  </main>
</body>
</html>"""


def _parse_time(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _seconds_between(start: Any, end: Any) -> Optional[float]:
    start_dt = _parse_time(start)
    end_dt = _parse_time(end)
    if start_dt is None or end_dt is None:
        return None
    return max(0.0, round((end_dt - start_dt).total_seconds(), 3))


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, ensure_ascii=False, default=str)
    rendered = str(value).strip()
    return rendered or None


def _first(record: Mapping[str, Any], fields: Iterable[str]) -> Optional[str]:
    for field in fields:
        rendered = _text(record.get(field))
        if rendered is not None:
            return rendered
    return None


def _step_duration(step: Mapping[str, Any]) -> Optional[float]:
    for field in ("duration_seconds", "load_time_seconds"):
        try:
            value = float(step[field])
        except (KeyError, TypeError, ValueError):
            continue
        return max(0.0, round(value, 3))
    for field in ("duration_ms", "response_time_ms"):
        try:
            value = float(step[field]) / 1000.0
        except (KeyError, TypeError, ValueError):
            continue
        return max(0.0, round(value, 3))
    return _seconds_between(step.get("started_at"), step.get("completed_at"))


def _duration_label(value: Optional[float]) -> str:
    return "Unavailable" if value is None else f"{value:.3f}s"


def _step_name(step: Mapping[str, Any], index: int) -> str:
    return _first(step, ("name", "description", "title", "action_type")) or f"Step {index}"


def _step_error(step: Mapping[str, Any]) -> Optional[str]:
    return _first(step, ("failure_reason", "error", "notes", "message"))


def _rule_id(step: Mapping[str, Any]) -> str:
    base = _first(step, ("action_type", "name", "description")) or "inspectra-step"
    slug = re.sub(r"[^a-z0-9]+", "-", base.casefold()).strip("-")
    return slug or "inspectra-step"


def _css_string(value: Any) -> Markup:
    """Return a quoted CSS string that cannot terminate the style element."""
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("\r", " ").replace("\n", " ")
    escaped = escaped.replace("<", "\\3C ").replace(">", "\\3E ")
    return Markup(f'"{escaped}"')


class RunReportExporter:
    """Build on-demand reports from one canonical persisted run context."""

    def __init__(self, storage: ProductStorage, artifact_index: ArtifactIndex) -> None:
        self.storage = storage
        self.artifact_index = artifact_index
        self._jinja = Environment(autoescape=True)
        self._template = self._jinja.from_string(_HTML_TEMPLATE)

    def build_context(self, run_id: str) -> Dict[str, Any]:
        run = self.storage.get_run(run_id)
        if run is None:
            raise ReportExportError(404, "Run not found.")
        status = str(run.get("status") or "").casefold()
        if status not in TERMINAL_RUN_STATUSES:
            raise ReportExportError(409, "Report not available — run is still in progress.")

        pack = self.storage.get_validation_pack(str(run.get("pack_id") or "")) or {}
        app = self.storage.get_app_target(str(run.get("app_target_id") or "")) or {}
        evidence = self.storage.list_evidence(run_id=run_id)
        by_step: Dict[str, List[Dict[str, Any]]] = {}
        for item in evidence:
            step_id = item.get("step_id")
            if step_id:
                by_step.setdefault(str(step_id), []).append(item)

        normalized_steps: List[Dict[str, Any]] = []
        passed = failed = errors = 0
        failure_reasons: List[str] = []
        for index, raw_step in enumerate(run.get("step_results") or [], start=1):
            step = dict(raw_step)
            step_id = str(step.get("step_id") or step.get("id") or f"step-{index}")
            step_status = str(step.get("status") or step.get("verdict") or "unknown").casefold()
            if step_status in {"passed", "pass"}:
                passed += 1
            elif step_status == "error":
                errors += 1
            elif step_status in {"failed", "fail", "blocked", "inconclusive"}:
                failed += 1
            error = _step_error(step)
            if step_status in {"failed", "fail", "blocked", "inconclusive", "error"} and error:
                if error not in failure_reasons:
                    failure_reasons.append(error)

            screenshots: List[Dict[str, Any]] = []
            text_evidence: List[Dict[str, Any]] = []
            console_output: List[str] = []
            for item in by_step.get(step_id, []):
                kind = str(item.get("type") or item.get("evidence_type") or "").casefold()
                mime = str(item.get("mime_type") or "application/octet-stream").casefold()
                provenance = str(item.get("provenance") or "UNAVAILABLE")
                if "screenshot" in kind or mime.startswith("image/"):
                    data_uri = self._image_data_uri(item)
                    if data_uri:
                        screenshots.append({
                            "name": item.get("name") or "Screenshot",
                            "data_uri": data_uri,
                            "provenance": provenance,
                        })
                    continue
                if kind not in {"console", "api_request", "api_response", "request", "response"}:
                    continue
                content = self._evidence_text(item)
                label = {
                    "console": "Console log",
                    "api_request": "API request",
                    "request": "API request",
                    "api_response": "API response",
                    "response": "API response",
                }.get(kind, item.get("name") or "Evidence")
                text_evidence.append({"label": label, "content": content, "provenance": provenance})
                if kind == "console":
                    console_output.append(content)

            duration = _step_duration(step)
            normalized_steps.append({
                "index": index,
                "id": step_id,
                "name": _step_name(step, index),
                "action_type": str(step.get("action_type") or "unknown"),
                "status": step_status,
                "duration_seconds": duration,
                "duration_label": _duration_label(duration),
                "expected": _first(step, ("expected_result", "expected", "expected_value", "expected_status")),
                "actual": _first(step, ("actual_result", "actual", "result", "status_code")),
                "error": error,
                "provenance": str(step.get("provenance") or "UNAVAILABLE"),
                "screenshots": screenshots,
                "text_evidence": text_evidence,
                "console_output": "\n\n".join(console_output),
                "rule_id": _rule_id(step),
            })

        duration = _seconds_between(run.get("started_at"), run.get("completed_at"))
        context = {
            "run_id": str(run["id"]),
            "pack_id": str(run.get("pack_id") or ""),
            "pack_name": str(pack.get("name") or run.get("pack_name") or "Validation pack"),
            "app_id": str(run.get("app_target_id") or ""),
            "app_name": str(app.get("name") or run.get("app_name") or "App"),
            "app_url": app.get("base_url"),
            "status": status,
            "started_at": run.get("started_at"),
            "completed_at": run.get("completed_at"),
            "duration_seconds": duration,
            "duration_label": _duration_label(duration),
            "steps": normalized_steps,
            "steps_total": len(normalized_steps),
            "steps_passed": passed,
            "steps_failed": failed,
            "steps_error": errors,
            "failure_reasons": failure_reasons,
            "provenance": str(run.get("provenance") or "UNAVAILABLE"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        context["print_header_css"] = _css_string(
            f"{context['pack_name']} · {context['app_name']} · {status.upper()}"
        )
        context["print_footer_css"] = _css_string(
            f"Generated by Inspectra · {context['generated_at']}"
        )
        return context

    def summary(self, run_id: str) -> Dict[str, Any]:
        context = self.build_context(run_id)
        return {
            "run_id": context["run_id"],
            "pack_name": context["pack_name"],
            "app_name": context["app_name"],
            "status": context["status"],
            "started_at": context["started_at"],
            "completed_at": context["completed_at"],
            "duration_seconds": context["duration_seconds"],
            "steps_total": context["steps_total"],
            "steps_passed": context["steps_passed"],
            "steps_failed": context["steps_failed"],
            "steps_error": context["steps_error"],
            "failure_reasons": context["failure_reasons"],
            "provenance": context["provenance"],
            "formats_available": list(REPORT_FORMATS),
        }

    def export_html(self, run_id: str) -> str:
        return self._template.render(report=self.build_context(run_id))

    def export_pdf(self, run_id: str) -> bytes:
        try:
            from weasyprint import HTML
            return HTML(string=self.export_html(run_id)).write_pdf()
        except (ImportError, OSError) as exc:  # pragma: no cover - host dependency failure
            raise ReportExportError(
                500,
                "PDF export is unavailable. Install WeasyPrint and its native Pango libraries.",
            ) from exc

    def export_junit(self, run_id: str) -> bytes:
        context = self.build_context(run_id)
        suite = ET.Element(
            "testsuite",
            {
                "name": context["pack_name"],
                "timestamp": str(context["started_at"] or context["generated_at"]),
                "time": f"{(context['duration_seconds'] or 0):.3f}",
                "tests": str(context["steps_total"]),
                "failures": str(context["steps_failed"]),
                "errors": str(context["steps_error"]),
            },
        )
        for step in context["steps"]:
            case = ET.SubElement(
                suite,
                "testcase",
                {
                    "classname": context["app_name"],
                    "name": step["name"],
                    "time": f"{(step['duration_seconds'] or 0):.3f}",
                },
            )
            if step["status"] == "error":
                node = ET.SubElement(
                    case,
                    "error",
                    {"message": step["error"] or "Execution error", "type": "ExecutionError"},
                )
                node.text = step["error"] or "Execution error"
            elif step["status"] in {"failed", "fail", "blocked", "inconclusive"}:
                node = ET.SubElement(
                    case,
                    "failure",
                    {"message": step["error"] or "Step failed", "type": "AssertionFailure"},
                )
                node.text = step["error"] or "Step failed"
            if step["console_output"]:
                ET.SubElement(case, "system-out").text = step["console_output"]
        return ET.tostring(suite, encoding="utf-8", xml_declaration=True)

    def export_sarif(self, run_id: str) -> Dict[str, Any]:
        context = self.build_context(run_id)
        reportable = [
            step
            for step in context["steps"]
            if step["status"] in {"failed", "fail", "blocked", "inconclusive", "error", "warning", "warn"}
        ]
        rules: Dict[str, Dict[str, Any]] = {}
        results: List[Dict[str, Any]] = []
        for step in reportable:
            rule_id = step["rule_id"]
            rules.setdefault(rule_id, {"id": rule_id, "name": step["name"], "shortDescription": {"text": step["name"]}})
            result: Dict[str, Any] = {
                "ruleId": rule_id,
                "level": "warning" if step["status"] in {"warning", "warn", "inconclusive"} else "error",
                "message": {"text": step["error"] or f"{step['name']} did not pass."},
            }
            if context.get("app_url"):
                result["locations"] = [{
                    "physicalLocation": {"artifactLocation": {"uri": context["app_url"]}}
                }]
            results.append(result)
        return {
            "$schema": SARIF_SCHEMA,
            "version": "2.1.0",
            "runs": [{
                "tool": {"driver": {"name": "Inspectra", "rules": list(rules.values())}},
                "results": results,
            }],
        }

    def _read_artifact(self, evidence: Mapping[str, Any]) -> bytes:
        relative_path = str(evidence.get("relative_path") or "")
        if not relative_path:
            raise FileNotFoundError("Evidence path is missing")
        return b"".join(self.artifact_index.stream_file(relative_path))

    def _evidence_text(self, evidence: Mapping[str, Any]) -> str:
        try:
            raw = self._read_artifact(evidence)
        except (FileNotFoundError, ValueError, OSError):
            return "Evidence unavailable."
        decoded = raw.decode("utf-8", errors="replace")
        try:
            return json.dumps(json.loads(decoded), indent=2, ensure_ascii=False, default=str)
        except json.JSONDecodeError:
            return decoded

    def _image_data_uri(self, evidence: Mapping[str, Any]) -> Optional[str]:
        try:
            raw = self._read_artifact(evidence)
            image = Image.open(BytesIO(raw))
            image.load()
            image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            output = BytesIO()
            has_alpha = image.mode in {"RGBA", "LA"} or (
                image.mode == "P" and "transparency" in image.info
            )
            if has_alpha:
                image.save(output, format="PNG", optimize=True)
                mime = "image/png"
            else:
                image.convert("RGB").save(output, format="JPEG", quality=82, optimize=True)
                mime = "image/jpeg"
            encoded = base64.b64encode(output.getvalue()).decode("ascii")
            return f"data:{mime};base64,{encoded}"
        except (FileNotFoundError, ValueError, OSError, Image.UnidentifiedImageError):
            return None
