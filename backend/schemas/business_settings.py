from pydantic import BaseModel


class BusinessSettingsUpdate(BaseModel):
    low_stock_threshold: float | None = None
    expiry_alert_days: int | None = None
    shelf_life_breach_enabled: int | None = None
    low_stock_alert_enabled: int | None = None


class BusinessSettingsOut(BaseModel):
    id: int
    owner_id: int
    low_stock_threshold: float
    expiry_alert_days: int
    shelf_life_breach_enabled: int
    low_stock_alert_enabled: int

    class Config:
        from_attributes = True
