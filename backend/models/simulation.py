from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, String, ForeignKey, JSON

from database import Base


class Simulation(Base):
    """Saved what-if simulation run."""

    __tablename__ = "simulations"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    user_id = Column(Integer, nullable=True)
    item_id = Column(Integer, nullable=True)
    item_name = Column(String, nullable=True)
    input_parameters = Column(JSON, default=dict)
    results = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)