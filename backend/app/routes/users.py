from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth.security import hash_password
from app.database.database import SessionLocal
from app.models.event_log import EventLog
from app.models.user import User
from app.services.access_service import require_admin
from app.services.time_service import register_time_filters


router = APIRouter()
templates = register_time_filters(
    Jinja2Templates(directory="app/templates")
)


def add_audit(db, request: Request, message: str):
    db.add(
        EventLog(
            level="INFO",
            event_type="audit",
            hostname="OpenDesk Hub",
            rustdesk_id="",
            message=(
                f"{request.session.get('user', 'inconnu')} — {message}"
            ),
        )
    )


@router.get("/users", response_class=HTMLResponse)
def users_page(request: Request):
    denied = require_admin(request)
    if denied:
        return denied

    db = SessionLocal()
    users = db.query(User).order_by(User.username.asc()).all()
    admin_count = (
        db.query(User)
        .filter(User.is_admin.is_(True))
        .count()
    )
    db.close()

    return templates.TemplateResponse(
        request=request,
        name="users.html",
        context={
            "users": users,
            "admin_count": admin_count,
        },
    )


@router.post("/users/create")
def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("viewer"),
):
    denied = require_admin(request)
    if denied:
        return denied

    username = username.strip()
    if len(username) < 3 or len(password) < 8:
        return RedirectResponse(
            "/users?error=invalid",
            status_code=303,
        )

    db = SessionLocal()

    existing = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if existing:
        db.close()
        return RedirectResponse(
            "/users?error=exists",
            status_code=303,
        )

    user = User(
        username=username,
        password_hash=hash_password(password),
        is_admin=(role == "admin"),
    )
    db.add(user)
    add_audit(
        db,
        request,
        f"création du compte {username} ({role})",
    )
    db.commit()
    db.close()

    return RedirectResponse(
        "/users?created=1",
        status_code=303,
    )


@router.post("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    request: Request,
    role: str = Form(...),
):
    denied = require_admin(request)
    if denied:
        return denied

    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        db.close()
        return RedirectResponse("/users", status_code=303)

    target_admin = role == "admin"

    if (
        user.is_admin
        and not target_admin
        and db.query(User)
        .filter(User.is_admin.is_(True))
        .count() <= 1
    ):
        db.close()
        return RedirectResponse(
            "/users?error=last_admin",
            status_code=303,
        )

    user.is_admin = target_admin
    add_audit(
        db,
        request,
        f"rôle de {user.username} changé en {role}",
    )
    db.commit()
    db.close()

    return RedirectResponse(
        "/users?updated=1",
        status_code=303,
    )


@router.post("/users/{user_id}/password")
def reset_user_password(
    user_id: int,
    request: Request,
    password: str = Form(...),
):
    denied = require_admin(request)
    if denied:
        return denied

    if len(password) < 8:
        return RedirectResponse(
            "/users?error=password",
            status_code=303,
        )

    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()

    if user:
        user.password_hash = hash_password(password)
        add_audit(
            db,
            request,
            f"réinitialisation du mot de passe de {user.username}",
        )
        db.commit()

    db.close()
    return RedirectResponse(
        "/users?password_reset=1",
        status_code=303,
    )


@router.post("/users/{user_id}/delete")
def delete_user(
    user_id: int,
    request: Request,
):
    denied = require_admin(request)
    if denied:
        return denied

    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        db.close()
        return RedirectResponse("/users", status_code=303)

    if user.username == request.session.get("user"):
        db.close()
        return RedirectResponse(
            "/users?error=self_delete",
            status_code=303,
        )

    if (
        user.is_admin
        and db.query(User)
        .filter(User.is_admin.is_(True))
        .count() <= 1
    ):
        db.close()
        return RedirectResponse(
            "/users?error=last_admin",
            status_code=303,
        )

    username = user.username
    db.delete(user)
    add_audit(
        db,
        request,
        f"suppression du compte {username}",
    )
    db.commit()
    db.close()

    return RedirectResponse(
        "/users?deleted=1",
        status_code=303,
    )
