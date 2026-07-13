from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.machine_change import MachineChange


def _clean(value: Optional[str]) -> str:
    return (value or "").strip()


def _remember_change(db: Session, client: Client, field: str, old: str, new: str) -> None:
    if _clean(old) == _clean(new):
        return
    db.add(MachineChange(
        client_id=client.id,
        field_name=field,
        old_value=_clean(old),
        new_value=_clean(new),
    ))


def find_existing_client(
    db: Session,
    machine_uuid: str,
    rustdesk_id: str,
    hostname: str,
) -> Optional[Client]:
    machine_uuid = _clean(machine_uuid)
    rustdesk_id = _clean(rustdesk_id)
    hostname = _clean(hostname)

    if machine_uuid:
        client = db.query(Client).filter(Client.machine_uuid == machine_uuid).first()
        if client:
            return client

    if rustdesk_id:
        client = db.query(Client).filter(Client.rustdesk_id == rustdesk_id).first()
        if client:
            return client

    # Reprise prudente d'une fiche créée avant l'UUID : uniquement si le
    # hostname correspond à une seule fiche sans UUID.
    if hostname:
        candidates = (
            db.query(Client)
            .filter(Client.machine_uuid.is_(None))
            .all()
        )
        matches = [
            item for item in candidates
            if _clean(item.hostname).casefold() == hostname.casefold()
            or _clean(item.name).casefold() == hostname.casefold()
        ]
        if len(matches) == 1:
            return matches[0]

    return None


def upsert_heartbeat(
    db: Session,
    *,
    machine_uuid: str,
    rustdesk_id: str,
    hostname: str,
    os_name: str,
    ip: str,
    rustdesk_version: str,
    bios_serial: str,
    motherboard_serial: str,
    primary_mac: str,
    agent_version: str,
) -> Client:
    machine_uuid = _clean(machine_uuid)
    rustdesk_id = _clean(rustdesk_id)
    hostname = _clean(hostname)

    if not machine_uuid:
        raise ValueError("machine_uuid manquant")
    if not rustdesk_id:
        raise ValueError("rustdesk_id introuvable")

    client = find_existing_client(db, machine_uuid, rustdesk_id, hostname)

    if client is None:
        client = Client(
            name=hostname or rustdesk_id,
            machine_uuid=machine_uuid,
            rustdesk_id=rustdesk_id,
            group_name="Clients",
            first_seen=datetime.utcnow(),
        )
        db.add(client)
        db.flush()
    else:
        # L'UUID est désormais l'identité principale. Si RustDesk change,
        # l'ancienne valeur est remplacée sur la même fiche.
        if client.machine_uuid and client.machine_uuid != machine_uuid:
            raise ValueError("conflit d'identité machine")
        if not client.machine_uuid:
            client.machine_uuid = machine_uuid

    tracked = {
        "rustdesk_id": rustdesk_id,
        "hostname": hostname,
        "os": _clean(os_name),
        "ip": _clean(ip),
        "version": _clean(rustdesk_version),
        "bios_serial": _clean(bios_serial),
        "motherboard_serial": _clean(motherboard_serial),
        "primary_mac": _clean(primary_mac),
        "agent_version": _clean(agent_version),
    }

    for field, new_value in tracked.items():
        old_value = getattr(client, field, "") or ""
        _remember_change(db, client, field, str(old_value), new_value)
        setattr(client, field, new_value)

    if hostname and (not client.name or client.name == client.rustdesk_id):
        client.name = hostname

    client.online = True
    client.last_seen = datetime.utcnow()
    db.commit()
    db.refresh(client)
    return client
