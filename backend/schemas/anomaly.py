from datetime import datetime
from pydantic import BaseModel


class AnomalyOut(BaseModel):
    id: int
    item_id: int | None = None
    item_name: str | None = None
    anomaly_type: str
    severity: str = "medium"
    detected_value: float = 0.0
    expected_value: float = 0.0
    expected_low: float | None = None
    expected_high: float | None = None
    explanation: str | None = None
    method: str | None = None
    is_resolved: bool = False
    detected_at: datetime | None = None

    class Config:
        from_attributes = True