from datetime import datetime
from pydantic import BaseModel


class TransactionCreate(BaseModel):
    item_id: int | None = None
    transaction_type: str
    quantity: float = 0.0
    unit_price: float = 0.0
    reference: str | None = None


class TransactionOut(BaseModel):
    id: int
    item_id: int | None = None
    item_name: str | None = None
    transaction_type: str
    quantity: float
    unit: str
    unit_price: float
    reference: str | None = None
    transaction_date: datetime

    class Config:
        from_attributes = True
