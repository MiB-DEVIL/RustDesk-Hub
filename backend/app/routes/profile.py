from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth.security import hash_password, verify_password
from app.database.database import SessionLocal
from app.models.event_log import EventLog
from app.models.user import User
from app.services.access_service import require_login
from app.services.time_service import register_time_filters


router = APIRouter()
templates = register_time_filters(
    Jinja2Templates(directory="app/templates")
)


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    denied = require_login(request)
    if denied:
        return denied

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={},
    )


@router.post("/profile/password")
def change_own_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirmation: str = Form(...),
):
    denied = require_login(request)
    if denied:
        return denied

    if len(new_password) < 8:
        return RedirectResponse(
            "/profile?error=length",
            status_code=303,
        )

    if new_password != confirmation:
        return RedirectResponse(
            "/profile?error=confirmation",
            status_code=303,
        )

    db = SessionLocal()
    user = (
        db.query(User)
        .filter(User.username == request.session.get("user"))
        .first()
    )

    if not user or not verify_password(
        current_password,
        user.password_hash,
    ):
        db.close()
        return RedirectResponse(
            "/profile?error=current",
            status_code=303,
        )

    user.password_hash = hash_password(new_password)
    db.add(
        EventLog(
            level="INFO",
            event_type="audit",
            hostname="OpenDesk Hub",
            rustdesk_id="",
            message=(
                f"{user.username} — modification de son mot de passe"
            ),
        )
    )
    db.commit()
    db.close()

    request.session.clear()

    return RedirectResponse(
        "/login?password_changed=1",
        status_code=303,
    )
