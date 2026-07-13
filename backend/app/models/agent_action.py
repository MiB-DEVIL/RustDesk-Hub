from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.database.database import Base


class AgentAction(Base):
    __tablename__ = "agent_actions"

    id = Column(Integer, primary_key=True, index=True)
    action_uuid = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    action_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="pending", index=True)
    requested_by = Column(String, nullable=False, default="admin")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    result_message = Column(Text, nullable=False, default="")
    result_data = Column(Text, nullable=False, default="")
    error_message = Column(Text, nullable=False, default="")
