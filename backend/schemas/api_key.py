from datetime import datetime
from pydantic import BaseModel


class ApiKeyCreate(BaseModel):
    label: str | None = None


class ApiKeyOut(BaseModel):
    id: int
    label: str | None = None
    key: str | None = None
    is_active: bool
    created_at: datetime | None = None

    class Config:
        from_attributes = True