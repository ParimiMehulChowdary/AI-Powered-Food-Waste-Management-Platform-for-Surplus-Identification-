from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, String, Boolean, ForeignKey

from database import Base


class DonationPartner(Base):
    """Donation partner registry for surplus allocation (empty until added by the business)."""

    __tablename__ = "donation_partners"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    contact = Column(String, nullable=True)
    capacity = Column(Float, default=0.0)  # max quantity the partner can accept
    notes = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)