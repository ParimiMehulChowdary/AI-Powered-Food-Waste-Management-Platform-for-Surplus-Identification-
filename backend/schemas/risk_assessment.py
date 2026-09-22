from datetime import datetime
from pydantic import BaseModel


class RiskFactor(BaseModel):
    factor: str
    value: str
    detail: str


class RiskAssessmentOut(BaseModel):
    id: int
    item_id: int
    item_name: str | None = None
    category_id: int | None = None
    risk_score: float = 0.0
    risk_level: str = "low"
    factors: list = []
    explanation: str | None = None
    model_name: str = "risk_engine_v2"
    model_version: str = "2.0.0"
    created_at: datetime | None = None

    class Config:
        from_attributes = True