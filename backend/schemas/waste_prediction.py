from datetime import datetime
from pydantic import BaseModel


class WastePredictionOut(BaseModel):
    id: int
    owner_id: int
    item_id: int
    item_name: str | None = None
    category_id: int | None = None
    prediction_date: datetime | None = None
    target_date: datetime
    predicted_demand: float = 0.0
    predicted_sales: float = 0.0
    predicted_surplus: float = 0.0
    predicted_waste: float = 0.0
    waste_probability: float = 0.0
    waste_risk_level: str = "low"
    expected_waste_value: float = 0.0
    expected_waste_pct: float = 0.0
    confidence: float = 0.0
    model_name: str = "rule_based_fallback"
    model_version: str = "1.0.0"
    is_fallback: bool = False
    method: str | None = None

    class Config:
        from_attributes = True


class ForecastSummary(BaseModel):
    item_id: int
    item_name: str | None = None
    predicted_demand: float = 0.0
    predicted_waste: float = 0.0
    predicted_surplus: float = 0.0
    waste_probability: float = 0.0
    confidence: float = 0.0
    model_name: str = "rule_based_fallback"
    is_fallback: bool = False


class WastePredictByItemPayload(BaseModel):
    item_id: int | None = None
    horizon_days: int = 7