from datetime import datetime
from pydantic import BaseModel


class WasteCauseOut(BaseModel):
    id: int
    item_id: int
    item_name: str | None = None
    cause: str
    explanation: str | None = None
    confidence: float = 0.0
    period_start: datetime | None = None
    period_end: datetime | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True