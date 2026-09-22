from datetime import datetime
from pydantic import BaseModel


class SurplusAllocationOut(BaseModel):
    id: int
    item_id: int
    item_name: str | None = None
    surplus_quantity: float = 0.0
    safe_period_days: int = 0
    urgency: int = 3
    allocation_type: str = "donation"
    suggested_partner: str | None = None
    reason: str | None = None
    status: str = "pending"
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class SurplusStatusUpdate(BaseModel):
    status: str  # actioned | dismissed


class DonationPartnerCreate(BaseModel):
    name: str
    contact: str | None = None
    capacity: float = 0.0
    notes: str | None = None


class DonationPartnerOut(BaseModel):
    id: int
    name: str
    contact: str | None = None
    capacity: float = 0.0
    notes: str | None = None
    is_active: bool = True
    created_at: datetime | None = None

    class Config:
        from_attributes = True