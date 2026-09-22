from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, String, Boolean, ForeignKey

from database import Base


class Anomaly(Base):
    """Detected anomaly in sales / inventory / waste patterns."""

    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    item_id = Column(Integer, index=True, nullable=True)  # None = tenant/global level
    item_name = Column(String, nullable=True)
    anomaly_type = Column(String, nullable=False)  # sales_spike, sales_drop, demand_drop, demand_spike, stock_increase, stock_decrease, stock_accumulation, waste_spike, waste_pct_spike, product_waste_spike
    severity = Column(String, default="medium")  # low | medium | high | critical
    detected_value = Column(Float, default=0.0)
    expected_value = Column(Float, default=0.0)
    expected_low = Column(Float, nullable=True)
    expected_high = Column(Float, nullable=True)
    explanation = Column(String, nullable=True)
    method = Column(String, nullable=True)
    dedupe_key = Column(String, unique=True, index=True, nullable=False)
    is_resolved = Column(Boolean, default=False)
    detected_at = Column(DateTime, default=datetime.utcnow)