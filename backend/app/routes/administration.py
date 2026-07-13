from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database.database import SessionLocal
from app.models.client import Client
from app.models.group import Group
from app.models.inventory import Inventory
from app.services.time_service import register_time_filters


router = APIRouter()
templates = register_time_filters(
    Jinja2Templates(directory="app/templates")
)


@router.get("/administration", response_class=HTMLResponse)
def administration_page(
    request: Request,
    group: str = "",
    status: str = "",
):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()

    query = (
        db.query(Client, Inventory)
        .outerjoin(Inventory, Inventory.client_id == Client.id)
    )

    if group:
        query = query.filter(Client.group_name == group)

    if status == "online":
        query = query.filter(Client.online.is_(True))
    elif status == "offline":
        query = query.filter(Client.online.is_(False))

    rows = query.order_by(Client.name.asc()).all()
    groups = db.query(Group).order_by(Group.name.asc()).all()

    online_count = db.query(Client).filter(Client.online.is_(True)).count()
    offline_count = db.query(Client).filter(Client.online.is_(False)).count()
    total_count = db.query(Client).count()

    db.close()

    return templates.TemplateResponse(
        request=request,
        name="administration.html",
        context={
            "rows": rows,
            "groups": groups,
            "selected_group": group,
            "selected_status": status,
            "online_count": online_count,
            "offline_count": offline_count,
            "total_count": total_count,
        },
    )
