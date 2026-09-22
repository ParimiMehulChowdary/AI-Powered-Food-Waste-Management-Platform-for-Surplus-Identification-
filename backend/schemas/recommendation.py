from datetime import datetime
from pydantic import BaseModel


class RecommendationOut(BaseModel):
    id: int
    item_id: int
    item_name: str | None = None
    recommendation_type: str
    recommended_quantity: float = 0.0
    priority: int = 3
    reason: str | None = None
    expected_benefit: float = 0.0
    deadline: datetime | None = None
    status: str = "pending"
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class RecommendationStatusUpdate(BaseModel):
    status: str  # applied | rejected | expired