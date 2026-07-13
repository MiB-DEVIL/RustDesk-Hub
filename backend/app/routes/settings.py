from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database.database import SessionLocal
from app.services.settings_service import get_settings_dict, set_setting
from app.services.time_service import register_time_filters

router = APIRouter()
templates = register_time_filters(
    Jinja2Templates(directory="app/templates")
)


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    settings = get_settings_dict(db)
    db.close()

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={"settings": settings},
    )


@router.post("/settings")
def save_settings(
    request: Request,
    organization_name: str = Form("OpenDesk Hub"),
    heartbeat_interval: int = Form(30),
    address_book_interval: int = Form(300),
    inventory_interval: int = Form(86400),
    agent_api_key: str = Form("OpenDeskAgent2026"),
    notification_stale_minutes: int = Form(10),
    notification_error_hours: int = Form(24),
    debug_mode: bool = Form(False),
    inventory_enabled: bool = Form(False),
    address_book_enabled: bool = Form(False),
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    set_setting(db, "organization_name", organization_name.strip() or "OpenDesk Hub")
    set_setting(db, "heartbeat_interval", str(max(10, heartbeat_interval)))
    set_setting(db, "address_book_interval", str(max(60, address_book_interval)))
    set_setting(db, "inventory_interval", str(max(300, inventory_interval)))
    set_setting(db, "agent_api_key", agent_api_key.strip() or "OpenDeskAgent2026")
    set_setting(db, "notification_stale_minutes", str(max(1, notification_stale_minutes)))
    set_setting(db, "notification_error_hours", str(max(1, notification_error_hours)))
    set_setting(db, "debug_mode", "true" if debug_mode else "false")
    set_setting(db, "inventory_enabled", "true" if inventory_enabled else "false")
    set_setting(db, "address_book_enabled", "true" if address_book_enabled else "false")
    db.close()

    return RedirectResponse("/settings?saved=1", status_code=303)


@router.get("/api/agent/config")
def agent_config():
    db = SessionLocal()
    settings = get_settings_dict(db)
    db.close()

    return {
        "heartbeat": int(settings.get("heartbeat_interval", "30")),
        "address_book_sync": int(settings.get("address_book_interval", "300")),
        "inventory_sync": int(settings.get("inventory_interval", "86400")),
        "inventory_enabled": settings.get("inventory_enabled", "true") == "true",
        "address_book_enabled": settings.get("address_book_enabled", "true") == "true",
    }
