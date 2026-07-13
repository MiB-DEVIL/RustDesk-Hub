from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database.database import SessionLocal
from app.models.agent_action import AgentAction
from app.models.client import Client
from app.models.event_log import EventLog
from app.models.inventory import Inventory
from app.services.action_service import ALLOWED_ACTION_TYPES, create_action
from app.models.machine_change import MachineChange
from app.services.time_service import register_time_filters

router = APIRouter()
templates = register_time_filters(
    Jinja2Templates(directory="app/templates")
)


@router.get("/machines/{client_id}", response_class=HTMLResponse)
def machine_detail(request: Request, client_id: int):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    client = db.query(Client).filter(Client.id == client_id).first()
    inventory = db.query(Inventory).filter(Inventory.client_id == client_id).first()

    logs = []
    changes = []
    recent_tasks = []
    task_counters = {
        "pending": 0,
        "running": 0,
        "success": 0,
        "failed": 0,
        "cancelled": 0,
    }

    if client:
        recent_tasks = (
            db.query(AgentAction)
            .filter(AgentAction.client_id == client.id)
            .order_by(AgentAction.created_at.desc())
            .limit(12)
            .all()
        )

        for status in task_counters:
            task_counters[status] = (
                db.query(AgentAction)
                .filter(
                    AgentAction.client_id == client.id,
                    AgentAction.status == status,
                )
                .count()
            )

        logs = (
            db.query(EventLog)
            .filter(
                (EventLog.rustdesk_id == client.rustdesk_id)
                | (EventLog.hostname == client.hostname)
            )
            .order_by(EventLog.created_at.desc())
            .limit(30)
            .all()
        )

    if client:
        changes = (
            db.query(MachineChange)
            .filter(MachineChange.client_id == client.id)
            .order_by(MachineChange.created_at.desc())
            .limit(30)
            .all()
        )

    db.close()

    if client is None:
        return RedirectResponse("/clients", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="machine_detail.html",
        context={
            "client": client,
            "inventory": inventory,
            "logs": logs,
            "changes": changes,
            "recent_tasks": recent_tasks,
            "task_counters": task_counters,
        },
    )


@router.post("/machines/{client_id}/quick-action")
def machine_quick_action(request: Request, client_id: int, action_type: str = Form(...)):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)
    db = SessionLocal()
    client = db.query(Client).filter(Client.id == client_id).first()
    if client is None:
        db.close()
        return RedirectResponse("/clients", status_code=303)
    if action_type not in ALLOWED_ACTION_TYPES:
        db.close()
        return RedirectResponse(f"/machines/{client_id}?action_error=type", status_code=303)
    action = create_action(db, client=client, action_type=action_type, requested_by=request.session.get("user", "admin"))
    action_uuid = action.action_uuid
    db.close()
    return RedirectResponse(f"/tasks/{action_uuid}?created=1", status_code=303)
