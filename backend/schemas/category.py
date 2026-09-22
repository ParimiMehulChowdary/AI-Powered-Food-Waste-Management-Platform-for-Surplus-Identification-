from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    description: str | None = None
    perishability_risk: str = "medium"
    storage_requirement: str = "ambient"
    default_shelf_life_days: int = 7
    waste_risk_weight: float = 1.0


class CategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    perishability_risk: str | None = None
    storage_requirement: str | None = None
    default_shelf_life_days: int | None = None
    waste_risk_weight: float | None = None


class CategoryOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    perishability_risk: str
    storage_requirement: str
    default_shelf_life_days: int
    waste_risk_weight: float
    item_count: int = 0

    class Config:
        from_attributes = True
