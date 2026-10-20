from sqlalchemy import Column, Integer, String
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    barcode = Column(String(50), nullable=True)
    price = Column(String, nullable=False)
    stock = Column(String, nullable=False)
