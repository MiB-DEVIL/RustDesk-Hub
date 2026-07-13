from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_

from app.database.database import SessionLocal
from app.models.client import Client
from app.models.group import Group
from app.services.client_status import refresh_client_statuses
from app.services.time_service import register_time_filters

router = APIRouter()
templates = register_time_filters(
    Jinja2Templates(directory="app/templates")
)

@router.get("/clients", response_class=HTMLResponse)
def clients(request: Request, group: str = "", search: str = ""):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    refresh_client_statuses(db)

    groups = db.query(Group).order_by(Group.name).all()
    query = db.query(Client)

    if group:
        query = query.filter(Client.group_name == group)

    if search:
        query = query.filter(
            or_(
                Client.name.ilike(f"%{search}%"),
                Client.rustdesk_id.ilike(f"%{search}%"),
                Client.hostname.ilike(f"%{search}%"),
                Client.ip.ilike(f"%{search}%"),
                Client.notes.ilike(f"%{search}%"),
            )
        )

    clients = query.order_by(Client.name).all()
    db.close()

    return templates.TemplateResponse(
        request=request,
        name="clients.html",
        context={
            "clients": clients,
            "groups": groups,
            "selected_group": group,
            "search": search,
        },
    )

@router.get("/clients/add", response_class=HTMLResponse)
def add_client_page(request: Request):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    groups = db.query(Group).order_by(Group.name).all()
    db.close()

    return templates.TemplateResponse(
        request=request,
        name="add_client.html",
        context={"groups": groups},
    )

@router.post("/clients/add")
def add_client(
    request: Request,
    name: str = Form(...),
    rustdesk_id: str = Form(...),
    group_name: str = Form(...),
    notes: str = Form(""),
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    existing = db.query(Client).filter(Client.rustdesk_id == rustdesk_id).first()

    if existing:
        db.close()
        return RedirectResponse("/clients", status_code=303)

    client = Client(
        name=name,
        rustdesk_id=rustdesk_id,
        group_name=group_name,
        notes=notes,
    )
    db.add(client)
    db.commit()
    db.close()
    return RedirectResponse("/clients", status_code=303)

@router.get("/clients/edit/{client_id}", response_class=HTMLResponse)
def edit_client_page(request: Request, client_id: int):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    client = db.query(Client).filter(Client.id == client_id).first()
    groups = db.query(Group).order_by(Group.name).all()
    db.close()

    if client is None:
        return RedirectResponse("/clients", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="edit_client.html",
        context={"client": client, "groups": groups},
    )

@router.post("/clients/edit/{client_id}")
def edit_client(
    request: Request,
    client_id: int,
    name: str = Form(...),
    rustdesk_id: str = Form(...),
    group_name: str = Form(...),
    notes: str = Form(""),
    active: bool = Form(False),
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    client = db.query(Client).filter(Client.id == client_id).first()

    if client is None:
        db.close()
        return RedirectResponse("/clients", status_code=303)

    duplicate = (
        db.query(Client)
        .filter(Client.rustdesk_id == rustdesk_id, Client.id != client_id)
        .first()
    )

    if duplicate:
        db.close()
        return RedirectResponse(f"/clients/edit/{client_id}", status_code=303)

    client.name = name
    client.rustdesk_id = rustdesk_id
    client.group_name = group_name
    client.notes = notes
    client.active = active

    db.commit()
    db.close()
    return RedirectResponse("/clients", status_code=303)

@router.get("/clients/delete/{client_id}")
def delete_client(request: Request, client_id: int):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    client = db.query(Client).filter(Client.id == client_id).first()

    if client:
        db.delete(client)
        db.commit()

    db.close()
    return RedirectResponse("/clients", status_code=303)
