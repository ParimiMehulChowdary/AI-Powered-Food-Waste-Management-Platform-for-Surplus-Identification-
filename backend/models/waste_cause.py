from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, String, ForeignKey

from database import Base


class WasteCause(Base):
    """Identified cause of waste for an item over a period (rule-based classification)."""

    __tablename__ = "waste_causes"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    item_id = Column(Integer, index=True, nullable=False)
    item_name = Column(String, nullable=True)
    cause = Column(String, nullable=False)
    explanation = Column(String, nullable=True)
    confidence = Column(Float, default=0.0)
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)