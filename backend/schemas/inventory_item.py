from datetime import datetime
from pydantic import BaseModel


class InventoryItemCreate(BaseModel):
    category_id: int | None = None
    name: str
    sku: str | None = None
    barcode: str | None = None
    quantity: float = 0.0
    unit: str = "units"
    cost_per_unit: float = 0.0
    expiry_date: datetime | None = None
    storage_location: str | None = None
    supplier: str | None = None
    notes: str | None = None


class InventoryItemUpdate(BaseModel):
    category_id: int | None = None
    name: str | None = None
    sku: str | None = None
    barcode: str | None = None
    quantity: float | None = None
    unit: str | None = None
    cost_per_unit: float | None = None
    expiry_date: datetime | None = None
    storage_location: str | None = None
    supplier: str | None = None
    notes: str | None = None


class InventoryItemOut(BaseModel):
    id: int
    category_id: int | None = None
    category_name: str | None = None
    perishability_risk: str | None = None
    name: str
    sku: str | None = None
    barcode: str | None = None
    quantity: float
    unit: str
    cost_per_unit: float
    expiry_date: datetime | None = None
    days_to_expiry: int | None = None
    storage_location: str | None = None
    supplier: str | None = None
    notes: str | None = None
    is_surplus_listed: bool
    risk_score: float = 0.0
    risk_level: str = "low"
    created_at: datetime | None = None

    class Config:
        from_attributes = True
