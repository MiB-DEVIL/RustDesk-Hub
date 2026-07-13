from fastapi import APIRouter
from fastapi import Form
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database.database import SessionLocal
from app.models.client import Client
from app.models.group import Group
from app.services.time_service import register_time_filters

router = APIRouter()
templates = register_time_filters(
    Jinja2Templates(directory="app/templates")
)


@router.get("/groups", response_class=HTMLResponse)
def groups(request: Request):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    groups = db.query(Group).order_by(Group.name).all()
    stats = {}

    for group in groups:
        stats[group.name] = db.query(Client).filter(Client.group_name == group.name).count()

    db.close()

    return templates.TemplateResponse(
        request=request,
        name="groups.html",
        context={"groups": groups, "stats": stats}
    )


@router.post("/groups/add")
def add_group(request: Request, name: str = Form(...)):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    clean_name = name.strip()

    if not clean_name:
        return RedirectResponse("/groups", status_code=303)

    db = SessionLocal()
    existing = db.query(Group).filter(Group.name == clean_name).first()

    if not existing:
        db.add(Group(name=clean_name))
        db.commit()

    db.close()
    return RedirectResponse("/groups", status_code=303)


@router.get("/groups/delete/{group_id}")
def delete_group(request: Request, group_id: int):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    group = db.query(Group).filter(Group.id == group_id).first()

    if group:
        nb_clients = db.query(Client).filter(Client.group_name == group.name).count()
        if nb_clients == 0:
            db.delete(group)
            db.commit()

    db.close()
    return RedirectResponse("/groups", status_code=303)
