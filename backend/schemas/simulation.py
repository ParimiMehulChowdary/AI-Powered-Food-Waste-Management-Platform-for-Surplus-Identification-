from datetime import datetime
from pydantic import BaseModel


class SimulationOut(BaseModel):
    id: int
    item_id: int | None = None
    item_name: str | None = None
    input_parameters: dict = {}
    results: dict = {}
    created_at: datetime | None = None

    class Config:
        from_attributes = True