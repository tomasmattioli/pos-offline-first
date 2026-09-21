from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.pendig_operation import PendingOperation
from app.schemas.pending_operation import PendingOperationCreate, PendingOperationOut

router = APIRouter()

@router.post("/pending_operations", response_model= PendingOperationOut)
def create_pending_operation(operation: PendingOperationCreate, db: Session = Depends(get_db)):
    existing = db.query(PendingOperation).filter(PendingOperation.operation_uuid == operation.operation_uuid).first()
    if existing:
        return existing
    new_operation = PendingOperation(operation_uuid = operation.operation_uuid, cash_register_id = operation.cash_register_id, payload = operation.payload, occurred_at = operation.occurred_at)
    db.add(new_operation)
    db.commit()
    db.refresh(new_operation)
    return new_operation
    