from sqlalchemy import Column, Integer, String, Numeric, ForeignKey
from app.database import Base

class SaleDetail(Base):
    __tablename__ = "sale_details"

    id = Column(Integer, primary_key = True, index = True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable = False)

    def __repr__(self):
        return f"<Quantity {self.quantity} - Product {self.product_id}>"