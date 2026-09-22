from datetime import datetime
from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: int
    item_id: int | None = None
    item_name: str | None = None
    notification_type: str
    severity: str = "medium"
    message: str | None = None
    source_ref: str | None = None
    is_read: bool = False
    created_at: datetime | None = None

    class Config:
        from_attributes = True