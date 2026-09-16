from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

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
