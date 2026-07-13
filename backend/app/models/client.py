from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.database.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    rustdesk_id = Column(String, unique=True, nullable=False)
    machine_uuid = Column(String, unique=True, nullable=True, index=True)
    bios_serial = Column(String, default="")
    motherboard_serial = Column(String, default="")
    primary_mac = Column(String, default="")
    agent_version = Column(String, default="")
    group_name = Column(String, default="Clients")
    notes = Column(String, default="")
    active = Column(Boolean, default=True)
    hostname = Column(String, default="")
    os = Column(String, default="")
    ip = Column(String, default="")
    version = Column(String, default="")
    online = Column(Boolean, default=False)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
