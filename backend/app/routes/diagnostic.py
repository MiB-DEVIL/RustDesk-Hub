from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database.database import SessionLocal
from app.models.agent_action import AgentAction
from app.models.client import Client
from app.models.event_log import EventLog
from app.models.inventory import Inventory
from app.services.time_service import register_time_filters

router = APIRouter()
templates = register_time_filters(
    Jinja2Templates(directory="app/templates")
)


@router.get("/diagnostic", response_class=HTMLResponse)
def diagnostic_page(request: Request):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    now = datetime.utcnow()
    heartbeat_limit = now - timedelta(minutes=10)
    inventory_limit = now - timedelta(hours=24)

    clients = db.query(Client).order_by(Client.name.asc()).all()
    inventory_by_client = {
        row.client_id: row for row in db.query(Inventory).all()
    }

    machine_rows = []

    for client in clients:
        inventory = inventory_by_client.get(client.id)

        heartbeat_ok = bool(
            client.last_seen and client.last_seen >= heartbeat_limit
        )
        inventory_ok = bool(
            inventory
            and inventory.updated_at
            and inventory.updated_at >= inventory_limit
        )
        identity_ok = bool(
            client.machine_uuid
            and client.rustdesk_id
            and client.rustdesk_id != "005"
        )
        agent_version_ok = bool(client.agent_version)

        checks = [
            heartbeat_ok,
            inventory_ok,
            identity_ok,
            agent_version_ok,
        ]
        score = int((sum(checks) / len(checks)) * 100)

        if score == 100:
            health, health_label = "healthy", "Sain"
        elif score >= 50:
            health, health_label = "warning", "À vérifier"
        else:
            health, health_label = "critical", "Critique"

        machine_rows.append({
            "client": client,
            "inventory": inventory,
            "heartbeat_ok": heartbeat_ok,
            "inventory_ok": inventory_ok,
            "identity_ok": identity_ok,
            "agent_version_ok": agent_version_ok,
            "score": score,
            "health": health,
            "health_label": health_label,
        })

    pending_actions = (
        db.query(AgentAction)
        .filter(AgentAction.status.in_(["pending", "running"]))
        .count()
    )

    failed_actions_24h = (
        db.query(AgentAction)
        .filter(
            AgentAction.status == "failed",
            AgentAction.created_at >= now - timedelta(hours=24),
        )
        .count()
    )

    recent_errors = (
        db.query(EventLog)
        .filter(
            EventLog.level.in_(["ERROR", "WARNING"]),
            EventLog.created_at >= now - timedelta(hours=24),
        )
        .order_by(EventLog.created_at.desc())
        .limit(20)
        .all()
    )

    db.close()

    return templates.TemplateResponse(
        request=request,
        name="diagnostic.html",
        context={
            "machine_rows": machine_rows,
            "total_clients": len(machine_rows),
            "healthy_count": sum(1 for r in machine_rows if r["health"] == "healthy"),
            "warning_count": sum(1 for r in machine_rows if r["health"] == "warning"),
            "critical_count": sum(1 for r in machine_rows if r["health"] == "critical"),
            "pending_actions": pending_actions,
            "failed_actions_24h": failed_actions_24h,
            "recent_errors": recent_errors,
            "generated_at": now,
        },
    )
