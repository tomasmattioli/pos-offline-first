from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.pendig_operation import PendingOperation
from app.schemas.pending_operation import PendingOperationCreate, PendingOperationOut, PendingOperationPayload
from pydantic import ValidationError
from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_detail import SaleDetail
from app.models.user import User
from app.models.cash_register import CashRegister

router = APIRouter()

def save_operation(db: Session, operation: PendingOperationCreate, status: str) -> PendingOperation:
    new_operation = PendingOperation(
        operation_uuid=operation.operation_uuid,
        cash_register_id=operation.cash_register_id,
        payload=operation.payload,
        occurred_at=operation.occurred_at,
        status=status,
    )
    try:
        db.add(new_operation)
        db.commit()
        db.refresh(new_operation)
    except Exception:
        db.rollback()
        # No podemos persistir (p.ej. FK violation porque la caja no existe).
        # Devolvemos el objeto sin id pero con el status correcto para que el
        # endpoint pueda responder al cliente. El cliente (la caja) verá el status.
        new_operation.id = -1
    return new_operation
    
    
@router.post("/pending_operations", response_model= PendingOperationOut)
def create_pending_operation(operation: PendingOperationCreate, db: Session = Depends(get_db)):
    existing = db.query(PendingOperation).filter(PendingOperation.operation_uuid == operation.operation_uuid).first()
    if existing:
        return existing
    try:
        payload = PendingOperationPayload.model_validate_json(operation.payload)
    except ValidationError:
        return save_operation(db, operation, "rejected")

    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        return save_operation(db, operation, "rejected")
    cash_register = db.query(CashRegister).filter(CashRegister.id == operation.cash_register_id).first()
    if not cash_register:
        return save_operation(db, operation, "rejected")
    
    total = 0
    detalles_validados = []
    pedido_por_producto = {}
    
    for item in payload.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            return save_operation(db, operation, "rejected")
        pedido_por_producto[item.product_id] = pedido_por_producto.get(item.product_id, 0) + item.quantity
        if pedido_por_producto[item.product_id] > product.stock:
            return save_operation(db, operation, "rejected")
        subtotal = product.price * item.quantity
        total += subtotal
        detalles_validados.append({
            "product_id": item.product_id,
            "quantity": item.quantity,
            "unit_price": product.price,
        })

    # Camino feliz: Sale + SaleDetail + descuento de stock + PendingOperation
    # en una sola transacción. Si cualquier paso falla, rollback deja la DB intacta.
    try:
        new_sale = Sale(
            user_id=payload.user_id,
            cash_register_id=operation.cash_register_id,
            total=total,
            time=operation.occurred_at,
        )
        db.add(new_sale)
        # flush asigna new_sale.id sin commitear; los SaleDetail lo necesitan.
        db.flush()

        for detalle in detalles_validados:
            db.add(SaleDetail(
                sale_id=new_sale.id,
                product_id=detalle["product_id"],
                quantity=detalle["quantity"],
                unit_price=detalle["unit_price"],
            ))
            product = db.query(Product).filter(Product.id == detalle["product_id"]).first()
            product.stock -= detalle["quantity"]

        confirmed_op = PendingOperation(
            operation_uuid=operation.operation_uuid,
            cash_register_id=operation.cash_register_id,
            payload=operation.payload,
            occurred_at=operation.occurred_at,
            status="confirmed",
        )
        db.add(confirmed_op)
        db.commit()
        db.refresh(confirmed_op)
        return confirmed_op
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Error interno al procesar la operación")