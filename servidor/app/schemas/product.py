from pydantic import BaseModel
from typing import Optional
from decimal import Decimal

class ProductCreate(BaseModel):
    name: str
    price: Decimal
    stock: Optional[Decimal] = 0
    barcode: Optional[str] = None

class ProductOut(BaseModel):
    id: int
    name: str
    price: Decimal
    stock: Decimal
    barcode: Optional[str] = None
    
    class Config:
        from_attributes = True



