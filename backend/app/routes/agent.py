from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.database.database import SessionLocal
from app.services.identity_service import upsert_heartbeat


router = APIRouter()


@router.post("/api/agent/heartbeat")
def agent_heartbeat(
    machine_uuid: str = Form(...),
    rustdesk_id: str = Form(...),
    hostname: str = Form(""),
    os: str = Form(""),
    ip: str = Form(""),
    version: str = Form(""),
    bios_serial: str = Form(""),
    motherboard_serial: str = Form(""),
    primary_mac: str = Form(""),
    agent_version: str = Form(""),
):
    db = SessionLocal()

    try:
        client = upsert_heartbeat(
            db,
            machine_uuid=machine_uuid,
            rustdesk_id=rustdesk_id,
            hostname=hostname,
            os_name=os,
            ip=ip,
            rustdesk_version=version,
            bios_serial=bios_serial,
            motherboard_serial=motherboard_serial,
            primary_mac=primary_mac,
            agent_version=agent_version,
        )
        return JSONResponse({
            "status": "ok",
            "client_id": client.id,
            "machine_uuid": client.machine_uuid,
            "rustdesk_id": client.rustdesk_id,
        })
    except (ValueError, IntegrityError) as exc:
        db.rollback()
        return JSONResponse(
            {"status": "error", "detail": str(exc)},
            status_code=409,
        )
    finally:
        db.close()
