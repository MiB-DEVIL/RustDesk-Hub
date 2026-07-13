from datetime import datetime, timedelta

from app.models.agent_action import AgentAction
from app.models.client import Client
from app.models.event_log import EventLog
from app.services.settings_service import get_settings_dict


def build_notification_snapshot(db):
    settings = get_settings_dict(db)

    try:
        stale_minutes = max(1, int(settings.get("notification_stale_minutes", "10")))
    except (TypeError, ValueError):
        stale_minutes = 10

    try:
        error_hours = max(1, int(settings.get("notification_error_hours", "24")))
    except (TypeError, ValueError):
        error_hours = 24

    now = datetime.utcnow()
    stale_limit = now - timedelta(minutes=stale_minutes)
    recent_error_limit = now - timedelta(hours=error_hours)

    clients = db.query(Client).order_by(Client.name.asc()).all()
    recent_errors = (
        db.query(EventLog)
        .filter(
            EventLog.level.in_(["ERROR", "WARNING"]),
            EventLog.created_at >= recent_error_limit,
        )
        .order_by(EventLog.created_at.desc())
        .limit(50)
        .all()
    )


    failed_tasks = (
        db.query(AgentAction, Client)
        .join(Client, Client.id == AgentAction.client_id)
        .filter(
            AgentAction.status == "failed",
            AgentAction.created_at >= recent_error_limit,
        )
        .order_by(AgentAction.created_at.desc())
        .limit(20)
        .all()
    )

    blocked_limit = now - timedelta(minutes=5)
    blocked_tasks = (
        db.query(AgentAction, Client)
        .join(Client, Client.id == AgentAction.client_id)
        .filter(
            AgentAction.status == "running",
            AgentAction.started_at.isnot(None),
            AgentAction.started_at < blocked_limit,
        )
        .order_by(AgentAction.started_at.asc())
        .all()
    )

    alerts = []

    for client in clients:
        if not client.active:
            continue

        if not client.last_seen or client.last_seen < stale_limit:
            alerts.append({
                "severity": "critical",
                "title": f"{client.name} ne répond plus",
                "message": f"Aucun heartbeat reçu depuis plus de {stale_minutes} minute(s).",
                "client_id": client.id,
                "created_at": client.last_seen,
            })

        if not client.agent_version:
            alerts.append({
                "severity": "warning",
                "title": f"Version Agent inconnue — {client.name}",
                "message": "La machine n’a pas encore envoyé sa version d’Agent.",
                "client_id": client.id,
                "created_at": client.last_seen,
            })

        if not client.machine_uuid:
            alerts.append({
                "severity": "warning",
                "title": f"Identité incomplète — {client.name}",
                "message": "Aucun UUID permanent n’est associé à cette machine.",
                "client_id": client.id,
                "created_at": client.last_seen,
            })

    for row in recent_errors:
        matched_client = next(
            (
                client
                for client in clients
                if client.rustdesk_id == row.rustdesk_id
                or (row.hostname and client.hostname == row.hostname)
            ),
            None,
        )

        alerts.append({
            "severity": "critical" if row.level == "ERROR" else "warning",
            "title": f"{row.level} — {row.event_type}",
            "message": row.message,
            "client_id": matched_client.id if matched_client else None,
            "created_at": row.created_at,
        })


    for action, client in failed_tasks:
        alerts.append({
            "severity": "critical",
            "title": f"Tâche échouée — {client.name}",
            "message": (
                action.error_message
                or action.result_message
                or f"Action {action.action_type} terminée en échec."
            ),
            "client_id": client.id,
            "task_uuid": action.action_uuid,
            "created_at": action.finished_at or action.created_at,
        })

    for action, client in blocked_tasks:
        alerts.append({
            "severity": "warning",
            "title": f"Tâche potentiellement bloquée — {client.name}",
            "message": (
                f"L’action {action.action_type} est en cours depuis plus de "
                "5 minutes."
            ),
            "client_id": client.id,
            "task_uuid": action.action_uuid,
            "created_at": action.started_at,
        })

    alerts.sort(
        key=lambda item: item.get("created_at") or datetime.min,
        reverse=True,
    )

    counts = {
        "critical": sum(1 for alert in alerts if alert["severity"] == "critical"),
        "warning": sum(1 for alert in alerts if alert["severity"] == "warning"),
        "total": len(alerts),
    }

    return {
        "alerts": alerts,
        "counts": counts,
        "generated_at": now,
        "stale_minutes": stale_minutes,
        "error_hours": error_hours,
    }
