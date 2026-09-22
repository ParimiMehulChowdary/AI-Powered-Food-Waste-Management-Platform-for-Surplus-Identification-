from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, String, Boolean, ForeignKey

from database import Base


class WasteAlert(Base):
    __tablename__ = "waste_alerts"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    item_id = Column(Integer, nullable=True)
    item_name = Column(String, nullable=True)
    alert_type = Column(String, nullable=False)  # expiry_soon | shelf_life_breach | low_stock
    risk_score = Column(Float, default=0.0)
    days_to_expiry = Column(Integer, default=0)
    message = Column(String, nullable=True)
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
