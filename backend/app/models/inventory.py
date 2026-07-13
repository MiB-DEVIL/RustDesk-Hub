from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from datetime import datetime

from app.database.database import Base


class Inventory(Base):
    __tablename__ = "inventories"

    id = Column(Integer, primary_key=True, index=True)

    client_id = Column(
        Integer,
        ForeignKey("clients.id"),
        unique=True,
        nullable=False
    )

    username = Column(String, default="")
    os_version = Column(String, default="")
    cpu = Column(String, default="")
    ram_gb = Column(String, default="")
    manufacturer = Column(String, default="")
    model = Column(String, default="")
    serial_number = Column(String, default="")
    mac = Column(String, default="")
    uptime_seconds = Column(Integer, default=0)
    disks_json = Column(Text, default="[]")
    updated_at = Column(DateTime, default=datetime.utcnow)
