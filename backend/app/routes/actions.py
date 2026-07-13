from fastapi import APIRouter
from fastapi import Form
from fastapi import Request

from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse

from fastapi.templating import Jinja2Templates

from app.database.database import SessionLocal
from app.models.client import Client
from app.models.event_log import EventLog
from app.models.inventory import Inventory
from app.services.event_log_service import add_event_log
from app.services.wake_on_lan import send_magic_packet
from app.services.time_service import register_time_filters


router = APIRouter()

templates = Jinja2Templates(
    directory="app/templates"
)


@router.get(
    "/actions",
    response_class=HTMLResponse
)
def actions_page(request: Request):

    if "user" not in request.session:
        return RedirectResponse(
            "/login",
            status_code=303
        )

    db = SessionLocal()

    rows = (
        db.query(Client, Inventory)
        .outerjoin(
            Inventory,
            Inventory.client_id == Client.id
        )
        .order_by(Client.name)
        .all()
    )

    db.close()

    return templates.TemplateResponse(
        request=request,
        name="actions.html",
        context={
            "rows": rows,
            "sent": request.query_params.get("sent"),
            "error": request.query_params.get("error")
        }
    )


@router.post("/actions/wake/{client_id}")
def wake_client(
    request: Request,
    client_id: int,
    broadcast_address: str = Form("255.255.255.255"),
    port: int = Form(9),
):

    if "user" not in request.session:
        return RedirectResponse(
            "/login",
            status_code=303
        )

    db = SessionLocal()

    client = (
        db.query(Client)
        .filter(Client.id == client_id)
        .first()
    )

    inventory = (
        db.query(Inventory)
        .filter(Inventory.client_id == client_id)
        .first()
    )

    if client is None:
        db.close()

        return RedirectResponse(
            "/actions?error=client",
            status_code=303
        )

    if inventory is None or not inventory.mac:
        add_event_log(
            db,
            rustdesk_id=client.rustdesk_id,
            hostname=client.hostname,
            level="ERROR",
            event_type="wake_on_lan",
            message="Adresse MAC manquante"
        )

        db.close()

        return RedirectResponse(
            "/actions?error=mac",
            status_code=303
        )

    try:
        send_magic_packet(
            mac_address=inventory.mac,
            broadcast_address=broadcast_address,
            port=port
        )

        add_event_log(
            db,
            rustdesk_id=client.rustdesk_id,
            hostname=client.hostname,
            level="INFO",
            event_type="wake_on_lan",
            message=(
                f"Paquet Wake-on-LAN envoyé "
                f"vers {inventory.mac} "
                f"via {broadcast_address}:{port}"
            )
        )

    except (ValueError, OSError) as exc:
        add_event_log(
            db,
            rustdesk_id=client.rustdesk_id,
            hostname=client.hostname,
            level="ERROR",
            event_type="wake_on_lan",
            message=str(exc)
        )

        db.close()

        return RedirectResponse(
            "/actions?error=send",
            status_code=303
        )

    db.close()

    return RedirectResponse(
        "/actions?sent=1",
        status_code=303
    )


@router.post("/actions/wake-selected")
def wake_selected(
    request: Request,
    client_ids: list[int] = Form(default=[]),
    broadcast_address: str = Form("255.255.255.255"),
    port: int = Form(9),
):

    if "user" not in request.session:
        return RedirectResponse(
            "/login",
            status_code=303
        )

    db = SessionLocal()

    success_count = 0
    error_count = 0

    for client_id in client_ids:
        client = (
            db.query(Client)
            .filter(Client.id == client_id)
            .first()
        )

        inventory = (
            db.query(Inventory)
            .filter(Inventory.client_id == client_id)
            .first()
        )

        if (
            client is None
            or inventory is None
            or not inventory.mac
        ):
            error_count += 1
            continue

        try:
            send_magic_packet(
                mac_address=inventory.mac,
                broadcast_address=broadcast_address,
                port=port
            )

            add_event_log(
                db,
                rustdesk_id=client.rustdesk_id,
                hostname=client.hostname,
                level="INFO",
                event_type="wake_on_lan",
                message=(
                    f"Paquet Wake-on-LAN groupé envoyé "
                    f"vers {inventory.mac}"
                )
            )

            success_count += 1

        except (ValueError, OSError):
            error_count += 1

    db.close()

    return RedirectResponse(
        (
            "/actions?"
            f"sent={success_count}&"
            f"error_count={error_count}"
        ),
        status_code=303
    )
