from sqlalchemy import Column, Integer, String, Boolean

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    business_name = Column(String, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    contact = Column(String, nullable=True)
    address = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="business")
    is_active = Column(Boolean, default=True)
