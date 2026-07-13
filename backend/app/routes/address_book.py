from fastapi import APIRouter
from fastapi import Header
from fastapi import HTTPException
from fastapi import Request

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from sqlalchemy import or_

from app.database.database import SessionLocal
from app.models.client import Client
from app.models.group import Group
from app.services.address_book import build_address_book
from app.services.time_service import register_time_filters


router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates"
)


@router.get("/address-book", response_class=HTMLResponse)
def address_book_page(
    request: Request,
    group: str = "",
    search: str = ""
):

    if "user" not in request.session:
        return RedirectResponse(
            "/login",
            status_code=303
        )

    db = SessionLocal()

    groups = (
        db.query(Group)
        .order_by(Group.name)
        .all()
    )

    query = (
        db.query(Client)
        .filter(Client.active == True)
    )

    if group:
        query = query.filter(
            Client.group_name == group
        )

    if search:
        query = query.filter(
            or_(
                Client.name.ilike(f"%{search}%"),
                Client.rustdesk_id.ilike(f"%{search}%"),
                Client.hostname.ilike(f"%{search}%"),
                Client.group_name.ilike(f"%{search}%")
            )
        )

    clients = (
        query
        .order_by(
            Client.group_name,
            Client.name
        )
        .all()
    )

    db.close()

    return templates.TemplateResponse(
        request=request,
        name="address_book.html",
        context={
            "clients": clients,
            "groups": groups,
            "selected_group": group,
            "search": search
        }
    )


@router.get("/api/address-book")
def address_book_api(
    x_api_key: str = Header(default="")
):

    expected_key = "RustDeskHubAddressBook2026"

    if x_api_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    db = SessionLocal()

    clients = (
        db.query(Client)
        .filter(Client.active == True)
        .order_by(
            Client.group_name,
            Client.name
        )
        .all()
    )

    payload = build_address_book(clients)

    db.close()

    return payload
