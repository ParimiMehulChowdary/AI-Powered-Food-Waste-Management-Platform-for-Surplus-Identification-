from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey

from database import Base


class BusinessSettings(Base):
    __tablename__ = "business_settings"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    low_stock_threshold = Column(Float, default=5.0)
    expiry_alert_days = Column(Integer, default=3)
    shelf_life_breach_enabled = Column(Integer, default=1)
    low_stock_alert_enabled = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
