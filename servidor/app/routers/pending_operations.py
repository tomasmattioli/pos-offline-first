from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.pendig_operation import PendingOperation
from app.schemas.pending_operation import PendingOperationCreate, PendingOperationOut
import json
from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_detail import SaleDetail
from app.models.user import User
from app.models.cash_register import CashRegister
router = APIRouter()

def save_operation(db: Session, operation: PendingOperationCreate, status: str) -> PendingOperation:
    new_operation = PendingOperation(operation_uuid = operation.operation_uuid, cash_register_id = operation.cash_register_id, payload = operation.payload, occurred_at = operation.occurred_at, status = status)
    db.add(new_operation)
    db.commit()
    db.refresh(new_operation)
    return new_operation
    
    
        
@router.post("/pending_operations", response_model= PendingOperationOut)
def create_pending_operation(operation: PendingOperationCreate, db: Session = Depends(get_db)):
    existing = db.query(PendingOperation).filter(PendingOperation.operation_uuid == operation.operation_uuid).first()
    if existing:
        return existing
    try:
        datos = json.loads(operation.payload)
    except json.JSONDecodeError:
        return save_operation(db, operation, "rejected")
    
    user = db.query(User).filter(User.id == datos["user_id"]).first()
    if not user:
        return save_operation(db, operation, "rejected")
    cash_register = db.query(CashRegister).filter(CashRegister.id == operation.cash_register_id).first()
    if not cash_register:
        return save_operation(db, operation, "rejected")
    
    total = 0
    detalles_validados = []
    
    for item in datos["items"]:
        product = db.query(Product).filter(Product.id == item["product_id"]).first()
        if not product:
            return save_operation(db, operation, "rejected")
        if item["quantity"] > product.stock:
            return save_operation(db, operation, "rejected")
        subtotal = product.price * item["quantity"]
        total += subtotal
        detalles_validados.append({
            "product_id": item["product_id"],
            "quantity": item["quantity"],
            "unit_price": product.price
        })
    
    new_sale = Sale(
        user_id = datos["user_id"],
        cash_register_id = operation.cash_register_id,
        total = total,
        time = operation.occurred_at
    )
    db.add(new_sale)
    db.commit()
    db.refresh(new_sale)
    for detalle in detalles_validados:
        nuevo_detalle = SaleDetail(
            sale_id = new_sale.id,
            product_id = detalle["product_id"],
            quantity = detalle["quantity"],
            unit_price = detalle["unit_price"]
        )
        db.add(nuevo_detalle)
        product = db.query(Product).filter(Product.id == detalle["product_id"]).first()
        product.stock -= detalle["quantity"]
    db.commit()
    return save_operation(db, operation, "confirmed")