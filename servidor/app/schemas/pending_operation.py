from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import List

class PendingOperationItem(BaseModel):
    product_id: int
    quantity: Decimal = Field(gt=0)

class PendingOperationPayload(BaseModel):
    user_id: int
    items: List[PendingOperationItem] = Field(min_length=1)

class PendingOperationCreate(BaseModel):
    cash_register_id: int
    occurred_at: datetime
    operation_uuid: UUID
    payload: str

class PendingOperationOut(BaseModel):
    id: int
    status: str
    operation_uuid: UUID
    cash_register_id: int

    class Config:
        from_attributes = True

