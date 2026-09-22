from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, String, ForeignKey, JSON

from database import Base


class RiskAssessment(Base):
    """Latest explainable waste-risk assessment per product."""

    __tablename__ = "risk_assessments"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    item_id = Column(Integer, index=True, nullable=False)
    item_name = Column(String, nullable=True)
    category_id = Column(Integer, nullable=True)
    risk_score = Column(Float, default=0.0)
    risk_level = Column(String, default="low")  # low | moderate | high | critical
    factors = Column(JSON, default=list)  # list of {factor, value, detail}
    explanation = Column(String, nullable=True)
    model_name = Column(String, default="risk_engine_v2")
    model_version = Column(String, default="2.0.0")
    thresholds = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)