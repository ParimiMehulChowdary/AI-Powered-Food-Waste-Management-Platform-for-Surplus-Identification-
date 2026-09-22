from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, String, Boolean, ForeignKey

from database import Base


class Notification(Base):
    """User-facing notification with severity and read/unread state."""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    item_id = Column(Integer, index=True, nullable=True)
    item_name = Column(String, nullable=True)
    notification_type = Column(String, nullable=False)
    severity = Column(String, default="medium")  # low | medium | high | critical
    message = Column(String, nullable=True)
    source_ref = Column(String, nullable=True)
    dedupe_key = Column(String, unique=True, index=True, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)