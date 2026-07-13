from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text

from app.database.database import Base


class ProfessionalInventory(Base):
    __tablename__ = "professional_inventories"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(
        Integer,
        ForeignKey("clients.id"),
        unique=True,
        nullable=False,
        index=True,
    )
    software_json = Column(Text, default="[]")
    hotfixes_json = Column(Text, default="[]")
    security_json = Column(Text, default="{}")
    firmware_json = Column(Text, default="{}")
    devices_json = Column(Text, default="{}")
    updated_at = Column(DateTime, default=datetime.utcnow, index=True)
