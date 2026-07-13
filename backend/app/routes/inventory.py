from datetime import datetime
import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database.database import SessionLocal
from app.models.client import Client
from app.models.inventory import Inventory
from app.models.professional_inventory import ProfessionalInventory
from app.services.agent_auth import require_agent_key
from app.services.time_service import register_time_filters


router = APIRouter()
templates = register_time_filters(
    Jinja2Templates(directory="app/templates")
)


@router.post("/api/agent/inventory")
def receive_inventory(
    machine_uuid: str = Form(""),
    rustdesk_id: str = Form(...),
    username: str = Form(""),
    os_version: str = Form(""),
    cpu: str = Form(""),
    ram_gb: str = Form(""),
    manufacturer: str = Form(""),
    model: str = Form(""),
    serial_number: str = Form(""),
    mac: str = Form(""),
    uptime_seconds: int = Form(0),
    disks_json: str = Form("[]"),
):
    db = SessionLocal()

    client = (
        db.query(Client)
        .filter(
            (Client.machine_uuid == machine_uuid)
            if machine_uuid
            else (Client.rustdesk_id == rustdesk_id)
        )
        .first()
    )

    if client is None:
        db.close()
        return {
            "status": "error",
            "detail": "client not found"
        }

    inventory = (
        db.query(Inventory)
        .filter(Inventory.client_id == client.id)
        .first()
    )

    if inventory is None:
        inventory = Inventory(client_id=client.id)
        db.add(inventory)

    inventory.username = username
    inventory.os_version = os_version
    inventory.cpu = cpu
    inventory.ram_gb = ram_gb
    inventory.manufacturer = manufacturer
    inventory.model = model
    inventory.serial_number = serial_number
    inventory.mac = mac
    inventory.uptime_seconds = uptime_seconds
    inventory.disks_json = disks_json
    inventory.updated_at = datetime.utcnow()

    db.commit()
    db.close()

    return {
        "status": "ok",
        "rustdesk_id": rustdesk_id
    }


@router.post("/api/agent/professional-inventory")
def receive_professional_inventory(
    machine_uuid: str = Form(""),
    rustdesk_id: str = Form(""),
    software_json: str = Form("[]"),
    hotfixes_json: str = Form("[]"),
    security_json: str = Form("{}"),
    firmware_json: str = Form("{}"),
    devices_json: str = Form("{}"),
    _: None = Depends(require_agent_key),
):
    db = SessionLocal()

    client = (
        db.query(Client)
        .filter(
            (Client.machine_uuid == machine_uuid)
            if machine_uuid
            else (Client.rustdesk_id == rustdesk_id)
        )
        .first()
    )

    if client is None:
        db.close()
        return {
            "status": "error",
            "detail": "client not found",
        }

    record = (
        db.query(ProfessionalInventory)
        .filter(ProfessionalInventory.client_id == client.id)
        .first()
    )

    if record is None:
        record = ProfessionalInventory(client_id=client.id)
        db.add(record)

    record.software_json = software_json
    record.hotfixes_json = hotfixes_json
    record.security_json = security_json
    record.firmware_json = firmware_json
    record.devices_json = devices_json
    record.updated_at = datetime.utcnow()

    db.commit()
    db.close()

    return {
        "status": "ok",
        "client_id": client.id,
    }


@router.get("/inventory", response_class=HTMLResponse)
def inventory_page(request: Request):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

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
        name="inventory.html",
        context={"rows": rows}
    )


@router.get("/inventory/{client_id}", response_class=HTMLResponse)
def inventory_detail(request: Request, client_id: int):
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)

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

    professional = (
        db.query(ProfessionalInventory)
        .filter(ProfessionalInventory.client_id == client_id)
        .first()
    )

    disks = []
    software = []
    hotfixes = []
    security = {}
    firmware = {}
    devices = {}

    if inventory and inventory.disks_json:
        try:
            disks = json.loads(inventory.disks_json)
        except json.JSONDecodeError:
            disks = []

    if professional:
        try:
            software = json.loads(professional.software_json or "[]")
        except json.JSONDecodeError:
            software = []

        try:
            hotfixes = json.loads(professional.hotfixes_json or "[]")
        except json.JSONDecodeError:
            hotfixes = []

        try:
            security = json.loads(professional.security_json or "{}")
        except json.JSONDecodeError:
            security = {}

        try:
            firmware = json.loads(professional.firmware_json or "{}")
        except json.JSONDecodeError:
            firmware = {}

        try:
            devices = json.loads(professional.devices_json or "{}")
        except json.JSONDecodeError:
            devices = {}

    db.close()

    if client is None:
        return RedirectResponse("/inventory", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="inventory_detail.html",
        context={
            "client": client,
            "inventory": inventory,
            "professional": professional,
            "disks": disks,
            "software": software,
            "hotfixes": hotfixes,
            "security": security,
            "firmware": firmware,
            "devices": devices,
        }
    )
