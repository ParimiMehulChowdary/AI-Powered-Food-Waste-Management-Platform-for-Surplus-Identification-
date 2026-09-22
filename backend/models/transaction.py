from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, String, ForeignKey

from database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    item_id = Column(Integer, nullable=True)
    item_name = Column(String, nullable=True)
    transaction_type = Column(String, nullable=False)  # purchase | sale | donation | disposal | adjustment
    quantity = Column(Float, default=0.0)
    unit = Column(String, default="units")
    unit_price = Column(Float, default=0.0)
    reference = Column(String, nullable=True)
    transaction_date = Column(DateTime, default=datetime.utcnow)
