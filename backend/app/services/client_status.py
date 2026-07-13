from datetime import datetime, timedelta
from app.models.client import Client

OFFLINE_AFTER_SECONDS = 90

def refresh_client_statuses(db) -> int:
    threshold = datetime.utcnow() - timedelta(seconds=OFFLINE_AFTER_SECONDS)
    updated = (
        db.query(Client)
        .filter(Client.online == True, Client.last_seen < threshold)
        .update({Client.online: False}, synchronize_session=False)
    )
    if updated:
        db.commit()
    return updated
