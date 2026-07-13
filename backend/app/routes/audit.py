from datetime import datetime, timedelta
import csv
import io

from fastapi import APIRouter, Request
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.templating import Jinja2Templates

from app.database.database import SessionLocal
from app.models.event_log import EventLog
from app.services.access_service import require_admin
from app.services.time_service import (
    format_local_time,
    register_time_filters,
)


router = APIRouter()
templates = register_time_filters(
    Jinja2Templates(directory="app/templates")
)


def build_audit_query(
    db,
    search: str = "",
    result: str = "",
    date_from: str = "",
    date_to: str = "",
):
    query = db.query(EventLog).filter(
        EventLog.event_type == "audit"
    )

    if search.strip():
        value = f"%{search.strip()}%"
        query = query.filter(EventLog.message.ilike(value))

    if result == "allowed":
        query = query.filter(EventLog.level == "INFO")
    elif result == "denied":
        query = query.filter(EventLog.level == "WARNING")

    try:
        if date_from:
            query = query.filter(
                EventLog.created_at
                >= datetime.strptime(date_from, "%Y-%m-%d")
            )
    except ValueError:
        date_from = ""

    try:
        if date_to:
            query = query.filter(
                EventLog.created_at
                < (
                    datetime.strptime(date_to, "%Y-%m-%d")
                    + timedelta(days=1)
                )
            )
    except ValueError:
        date_to = ""

    return query, date_from, date_to


@router.get("/audit", response_class=HTMLResponse)
def audit_page(
    request: Request,
    search: str = "",
    result: str = "",
    date_from: str = "",
    date_to: str = "",
):
    denied = require_admin(request)
    if denied:
        return denied

    db = SessionLocal()

    query, date_from, date_to = build_audit_query(
        db,
        search=search,
        result=result,
        date_from=date_from,
        date_to=date_to,
    )

    rows = (
        query.order_by(EventLog.created_at.desc())
        .limit(500)
        .all()
    )

    total_count = (
        db.query(EventLog)
        .filter(EventLog.event_type == "audit")
        .count()
    )
    allowed_count = (
        db.query(EventLog)
        .filter(
            EventLog.event_type == "audit",
            EventLog.level == "INFO",
        )
        .count()
    )
    denied_count = (
        db.query(EventLog)
        .filter(
            EventLog.event_type == "audit",
            EventLog.level == "WARNING",
        )
        .count()
    )

    db.close()

    return templates.TemplateResponse(
        request=request,
        name="audit.html",
        context={
            "rows": rows,
            "search": search,
            "selected_result": result,
            "date_from": date_from,
            "date_to": date_to,
            "total_count": total_count,
            "allowed_count": allowed_count,
            "denied_count": denied_count,
        },
    )


@router.get("/audit/export.csv")
def audit_export_csv(
    request: Request,
    search: str = "",
    result: str = "",
    date_from: str = "",
    date_to: str = "",
):
    denied = require_admin(request)
    if denied:
        return denied

    db = SessionLocal()
    query, date_from, date_to = build_audit_query(
        db,
        search=search,
        result=result,
        date_from=date_from,
        date_to=date_to,
    )

    rows = (
        query.order_by(EventLog.created_at.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "Date",
        "Résultat",
        "Action",
    ])

    for row in rows:
        writer.writerow([
            format_local_time(row.created_at, "%d/%m/%Y %H:%M:%S"),
            "Autorisé" if row.level == "INFO" else "Refusé",
            row.message,
        ])

    db.close()

    content = "\ufeff" + output.getvalue()

    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                'attachment; filename="opendesk-audit.csv"'
            )
        },
    )
