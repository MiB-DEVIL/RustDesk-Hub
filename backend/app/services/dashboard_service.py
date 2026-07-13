from datetime import datetime, timedelta
import json

from app.models.agent_action import AgentAction
from app.models.client import Client
from app.models.event_log import EventLog
from app.models.group import Group
from app.models.inventory import Inventory
from app.models.user import User
from app.services.client_status import refresh_client_statuses


def _iso(value):
    return value.isoformat() if value else None


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _disk_summary(inventory):
    if not inventory:
        return {
            "count": 0,
            "total_gb": 0,
            "free_gb": 0,
            "used_percent": 0,
            "critical": False,
        }

    try:
        disks = json.loads(inventory.disks_json or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        disks = []

    if not isinstance(disks, list):
        disks = []

    total = 0.0
    free = 0.0

    for disk in disks:
        if not isinstance(disk, dict):
            continue
        total += _safe_float(disk.get("size_gb"))
        free += _safe_float(disk.get("free_gb"))

    used_percent = 0.0
    if total > 0:
        used_percent = round(((total - free) / total) * 100, 1)

    return {
        "count": len(disks),
        "total_gb": round(total, 1),
        "free_gb": round(free, 1),
        "used_percent": used_percent,
        "critical": bool(total > 0 and used_percent >= 90),
    }


def build_dashboard_snapshot(db):
    refresh_client_statuses(db)

    client_inventory_rows = (
        db.query(Client, Inventory)
        .outerjoin(Inventory, Inventory.client_id == Client.id)
        .order_by(Client.last_seen.desc())
        .all()
    )
    clients = [client for client, _ in client_inventory_rows]

    recent_events = (
        db.query(EventLog)
        .order_by(EventLog.created_at.desc())
        .limit(12)
        .all()
    )

    recent_tasks = (
        db.query(AgentAction, Client)
        .join(Client, Client.id == AgentAction.client_id)
        .order_by(AgentAction.created_at.desc())
        .limit(8)
        .all()
    )

    now = datetime.utcnow()
    stale_inventory_limit = now - timedelta(days=2)
    offline_long_limit = now - timedelta(hours=24)

    online = [client for client in clients if client.online]
    offline = [client for client in clients if not client.online]
    missing_agent_version = [
        client
        for client in online
        if not (client.agent_version or "").strip()
    ]

    stale_inventory = []
    disk_alerts = []
    long_offline = []
    total_disk_gb = 0.0
    total_free_gb = 0.0
    total_ram_gb = 0.0
    inventory_count = 0

    inventory_by_client = {}

    for client, inventory in client_inventory_rows:
        inventory_by_client[client.id] = inventory

        if inventory:
            inventory_count += 1
            total_ram_gb += _safe_float(inventory.ram_gb)

            disk = _disk_summary(inventory)
            total_disk_gb += disk["total_gb"]
            total_free_gb += disk["free_gb"]

            if disk["critical"]:
                disk_alerts.append(
                    {
                        "client_id": client.id,
                        "machine": client.name,
                        "used_percent": disk["used_percent"],
                        "free_gb": disk["free_gb"],
                    }
                )

            if (
                not inventory.updated_at
                or inventory.updated_at < stale_inventory_limit
            ):
                stale_inventory.append(
                    {
                        "client_id": client.id,
                        "machine": client.name,
                        "updated_at": _iso(inventory.updated_at),
                    }
                )
        else:
            stale_inventory.append(
                {
                    "client_id": client.id,
                    "machine": client.name,
                    "updated_at": None,
                }
            )

        if (
            not client.online
            and client.last_seen
            and client.last_seen < offline_long_limit
        ):
            long_offline.append(
                {
                    "client_id": client.id,
                    "machine": client.name,
                    "last_seen": _iso(client.last_seen),
                }
            )

    failed_24h = (
        db.query(AgentAction)
        .filter(
            AgentAction.status == "failed",
            AgentAction.created_at >= now - timedelta(hours=24),
        )
        .count()
    )

    success_24h = (
        db.query(AgentAction)
        .filter(
            AgentAction.status == "success",
            AgentAction.created_at >= now - timedelta(hours=24),
        )
        .count()
    )

    completed_24h = success_24h + failed_24h
    success_rate_24h = (
        round((success_24h / completed_24h) * 100, 1)
        if completed_24h else 0
    )

    alert_count = (
        len(missing_agent_version)
        + len(stale_inventory)
        + len(disk_alerts)
        + len(long_offline)
        + failed_24h
    )

    fleet_health = 100
    if clients:
        weighted_penalty = (
            len(offline) * 20
            + len(stale_inventory) * 8
            + len(disk_alerts) * 12
            + len(missing_agent_version) * 5
        )
        fleet_health = max(
            0,
            round(100 - (weighted_penalty / len(clients)), 0),
        )

    used_disk_percent = 0.0
    if total_disk_gb > 0:
        used_disk_percent = round(
            ((total_disk_gb - total_free_gb) / total_disk_gb) * 100,
            1,
        )

    recent_clients = []
    for client in clients[:10]:
        inventory = inventory_by_client.get(client.id)
        disk = _disk_summary(inventory)

        health = "critical" if not client.online else "healthy"
        health_label = "Hors ligne" if not client.online else "Sain"

        if client.online and (
            not (client.agent_version or "").strip()
            or not inventory
            or (
                inventory.updated_at
                and inventory.updated_at < stale_inventory_limit
            )
            or disk["critical"]
        ):
            health = "warning"
            health_label = "Attention"

        recent_clients.append(
            {
                "id": client.id,
                "name": client.name,
                "hostname": client.hostname or "-",
                "rustdesk_id": client.rustdesk_id,
                "group_name": client.group_name or "-",
                "online": bool(client.online),
                "health": health,
                "health_label": health_label,
                "agent_version": client.agent_version or "-",
                "last_seen": _iso(client.last_seen),
                "ram_gb": (
                    inventory.ram_gb
                    if inventory and inventory.ram_gb
                    else "-"
                ),
                "disk_used_percent": disk["used_percent"],
            }
        )

    events = [
        {
            "id": event.id,
            "created_at": _iso(event.created_at),
            "hostname": event.hostname or event.rustdesk_id or "Hub",
            "level": event.level or "INFO",
            "event_type": event.event_type or "system",
            "message": event.message or "",
        }
        for event in recent_events
    ]

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "stats": {
            "clients": len(clients),
            "groups": db.query(Group).count(),
            "users": db.query(User).count(),
            "online": len(online),
            "offline": len(offline),
            "warnings": alert_count,
            "fleet_health": fleet_health,
            "inventory_coverage": (
                round((inventory_count / len(clients)) * 100, 1)
                if clients else 0
            ),
            "ram_gb": round(total_ram_gb, 1),
            "disk_total_gb": round(total_disk_gb, 1),
            "disk_free_gb": round(total_free_gb, 1),
            "disk_used_percent": used_disk_percent,
            "success_rate_24h": success_rate_24h,
            "failed_24h": failed_24h,
        },
        "alerts": {
            "stale_inventory": stale_inventory[:8],
            "disk": disk_alerts[:8],
            "long_offline": long_offline[:8],
            "missing_agent_version": [
                {
                    "client_id": client.id,
                    "machine": client.name,
                }
                for client in missing_agent_version[:8]
            ],
        },
        "clients": recent_clients,
        "events": events,
        "tasks": {
            "counters": {
                "pending": db.query(AgentAction)
                .filter(AgentAction.status == "pending")
                .count(),
                "running": db.query(AgentAction)
                .filter(AgentAction.status == "running")
                .count(),
                "success": db.query(AgentAction)
                .filter(AgentAction.status == "success")
                .count(),
                "failed": db.query(AgentAction)
                .filter(AgentAction.status == "failed")
                .count(),
            },
            "recent": [
                {
                    "uuid": action.action_uuid,
                    "machine": client.name,
                    "action_type": action.action_type,
                    "status": action.status,
                    "created_at": _iso(action.created_at),
                }
                for action, client in recent_tasks
            ],
        },
    }
