"""
reports.py - Report API + safe export

GET /api/reports              — list (filter by run_id)
GET /api/reports/{id}         — metadata
GET /api/reports/{id}/export  — stream report file content
"""
from __future__ import annotations

import json
import logging
import re
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse

from qa_ai.product_backend.artifact_index import ArtifactIndex, _guess_mime
from qa_ai.product_backend.dependencies import get_artifact_index, get_storage
from qa_ai.product_backend.models import ReportRecord, RunReportSummary
from qa_ai.product_backend.report_exporters import ReportExportError, RunReportExporter
from qa_ai.product_backend.storage import ProductStorage

logger = logging.getLogger(__name__)
router = APIRouter(tags=["reports"])


_DOWNLOAD_FORMATS = {
    "html": ("text/html; charset=utf-8", "html"),
    "pdf": ("application/pdf", "pdf"),
    "junit": ("application/xml; charset=utf-8", "junit.xml"),
    "sarif": ("application/json; charset=utf-8", "sarif.json"),
}


def _run_exporter(storage: ProductStorage, index: ArtifactIndex) -> RunReportExporter:
    return RunReportExporter(storage, index)


def _raise_export_error(exc: ReportExportError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _download_filename(run_id: str, extension: str) -> str:
    safe_run_id = re.sub(r"[^A-Za-z0-9._-]", "-", run_id)[:120] or "run"
    return f"inspectra-run-{safe_run_id}.{extension}"


@router.get("/runs/{run_id}/report/summary", response_model=RunReportSummary)
def get_run_report_summary(
    run_id: str,
    storage: ProductStorage = Depends(get_storage),
    index: ArtifactIndex = Depends(get_artifact_index),
) -> RunReportSummary:
    try:
        summary = _run_exporter(storage, index).summary(run_id)
    except ReportExportError as exc:
        _raise_export_error(exc)
    return RunReportSummary(**summary)


@router.get("/runs/{run_id}/report")
def download_run_report(
    run_id: str,
    format: Literal["html", "pdf", "junit", "sarif"] = Query(...),
    storage: ProductStorage = Depends(get_storage),
    index: ArtifactIndex = Depends(get_artifact_index),
) -> Response:
    exporter = _run_exporter(storage, index)
    try:
        if format == "html":
            content = exporter.export_html(run_id).encode("utf-8")
        elif format == "pdf":
            content = exporter.export_pdf(run_id)
        elif format == "junit":
            content = exporter.export_junit(run_id)
        else:
            content = json.dumps(
                exporter.export_sarif(run_id),
                indent=2,
                ensure_ascii=False,
            ).encode("utf-8")
    except ReportExportError as exc:
        _raise_export_error(exc)

    media_type, extension = _DOWNLOAD_FORMATS[format]
    return Response(
        content=content,
        headers={
            "Content-Type": media_type,
            "Content-Disposition": (
                f'attachment; filename="{_download_filename(run_id, extension)}"'
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/reports", response_model=List[ReportRecord])
def list_reports(
    run_id: Optional[str] = Query(default=None),
    storage: ProductStorage = Depends(get_storage),
) -> List[ReportRecord]:
    return [ReportRecord(**r) for r in storage.list_reports(run_id=run_id)]


@router.get("/reports/{report_id}", response_model=ReportRecord)
def get_report(
    report_id: str,
    storage: ProductStorage = Depends(get_storage),
) -> ReportRecord:
    row = storage.get_report(report_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return ReportRecord(**row)


@router.get("/reports/{report_id}/export")
def export_report(
    report_id: str,
    storage: ProductStorage = Depends(get_storage),
    index: ArtifactIndex = Depends(get_artifact_index),
) -> StreamingResponse:
    """
    Stream report file content safely.

    Path traversal prevention: same as evidence download —
    relative_path validated via ArtifactIndex._resolve_safe().
    """
    row = storage.get_report(report_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")

    relative_path: str = row.get("relative_path", "")
    if not relative_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No file path stored.")

    try:
        stream = index.stream_file(relative_path)
    except ValueError as exc:
        logger.error("export_report: path traversal attempt blocked: %s", exc)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk.")

    fmt = row.get("format", "json")
    mime = _guess_mime(row.get("name", f"report.{fmt}"))
    filename = row.get("name", f"report-{report_id}.{fmt}")

    return StreamingResponse(
        stream,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
