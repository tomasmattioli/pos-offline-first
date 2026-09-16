from pydantic import BaseModel
from decimal import Decimal
from typing import List
from datetime import datetime

class SaleDetailCreate(BaseModel):
    product_id: int
    quantity: Decimal


class SaleDetailOut(BaseModel):
    product_id: int
    quantity: Decimal
    unit_price: Decimal

    class Config:
        from_attributes = True

        
class SaleCreate(BaseModel):
    user_id: int
    cash_register_id: int
    items: List[SaleDetailCreate]

class SaleOut(BaseModel):
    id: int
    user_id: int
    cash_register_id: int
    items: List[SaleDetailOut]
    total: Decimal
    time: datetime

    class Config:
        from_attributes = True

