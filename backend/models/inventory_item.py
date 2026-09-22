from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text

from database import Base


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    name = Column(String, nullable=False)
    sku = Column(String, nullable=True, index=True)
    barcode = Column(String, nullable=True, index=True)
    quantity = Column(Float, default=0.0)
    unit = Column(String, default="units")
    cost_per_unit = Column(Float, default=0.0)
    expiry_date = Column(DateTime, nullable=True)
    storage_location = Column(String, nullable=True)
    supplier = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    is_surplus_listed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
