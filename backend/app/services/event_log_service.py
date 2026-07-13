from app.models.event_log import EventLog

def add_event_log(db, rustdesk_id="", hostname="", level="INFO", event_type="agent", message=""):
    row=EventLog(rustdesk_id=rustdesk_id, hostname=hostname, level=(level or "INFO").upper(), event_type=event_type or "agent", message=message or "")
    db.add(row); db.commit(); db.refresh(row)
    return row
