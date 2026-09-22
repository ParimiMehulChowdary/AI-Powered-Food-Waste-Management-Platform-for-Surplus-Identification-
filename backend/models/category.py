from sqlalchemy import Column, Integer, String, Float, ForeignKey

from database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    perishability_risk = Column(String, default="medium")  # low | medium | high
    storage_requirement = Column(String, default="ambient")  # ambient | chilled | frozen
    default_shelf_life_days = Column(Integer, default=7)
    waste_risk_weight = Column(Float, default=1.0)
