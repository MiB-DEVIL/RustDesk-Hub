from fastapi import Header, HTTPException

from app.database.database import SessionLocal
from app.services.settings_service import get_settings_dict


def require_agent_key(x_agent_key: str = Header(default="")) -> None:
    db = SessionLocal()
    try:
        settings = get_settings_dict(db)
        expected = settings.get("agent_api_key", "OpenDeskAgent2026")
    finally:
        db.close()

    if not x_agent_key or x_agent_key != expected:
        raise HTTPException(status_code=401, detail="Clé Agent invalide")
