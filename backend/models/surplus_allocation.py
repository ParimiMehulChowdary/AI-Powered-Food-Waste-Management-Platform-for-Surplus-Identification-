from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, String, ForeignKey

from database import Base


class SurplusAllocation(Base):
    """Recommended allocation of predicted surplus food."""

    __tablename__ = "surplus_allocations"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    item_id = Column(Integer, index=True, nullable=False)
    item_name = Column(String, nullable=True)
    surplus_quantity = Column(Float, default=0.0)
    safe_period_days = Column(Integer, default=0)
    urgency = Column(Integer, default=3)  # 1 (highest) - 5 (lowest)
    allocation_type = Column(String, default="donation")  # donation | promotion | transfer
    suggested_partner = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending | actioned | dismissed
    created_at = Column(DateTime, default=datetime.utcnow)