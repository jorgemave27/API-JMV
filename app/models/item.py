from __future__ import annotations

from sqlalchemy import Column, Integer, String, Float
from app.database.database import Base


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(String(500), nullable=True)
    price = Column(Float, nullable=False)
    sku = Column(String(50), nullable=True, unique=True, index=True)
    codigo_sku = Column(String(20), nullable=True, index=True)
    stock = Column(Integer, nullable=False, default=0)


