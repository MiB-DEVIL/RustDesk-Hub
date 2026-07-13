from datetime import datetime, timedelta
import json
import uuid

from sqlalchemy.orm import Session

from app.models.agent_action import AgentAction
from app.models.client import Client
from app.services.event_log_service import add_event_log


ALLOWED_ACTION_TYPES = {
    "agent_status": "État de l’Agent",
    "inventory_now": "Inventaire immédiat",
    "rustdesk_refresh": "Actualiser RustDesk",
    "network_test": "Test réseau",
    "system_health": "Santé système",
    "network_details": "Détails réseau",
    "process_check": "Vérification des processus",
    "disk_details": "Détails des disques",
    "windows_info": "Informations Windows",
    "dns_configuration": "Configuration DNS",
    "recent_system_errors": "Erreurs système récentes",
}

STALE_RUNNING_MINUTES = 5


def create_action(
    db: Session,
    client: Client,
    action_type: str,
    requested_by: str,
) -> AgentAction:
    if action_type not in ALLOWED_ACTION_TYPES:
        raise ValueError("Type d’action non autorisé")

    action = AgentAction(
        action_uuid=str(uuid.uuid4()),
        client_id=client.id,
        action_type=action_type,
        status="pending",
        requested_by=requested_by or "admin",
    )
    db.add(action)
    db.commit()
    db.refresh(action)

    add_event_log(
        db,
        rustdesk_id=client.rustdesk_id,
        hostname=client.hostname,
        level="INFO",
        event_type="action_created",
        message=f"Action {action_type} créée par {action.requested_by}",
    )
    return action


def claim_next_action(db: Session, client: Client):
    expire_stale_actions(db)

    action = (
        db.query(AgentAction)
        .filter(
            AgentAction.client_id == client.id,
            AgentAction.status == "pending",
        )
        .order_by(AgentAction.created_at.asc())
        .first()
    )
    if action is None:
        return None

    action.status = "running"
    action.started_at = datetime.utcnow()
    db.commit()
    db.refresh(action)
    return action


def finish_action(
    db: Session,
    action: AgentAction,
    client: Client,
    success: bool,
    message: str,
    data,
    error: str,
):
    action.status = "success" if success else "failed"
    action.finished_at = datetime.utcnow()
    action.result_message = message or ""
    action.result_data = json.dumps(data or {}, ensure_ascii=False)
    action.error_message = error or ""
    db.commit()
    db.refresh(action)

    add_event_log(
        db,
        rustdesk_id=client.rustdesk_id,
        hostname=client.hostname,
        level="INFO" if success else "ERROR",
        event_type="action_result",
        message=(
            f"Action {action.action_type} terminée : "
            f"{'succès' if success else 'échec'}"
        ),
    )
    return action


def cancel_action(
    db: Session,
    action: AgentAction,
    client: Client,
    requested_by: str,
) -> AgentAction:
    if action.status != "pending":
        raise ValueError("Seule une tâche en attente peut être annulée")

    action.status = "cancelled"
    action.finished_at = datetime.utcnow()
    action.result_message = f"Annulée par {requested_by or 'admin'}"
    action.error_message = ""
    db.commit()
    db.refresh(action)

    add_event_log(
        db,
        rustdesk_id=client.rustdesk_id,
        hostname=client.hostname,
        level="WARNING",
        event_type="action_cancelled",
        message=f"Action {action.action_type} annulée par {requested_by or 'admin'}",
    )
    return action


def retry_action(
    db: Session,
    action: AgentAction,
    client: Client,
    requested_by: str,
) -> AgentAction:
    if action.status not in {"failed", "cancelled"}:
        raise ValueError("Seule une tâche échouée ou annulée peut être relancée")

    return create_action(
        db,
        client=client,
        action_type=action.action_type,
        requested_by=requested_by,
    )


def expire_stale_actions(db: Session) -> int:
    limit = datetime.utcnow() - timedelta(minutes=STALE_RUNNING_MINUTES)

    stale = (
        db.query(AgentAction)
        .filter(
            AgentAction.status == "running",
            AgentAction.started_at.isnot(None),
            AgentAction.started_at < limit,
        )
        .all()
    )

    for action in stale:
        action.status = "failed"
        action.finished_at = datetime.utcnow()
        action.result_message = "Expiration automatique"
        action.error_message = (
            f"Aucun résultat reçu après {STALE_RUNNING_MINUTES} minutes"
        )

    if stale:
        db.commit()

    return len(stale)
