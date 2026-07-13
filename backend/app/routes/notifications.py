from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database.database import SessionLocal
from app.services.notification_service import build_notification_snapshot
from app.services.time_service import register_time_filters

router = APIRouter()
templates = register_time_filters(
    Jinja2Templates(directory="app/templates")
)


@router.get("/notifications", response_class=HTMLResponse)
def notifications_page(request: Request):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    try:
        snapshot = build_notification_snapshot(db)
    finally:
        db.close()

    return templates.TemplateResponse(
        request=request,
        name="notifications.html",
        context=snapshot,
    )


@router.get("/api/notifications/summary")
def notifications_summary(request: Request):
    if "user" not in request.session:
        return {"authenticated": False, "counts": {"total": 0, "critical": 0, "warning": 0}}

    db = SessionLocal()
    try:
        snapshot = build_notification_snapshot(db)
    finally:
        db.close()

    return {
        "authenticated": True,
        "counts": snapshot["counts"],
        "generated_at": snapshot["generated_at"].isoformat(),
    }
