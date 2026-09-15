from sqlalchemy import Column, Integer, String, Numeric
from app.database import Base

class CashRegister(Base):
    __tablename__ = "cash_registers"

    id = Column(Integer, primary_key= True)
    name = Column(String(50), nullable=False, unique=True)

def __repr__(self):
    return f"<CashRegister {self.name}>"
