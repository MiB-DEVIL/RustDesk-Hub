from datetime import datetime, timedelta
import csv
import io
import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.database.database import SessionLocal
from app.models.agent_action import AgentAction
from app.models.client import Client
from app.services.action_service import (
    ALLOWED_ACTION_TYPES,
    cancel_action,
    claim_next_action,
    create_action,
    expire_stale_actions,
    finish_action,
    retry_action,
)
from app.services.agent_auth import require_agent_key
from app.services.time_service import register_time_filters


router = APIRouter()
templates = register_time_filters(
    Jinja2Templates(directory="app/templates")
)


MAINTENANCE_PROFILES = {
    "quick_diagnostic": {
        "label": "Diagnostic rapide",
        "actions": [
            "agent_status",
            "system_health",
            "network_test",
        ],
    },
    "full_refresh": {
        "label": "Actualisation complète",
        "actions": [
            "agent_status",
            "windows_info",
            "system_health",
            "disk_details",
            "network_details",
            "dns_configuration",
            "process_check",
            "recent_system_errors",
            "network_test",
            "rustdesk_refresh",
            "inventory_now",
        ],
    },
}



@router.get("/tasks", response_class=HTMLResponse)
def tasks_page(
    request: Request,
    status: str = "",
    search: str = "",
    action_type: str = "",
    client_id: int = 0,
    date_from: str = "",
    date_to: str = "",
    page: int = 1,
    per_page: int = 50,
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    expire_stale_actions(db)

    query = (
        db.query(AgentAction, Client)
        .join(Client, Client.id == AgentAction.client_id)
    )

    allowed_statuses = {
        "pending",
        "running",
        "success",
        "failed",
        "cancelled",
    }

    if status in allowed_statuses:
        query = query.filter(AgentAction.status == status)

    cleaned_search = (search or "").strip()

    if cleaned_search:
        like_value = f"%{cleaned_search}%"
        query = query.filter(
            (Client.name.ilike(like_value))
            | (Client.hostname.ilike(like_value))
            | (Client.rustdesk_id.ilike(like_value))
            | (AgentAction.action_type.ilike(like_value))
            | (AgentAction.requested_by.ilike(like_value))
        )

    if action_type in ALLOWED_ACTION_TYPES:
        query = query.filter(AgentAction.action_type == action_type)

    if client_id > 0:
        query = query.filter(Client.id == client_id)

    parsed_date_from = None
    parsed_date_to = None

    try:
        if date_from:
            parsed_date_from = datetime.strptime(
                date_from,
                "%Y-%m-%d",
            )
            query = query.filter(
                AgentAction.created_at >= parsed_date_from
            )
    except ValueError:
        date_from = ""

    try:
        if date_to:
            parsed_date_to = (
                datetime.strptime(date_to, "%Y-%m-%d")
                + timedelta(days=1)
            )
            query = query.filter(
                AgentAction.created_at < parsed_date_to
            )
    except ValueError:
        date_to = ""

    allowed_page_sizes = {25, 50, 100}
    if per_page not in allowed_page_sizes:
        per_page = 50

    page = max(page, 1)
    total_filtered = query.count()
    total_pages = max(1, (total_filtered + per_page - 1) // per_page)

    if page > total_pages:
        page = total_pages

    rows = (
        query.order_by(AgentAction.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    clients = db.query(Client).order_by(Client.name.asc()).all()

    counters = {
        "all": db.query(AgentAction).count(),
        "pending": db.query(AgentAction)
        .filter(AgentAction.status == "pending")
        .count(),
        "running": db.query(AgentAction)
        .filter(AgentAction.status == "running")
        .count(),
        "success": db.query(AgentAction)
        .filter(AgentAction.status == "success")
        .count(),
        "failed": db.query(AgentAction)
        .filter(AgentAction.status == "failed")
        .count(),
        "cancelled": db.query(AgentAction)
        .filter(AgentAction.status == "cancelled")
        .count(),
    }

    db.close()

    return templates.TemplateResponse(
        request=request,
        name="tasks.html",
        context={
            "rows": rows,
            "clients": clients,
            "action_types": ALLOWED_ACTION_TYPES,
            "selected_status": status,
            "search": cleaned_search,
            "selected_action_type": action_type,
            "selected_client_id": client_id,
            "date_from": date_from,
            "date_to": date_to,
            "counters": counters,
            "maintenance_profiles": MAINTENANCE_PROFILES,
            "page": page,
            "per_page": per_page,
            "total_filtered": total_filtered,
            "total_pages": total_pages,
        },
    )


@router.post("/tasks/create-bulk")
def create_bulk_tasks(
    request: Request,
    client_ids: list[int] = Form(default=[]),
    action_type: str = Form(...),
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    if not client_ids:
        return RedirectResponse("/tasks?error=no_selection", status_code=303)

    db = SessionLocal()

    if action_type not in ALLOWED_ACTION_TYPES:
        db.close()
        return RedirectResponse("/tasks?error=type", status_code=303)

    clients = (
        db.query(Client)
        .filter(Client.id.in_(client_ids))
        .order_by(Client.name.asc())
        .all()
    )

    created_count = 0
    for client in clients:
        create_action(
            db,
            client=client,
            action_type=action_type,
            requested_by=request.session.get("user", "admin"),
        )
        created_count += 1

    db.close()
    return RedirectResponse(
        f"/tasks?bulk_created={created_count}",
        status_code=303,
    )



@router.post("/tasks/create-maintenance")
def create_maintenance_profile(
    request: Request,
    client_ids: list[int] = Form(default=[]),
    profile_name: str = Form(...),
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    profile = MAINTENANCE_PROFILES.get(profile_name)

    if profile is None:
        return RedirectResponse(
            "/tasks?maintenance_error=profile",
            status_code=303,
        )

    if not client_ids:
        return RedirectResponse(
            "/tasks?maintenance_error=no_selection",
            status_code=303,
        )

    db = SessionLocal()
    clients = (
        db.query(Client)
        .filter(Client.id.in_(client_ids))
        .order_by(Client.name.asc())
        .all()
    )

    created_count = 0

    for client in clients:
        for action_type in profile["actions"]:
            create_action(
                db,
                client=client,
                action_type=action_type,
                requested_by=request.session.get("user", "admin"),
            )
            created_count += 1

    machine_count = len(clients)
    db.close()

    return RedirectResponse(
        (
            "/tasks?"
            f"maintenance_created={created_count}&"
            f"maintenance_machines={machine_count}"
        ),
        status_code=303,
    )


@router.post("/tasks/cleanup")
def cleanup_tasks(
    request: Request,
    retention_days: int = Form(...),
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    allowed_retention_days = {30, 90, 180, 365}

    if retention_days not in allowed_retention_days:
        return RedirectResponse(
            "/tasks?cleanup_error=retention",
            status_code=303,
        )

    db = SessionLocal()
    cutoff = datetime.utcnow() - timedelta(days=retention_days)

    completed_statuses = {
        "success",
        "failed",
        "cancelled",
    }

    old_actions = (
        db.query(AgentAction)
        .filter(
            AgentAction.status.in_(completed_statuses),
            AgentAction.created_at < cutoff,
        )
        .all()
    )

    deleted_count = len(old_actions)

    for action in old_actions:
        db.delete(action)

    db.commit()
    db.close()

    return RedirectResponse(
        (
            "/tasks?"
            f"cleanup_done={deleted_count}&"
            f"retention_days={retention_days}"
        ),
        status_code=303,
    )


@router.post("/tasks/bulk-cancel")
def bulk_cancel_tasks(
    request: Request,
    action_uuids: list[str] = Form(default=[]),
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    if not action_uuids:
        return RedirectResponse(
            "/tasks?bulk_error=no_selection",
            status_code=303,
        )

    db = SessionLocal()

    rows = (
        db.query(AgentAction, Client)
        .join(Client, Client.id == AgentAction.client_id)
        .filter(AgentAction.action_uuid.in_(action_uuids))
        .all()
    )

    cancelled_count = 0
    skipped_count = 0

    for action, client in rows:
        if action.status != "pending":
            skipped_count += 1
            continue

        cancel_action(
            db,
            action=action,
            client=client,
            requested_by=request.session.get("user", "admin"),
        )
        cancelled_count += 1

    db.close()

    return RedirectResponse(
        (
            "/tasks?"
            f"bulk_cancelled={cancelled_count}&"
            f"bulk_skipped={skipped_count}"
        ),
        status_code=303,
    )


@router.post("/tasks/bulk-retry")
def bulk_retry_tasks(
    request: Request,
    action_uuids: list[str] = Form(default=[]),
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    if not action_uuids:
        return RedirectResponse(
            "/tasks?bulk_error=no_selection",
            status_code=303,
        )

    db = SessionLocal()

    rows = (
        db.query(AgentAction, Client)
        .join(Client, Client.id == AgentAction.client_id)
        .filter(AgentAction.action_uuid.in_(action_uuids))
        .all()
    )

    retried_count = 0
    skipped_count = 0

    for action, client in rows:
        if action.status not in {"failed", "cancelled"}:
            skipped_count += 1
            continue

        retry_action(
            db,
            action=action,
            client=client,
            requested_by=request.session.get("user", "admin"),
        )
        retried_count += 1

    db.close()

    return RedirectResponse(
        (
            "/tasks?"
            f"bulk_retried={retried_count}&"
            f"bulk_skipped={skipped_count}"
        ),
        status_code=303,
    )


@router.get("/tasks/export.csv")
def export_tasks_csv(
    request: Request,
    status: str = "",
    search: str = "",
    action_type: str = "",
    client_id: int = 0,
    date_from: str = "",
    date_to: str = "",
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    expire_stale_actions(db)

    query = (
        db.query(AgentAction, Client)
        .join(Client, Client.id == AgentAction.client_id)
    )

    allowed_statuses = {
        "pending",
        "running",
        "success",
        "failed",
        "cancelled",
    }

    if status in allowed_statuses:
        query = query.filter(AgentAction.status == status)

    cleaned_search = (search or "").strip()

    if cleaned_search:
        like_value = f"%{cleaned_search}%"
        query = query.filter(
            (Client.name.ilike(like_value))
            | (Client.hostname.ilike(like_value))
            | (Client.rustdesk_id.ilike(like_value))
            | (AgentAction.action_type.ilike(like_value))
            | (AgentAction.requested_by.ilike(like_value))
        )

    if action_type in ALLOWED_ACTION_TYPES:
        query = query.filter(AgentAction.action_type == action_type)

    if client_id > 0:
        query = query.filter(Client.id == client_id)

    try:
        if date_from:
            query = query.filter(
                AgentAction.created_at
                >= datetime.strptime(date_from, "%Y-%m-%d")
            )
    except ValueError:
        pass

    try:
        if date_to:
            query = query.filter(
                AgentAction.created_at
                < (
                    datetime.strptime(date_to, "%Y-%m-%d")
                    + timedelta(days=1)
                )
            )
    except ValueError:
        pass

    rows = query.order_by(AgentAction.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")

    writer.writerow([
        "Date de création",
        "Machine",
        "Hostname",
        "ID RustDesk",
        "Action",
        "État",
        "Utilisateur",
        "Démarrée",
        "Terminée",
        "Message",
        "Erreur",
    ])

    for action, client in rows:
        writer.writerow([
            action.created_at.strftime("%Y-%m-%d %H:%M:%S")
            if action.created_at else "",
            client.name or "",
            client.hostname or "",
            client.rustdesk_id or "",
            ALLOWED_ACTION_TYPES.get(
                action.action_type,
                action.action_type,
            ),
            action.status or "",
            action.requested_by or "",
            action.started_at.strftime("%Y-%m-%d %H:%M:%S")
            if action.started_at else "",
            action.finished_at.strftime("%Y-%m-%d %H:%M:%S")
            if action.finished_at else "",
            action.result_message or "",
            action.error_message or "",
        ])

    db.close()

    content = "\ufeff" + output.getvalue()

    headers = {
        "Content-Disposition": (
            'attachment; filename="opendesk-tasks.csv"'
        )
    }

    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


@router.post("/tasks/{action_uuid}/duplicate")
def duplicate_task(request: Request, action_uuid: str):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()

    row = (
        db.query(AgentAction, Client)
        .join(Client, Client.id == AgentAction.client_id)
        .filter(AgentAction.action_uuid == action_uuid)
        .first()
    )

    if row is None:
        db.close()
        return RedirectResponse(
            "/tasks?error=not_found",
            status_code=303,
        )

    action, client = row

    if action.action_type not in ALLOWED_ACTION_TYPES:
        db.close()
        return RedirectResponse(
            f"/tasks/{action_uuid}?error=cannot_duplicate",
            status_code=303,
        )

    new_action = create_action(
        db,
        client=client,
        action_type=action.action_type,
        requested_by=request.session.get("user", "admin"),
    )

    new_uuid = new_action.action_uuid
    db.close()

    return RedirectResponse(
        f"/tasks/{new_uuid}?duplicated=1",
        status_code=303,
    )


@router.get("/tasks-report/export.csv")
def export_tasks_report_csv(
    request: Request,
    date_from: str = "",
    date_to: str = "",
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    query = (
        db.query(AgentAction, Client)
        .join(Client, Client.id == AgentAction.client_id)
    )

    try:
        if date_from:
            query = query.filter(
                AgentAction.created_at
                >= datetime.strptime(date_from, "%Y-%m-%d")
            )
    except ValueError:
        date_from = ""

    try:
        if date_to:
            query = query.filter(
                AgentAction.created_at
                < (
                    datetime.strptime(date_to, "%Y-%m-%d")
                    + timedelta(days=1)
                )
            )
    except ValueError:
        date_to = ""

    rows = query.order_by(AgentAction.created_at.desc()).all()

    counters = {
        "pending": 0,
        "running": 0,
        "success": 0,
        "failed": 0,
        "cancelled": 0,
    }
    durations = []
    action_breakdown = {}
    machine_breakdown = {}

    for action, client in rows:
        if action.status in counters:
            counters[action.status] += 1

        if action.started_at and action.finished_at:
            duration = (
                action.finished_at - action.started_at
            ).total_seconds()
            if duration >= 0:
                durations.append(duration)

        action_label = ALLOWED_ACTION_TYPES.get(
            action.action_type,
            action.action_type,
        )
        action_stats = action_breakdown.setdefault(
            action_label,
            {"total": 0, "success": 0, "failed": 0},
        )
        action_stats["total"] += 1
        if action.status == "success":
            action_stats["success"] += 1
        elif action.status == "failed":
            action_stats["failed"] += 1

        machine_name = (
            client.name
            or client.hostname
            or f"Machine {client.id}"
        )
        machine_stats = machine_breakdown.setdefault(
            machine_name,
            {"total": 0, "success": 0, "failed": 0},
        )
        machine_stats["total"] += 1
        if action.status == "success":
            machine_stats["success"] += 1
        elif action.status == "failed":
            machine_stats["failed"] += 1

    finished = counters["success"] + counters["failed"]
    success_rate = (
        round((counters["success"] / finished) * 100, 1)
        if finished else 0
    )
    average_duration = (
        round(sum(durations) / len(durations), 2)
        if durations else 0
    )

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")

    writer.writerow(["Rapport OpenDesk Hub", "Tâches"])
    writer.writerow(["Période de début", date_from or "Toutes"])
    writer.writerow(["Période de fin", date_to or "Toutes"])
    writer.writerow([])
    writer.writerow(["Indicateur", "Valeur"])
    writer.writerow(["Total", len(rows)])
    writer.writerow(["En attente", counters["pending"]])
    writer.writerow(["En cours", counters["running"]])
    writer.writerow(["Succès", counters["success"]])
    writer.writerow(["Échecs", counters["failed"]])
    writer.writerow(["Annulées", counters["cancelled"]])
    writer.writerow(["Taux de réussite", f"{success_rate} %"])
    writer.writerow(["Durée moyenne", f"{average_duration} s"])
    writer.writerow([])

    writer.writerow([
        "Répartition par action",
        "Total",
        "Succès",
        "Échecs",
        "Taux de réussite",
    ])

    for label, stats in sorted(
        action_breakdown.items(),
        key=lambda item: item[1]["total"],
        reverse=True,
    ):
        done = stats["success"] + stats["failed"]
        rate = (
            round((stats["success"] / done) * 100, 1)
            if done else 0
        )
        writer.writerow([
            label,
            stats["total"],
            stats["success"],
            stats["failed"],
            f"{rate} %",
        ])

    writer.writerow([])
    writer.writerow([
        "Machine",
        "Total",
        "Succès",
        "Échecs",
    ])

    for name, stats in sorted(
        machine_breakdown.items(),
        key=lambda item: item[1]["total"],
        reverse=True,
    ):
        writer.writerow([
            name,
            stats["total"],
            stats["success"],
            stats["failed"],
        ])

    db.close()

    content = "\ufeff" + output.getvalue()
    filename = "opendesk-task-report.csv"

    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            )
        },
    )


@router.get("/tasks-report", response_class=HTMLResponse)
def tasks_report(
    request: Request,
    date_from: str = "",
    date_to: str = "",
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    query = (
        db.query(AgentAction, Client)
        .join(Client, Client.id == AgentAction.client_id)
    )

    try:
        if date_from:
            query = query.filter(
                AgentAction.created_at
                >= datetime.strptime(date_from, "%Y-%m-%d")
            )
    except ValueError:
        date_from = ""

    try:
        if date_to:
            query = query.filter(
                AgentAction.created_at
                < (
                    datetime.strptime(date_to, "%Y-%m-%d")
                    + timedelta(days=1)
                )
            )
    except ValueError:
        date_to = ""

    rows = query.order_by(AgentAction.created_at.desc()).all()

    total = len(rows)
    counters = {
        "pending": 0,
        "running": 0,
        "success": 0,
        "failed": 0,
        "cancelled": 0,
    }
    durations = []
    action_breakdown = {}
    machine_breakdown = {}

    for action, client in rows:
        if action.status in counters:
            counters[action.status] += 1

        if action.started_at and action.finished_at:
            duration = (
                action.finished_at - action.started_at
            ).total_seconds()
            if duration >= 0:
                durations.append(duration)

        action_label = ALLOWED_ACTION_TYPES.get(
            action.action_type,
            action.action_type,
        )
        action_stats = action_breakdown.setdefault(
            action_label,
            {"total": 0, "success": 0, "failed": 0},
        )
        action_stats["total"] += 1
        if action.status == "success":
            action_stats["success"] += 1
        elif action.status == "failed":
            action_stats["failed"] += 1

        machine_stats = machine_breakdown.setdefault(
            client.name or client.hostname or f"Machine {client.id}",
            {"total": 0, "success": 0, "failed": 0},
        )
        machine_stats["total"] += 1
        if action.status == "success":
            machine_stats["success"] += 1
        elif action.status == "failed":
            machine_stats["failed"] += 1

    finished = counters["success"] + counters["failed"]
    success_rate = (
        round((counters["success"] / finished) * 100, 1)
        if finished else 0
    )
    average_duration = (
        round(sum(durations) / len(durations), 2)
        if durations else 0
    )

    action_rows = sorted(
        action_breakdown.items(),
        key=lambda item: item[1]["total"],
        reverse=True,
    )
    machine_rows = sorted(
        machine_breakdown.items(),
        key=lambda item: item[1]["total"],
        reverse=True,
    )[:10]

    db.close()

    return templates.TemplateResponse(
        request=request,
        name="tasks_report.html",
        context={
            "date_from": date_from,
            "date_to": date_to,
            "total": total,
            "counters": counters,
            "finished": finished,
            "success_rate": success_rate,
            "average_duration": average_duration,
            "action_rows": action_rows,
            "machine_rows": machine_rows,
        },
    )


@router.get("/tasks/{action_uuid}/export.json")
def export_task_json(request: Request, action_uuid: str):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()

    row = (
        db.query(AgentAction, Client)
        .join(Client, Client.id == AgentAction.client_id)
        .filter(AgentAction.action_uuid == action_uuid)
        .first()
    )

    if row is None:
        db.close()
        return JSONResponse(
            {"status": "error", "detail": "Tâche introuvable"},
            status_code=404,
        )

    action, client = row

    try:
        result_data = json.loads(action.result_data or "{}")
    except json.JSONDecodeError:
        result_data = {"raw": action.result_data}

    payload = {
        "opendesk_hub": {
            "version": "0.9.7.0",
            "export_type": "task",
        },
        "task": {
            "uuid": action.action_uuid,
            "type": action.action_type,
            "label": ALLOWED_ACTION_TYPES.get(
                action.action_type,
                action.action_type,
            ),
            "status": action.status,
            "requested_by": action.requested_by,
            "created_at": (
                action.created_at.isoformat()
                if action.created_at else None
            ),
            "started_at": (
                action.started_at.isoformat()
                if action.started_at else None
            ),
            "finished_at": (
                action.finished_at.isoformat()
                if action.finished_at else None
            ),
            "result_message": action.result_message,
            "error_message": action.error_message,
            "result_data": result_data,
        },
        "machine": {
            "id": client.id,
            "name": client.name,
            "hostname": client.hostname,
            "rustdesk_id": client.rustdesk_id,
            "machine_uuid": client.machine_uuid,
            "ip": client.ip,
            "agent_version": client.agent_version,
        },
    }

    db.close()

    content = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )

    headers = {
        "Content-Disposition": (
            f'attachment; filename="opendesk-task-{action_uuid}.json"'
        )
    }

    return StreamingResponse(
        iter([content]),
        media_type="application/json; charset=utf-8",
        headers=headers,
    )


@router.get("/tasks/{action_uuid}/print", response_class=HTMLResponse)
def task_print_report(request: Request, action_uuid: str):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    expire_stale_actions(db)

    row = (
        db.query(AgentAction, Client)
        .join(Client, Client.id == AgentAction.client_id)
        .filter(AgentAction.action_uuid == action_uuid)
        .first()
    )

    if row is None:
        db.close()
        return RedirectResponse("/tasks?error=not_found", status_code=303)

    action, client = row

    try:
        result_data = json.loads(action.result_data or "{}")
    except json.JSONDecodeError:
        result_data = {"raw": action.result_data}

    duration_seconds = None
    if action.started_at and action.finished_at:
        duration_seconds = round(
            (action.finished_at - action.started_at).total_seconds(),
            2,
        )

    db.close()

    return templates.TemplateResponse(
        request=request,
        name="task_print.html",
        context={
            "action": action,
            "client": client,
            "action_label": ALLOWED_ACTION_TYPES.get(
                action.action_type,
                action.action_type,
            ),
            "result_data": result_data,
            "duration_seconds": duration_seconds,
        },
    )


@router.get("/tasks/{action_uuid}", response_class=HTMLResponse)
def task_detail(request: Request, action_uuid: str):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    expire_stale_actions(db)

    row = (
        db.query(AgentAction, Client)
        .join(Client, Client.id == AgentAction.client_id)
        .filter(AgentAction.action_uuid == action_uuid)
        .first()
    )

    if row is None:
        db.close()
        return RedirectResponse("/tasks?error=not_found", status_code=303)

    action, client = row

    try:
        result_data = json.loads(action.result_data or "{}")
    except json.JSONDecodeError:
        result_data = {"raw": action.result_data}

    duration_seconds = None
    if action.started_at and action.finished_at:
        duration_seconds = round(
            (action.finished_at - action.started_at).total_seconds(),
            2,
        )

    db.close()

    return templates.TemplateResponse(
        request=request,
        name="task_detail.html",
        context={
            "action": action,
            "client": client,
            "action_label": ALLOWED_ACTION_TYPES.get(
                action.action_type,
                action.action_type,
            ),
            "result_data": result_data,
            "duration_seconds": duration_seconds,
        },
    )


@router.post("/tasks/create")
def create_task(
    request: Request,
    client_id: int = Form(...),
    action_type: str = Form(...),
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    client = db.query(Client).filter(Client.id == client_id).first()

    if client is None:
        db.close()
        return RedirectResponse("/tasks?error=client", status_code=303)

    try:
        create_action(
            db,
            client=client,
            action_type=action_type,
            requested_by=request.session.get("user", "admin"),
        )
    except ValueError:
        db.close()
        return RedirectResponse("/tasks?error=type", status_code=303)

    db.close()
    return RedirectResponse("/tasks?created=1", status_code=303)


@router.post("/tasks/{action_uuid}/cancel")
def cancel_task(request: Request, action_uuid: str):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()

    row = (
        db.query(AgentAction, Client)
        .join(Client, Client.id == AgentAction.client_id)
        .filter(AgentAction.action_uuid == action_uuid)
        .first()
    )

    if row is None:
        db.close()
        return RedirectResponse("/tasks?error=not_found", status_code=303)

    action, client = row

    try:
        cancel_action(
            db,
            action=action,
            client=client,
            requested_by=request.session.get("user", "admin"),
        )
    except ValueError:
        db.close()
        return RedirectResponse(
            f"/tasks/{action_uuid}?error=cannot_cancel",
            status_code=303,
        )

    db.close()
    return RedirectResponse(
        f"/tasks/{action_uuid}?cancelled=1",
        status_code=303,
    )


@router.post("/tasks/{action_uuid}/retry")
def retry_task(request: Request, action_uuid: str):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()

    row = (
        db.query(AgentAction, Client)
        .join(Client, Client.id == AgentAction.client_id)
        .filter(AgentAction.action_uuid == action_uuid)
        .first()
    )

    if row is None:
        db.close()
        return RedirectResponse("/tasks?error=not_found", status_code=303)

    action, client = row

    try:
        new_action = retry_action(
            db,
            action=action,
            client=client,
            requested_by=request.session.get("user", "admin"),
        )
    except ValueError:
        db.close()
        return RedirectResponse(
            f"/tasks/{action_uuid}?error=cannot_retry",
            status_code=303,
        )

    new_uuid = new_action.action_uuid
    db.close()

    return RedirectResponse(
        f"/tasks/{new_uuid}?retried=1",
        status_code=303,
    )


@router.get(
    "/api/agent/actions/next",
    dependencies=[Depends(require_agent_key)],
)
def next_agent_action(machine_uuid: str):
    db = SessionLocal()
    client = (
        db.query(Client)
        .filter(Client.machine_uuid == machine_uuid)
        .first()
    )

    if client is None:
        db.close()
        return JSONResponse(
            {"status": "error", "detail": "Machine inconnue"},
            status_code=404,
        )

    action = claim_next_action(db, client)

    if action is None:
        db.close()
        return {"status": "ok", "action": None}

    payload = {
        "uuid": action.action_uuid,
        "type": action.action_type,
        "created_at": action.created_at.isoformat(),
    }

    db.close()
    return {"status": "ok", "action": payload}


@router.post(
    "/api/agent/actions/{action_uuid}/result",
    dependencies=[Depends(require_agent_key)],
)
def agent_action_result(
    action_uuid: str,
    machine_uuid: str = Form(...),
    success: bool = Form(...),
    message: str = Form(""),
    data_json: str = Form("{}"),
    error: str = Form(""),
):
    db = SessionLocal()

    client = (
        db.query(Client)
        .filter(Client.machine_uuid == machine_uuid)
        .first()
    )
    action = (
        db.query(AgentAction)
        .filter(AgentAction.action_uuid == action_uuid)
        .first()
    )

    if client is None or action is None or action.client_id != client.id:
        db.close()
        return JSONResponse(
            {"status": "error", "detail": "Action invalide"},
            status_code=404,
        )

    if action.status not in {"running", "pending"}:
        db.close()
        return JSONResponse(
            {"status": "error", "detail": "Action déjà terminée"},
            status_code=409,
        )

    try:
        data = json.loads(data_json or "{}")
    except json.JSONDecodeError:
        data = {"raw": data_json}

    finish_action(
        db,
        action=action,
        client=client,
        success=success,
        message=message,
        data=data,
        error=error,
    )

    db.close()
    return {"status": "ok"}


@router.get("/api/tasks/recent")
def recent_tasks(request: Request):
    if "user" not in request.session:
        return JSONResponse(
            {"detail": "Non authentifié"},
            status_code=401,
        )

    db = SessionLocal()
    expire_stale_actions(db)

    rows = (
        db.query(AgentAction, Client)
        .join(Client, Client.id == AgentAction.client_id)
        .order_by(AgentAction.created_at.desc())
        .limit(50)
        .all()
    )

    result = []

    for action, client in rows:
        result.append({
            "uuid": action.action_uuid,
            "machine": client.name,
            "type": action.action_type,
            "status": action.status,
            "created_at": action.created_at.isoformat(),
            "finished_at": (
                action.finished_at.isoformat()
                if action.finished_at
                else None
            ),
            "message": action.result_message,
            "error": action.error_message,
        })

    counters = {
        "all": db.query(AgentAction).count(),
        "pending": db.query(AgentAction)
        .filter(AgentAction.status == "pending")
        .count(),
        "running": db.query(AgentAction)
        .filter(AgentAction.status == "running")
        .count(),
        "success": db.query(AgentAction)
        .filter(AgentAction.status == "success")
        .count(),
        "failed": db.query(AgentAction)
        .filter(AgentAction.status == "failed")
        .count(),
        "cancelled": db.query(AgentAction)
        .filter(AgentAction.status == "cancelled")
        .count(),
    }

    db.close()
    return {
        "items": result,
        "counters": counters,
        "labels": ALLOWED_ACTION_TYPES,
    }
