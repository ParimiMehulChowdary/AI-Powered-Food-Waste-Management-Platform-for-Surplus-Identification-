from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, String, ForeignKey

from database import Base


class ForecastPerformance(Base):
    """Forecast vs actual accuracy metrics computed weekly per item / model."""

    __tablename__ = "forecast_performance"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    item_id = Column(Integer, index=True, nullable=False)
    item_name = Column(String, nullable=True)
    model_name = Column(String, default="total")
    mae = Column(Float, nullable=True)
    rmse = Column(Float, nullable=True)
    mape = Column(Float, nullable=True)  # percent
    accuracy = Column(Float, nullable=True)  # percent 0-100
    samples = Column(Integer, default=0)
    window_start = Column(DateTime, nullable=True)
    window_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)