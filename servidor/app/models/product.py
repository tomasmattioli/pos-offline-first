from sqlalchemy import Column, Integer, String, Numeric
from app.database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key = True, index = True)
    name = Column(String(100), nullable = False)
    price = Column(Numeric(10, 2), nullable = False)
    stock = Column(Numeric(10, 3), nullable = False, default = 0)
    barcode = Column(String(50), unique = True, nullable = True, index = True)
    
def __repr__(self):
    return f"<Product {self.name} - stock_ {self.stock}>"