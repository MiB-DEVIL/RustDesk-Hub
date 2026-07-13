from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth.security import verify_password
from app.database.database import SessionLocal
from app.models.user import User
from app.services.time_service import register_time_filters

router = APIRouter()
templates = register_time_filters(
    Jinja2Templates(directory="app/templates")
)

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if "user" in request.session:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html")

@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    db.close()

    if not user or not verify_password(password, user.password_hash):
        return RedirectResponse("/login", status_code=303)

    request.session["user"] = user.username
    request.session["user_id"] = user.id
    request.session["is_admin"] = bool(user.is_admin)
    return RedirectResponse("/dashboard", status_code=303)

@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
