from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text
from app.database.database import Base

class EventLog(Base):
    __tablename__ = "event_logs"
    id = Column(Integer, primary_key=True, index=True)
    rustdesk_id = Column(String, default="")
    hostname = Column(String, default="")
    level = Column(String, default="INFO")
    event_type = Column(String, default="agent")
    message = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
