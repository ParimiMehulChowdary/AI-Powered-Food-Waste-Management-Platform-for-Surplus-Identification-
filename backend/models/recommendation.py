from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, String, ForeignKey

from database import Base


class Recommendation(Base):
    """Action recommendation produced by the recommendation engine."""

    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    item_id = Column(Integer, index=True, nullable=False)
    item_name = Column(String, nullable=True)
    recommendation_type = Column(String, nullable=False)
    recommended_quantity = Column(Float, default=0.0)
    priority = Column(Integer, default=3)  # 1 = most urgent ... 5 = least
    reason = Column(String, nullable=True)
    expected_benefit = Column(Float, default=0.0)  # estimated $ saved / recovered
    deadline = Column(DateTime, nullable=True)
    status = Column(String, default="pending")  # pending | applied | rejected | expired
    created_at = Column(DateTime, default=datetime.utcnow)