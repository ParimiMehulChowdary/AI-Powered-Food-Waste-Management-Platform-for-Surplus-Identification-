from datetime import datetime
from pydantic import BaseModel


class WasteAlertOut(BaseModel):
    id: int
    item_id: int | None = None
    item_name: str | None = None
    alert_type: str
    risk_score: float
    days_to_expiry: int
    message: str | None = None
    is_resolved: bool
    created_at: datetime | None = None

    class Config:
        from_attributes = True
