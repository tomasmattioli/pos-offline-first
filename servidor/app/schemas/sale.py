from pydantic import BaseModel, Field
from decimal import Decimal
from typing import List
from datetime import datetime

class SaleDetailCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)


class SaleDetailOut(BaseModel):
    product_id: int
    quantity: Decimal
    unit_price: Decimal

    class Config:
        from_attributes = True

        
class SaleCreate(BaseModel):
    user_id: int
    cash_register_id: int
    items: List[SaleDetailCreate] = Field(min_length=1)

class SaleOut(BaseModel):
    id: int
    user_id: int
    cash_register_id: int
    items: List[SaleDetailOut]
    total: Decimal
    time: datetime

    class Config:
        from_attributes = True

