from app.models.setting import Setting

DEFAULT_SETTINGS = {
    "organization_name": "OpenDesk Hub",
    "heartbeat_interval": "30",
    "address_book_interval": "300",
    "inventory_interval": "86400",
    "agent_api_key": "OpenDeskAgent2026",
    "debug_mode": "false",
    "inventory_enabled": "true",
    "address_book_enabled": "true",
    "notification_stale_minutes": "10",
    "notification_error_hours": "24",
}

def ensure_default_settings(db):
    changed=False
    for key,value in DEFAULT_SETTINGS.items():
        existing=db.query(Setting).filter(Setting.key==key).first()
        if existing is None:
            db.add(Setting(key=key,value=value)); changed=True
    if changed: db.commit()

def get_settings_dict(db):
    ensure_default_settings(db)
    return {row.key:row.value for row in db.query(Setting).all()}

def set_setting(db,key,value):
    row=db.query(Setting).filter(Setting.key==key).first()
    if row is None:
        db.add(Setting(key=key,value=value))
    else:
        row.value=value
    db.commit()
