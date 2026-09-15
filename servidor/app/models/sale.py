from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from app.database import Base

class Sale(Base):
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    cash_register_id = Column(Integer, ForeignKey("cash_registers.id"), nullable=False)
    time = Column(DateTime, nullable=False)
    total = Column(Numeric(10, 2), nullable=False)
