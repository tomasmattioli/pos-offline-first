import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from app.config import CASH_REGISTER_ID, USER_ID
from app.models.pending_operation import PendingOperation
from app.models.product import Product
from app.utils import to_decimal, to_text


def register_sale(
    db: Session, items: List[Tuple[int, Decimal]]
) -> Tuple[bool, str, Optional[PendingOperation]]:
    """
    Registra una venta localmente de forma atómica:
    1. Valida que la lista de ítems no esté vacía y que cada cantidad sea > 0.
    2. Valida que todos los productos existan en el catálogo local.
    3. Acumula la cantidad pedida por producto y valida contra el stock local.
    4. Descuenta el stock local de los productos.
    5. Arma el payload con USER_ID y las cantidades serializadas en string.
    6. Crea la PendingOperation con UUID generado en la caja, CASH_REGISTER_ID y timestamp UTC ISO.
    7. Realiza un único commit con rollback explícito ante cualquier error.

    Retorna una tupla (éxito, mensaje, operación).
    """
    if not items:
        return False, "La venta debe contener al menos un ítem.", None

    # Validar cantidades individuales > 0
    for product_id, quantity in items:
        if not isinstance(quantity, Decimal):
            try:
                quantity = Decimal(str(quantity))
            except Exception:
                return (
                    False,
                    f"Cantidad inválida para el producto ID {product_id}: {quantity}.",
                    None,
                )
        if quantity <= Decimal(0):
            return (
                False,
                f"La cantidad para el producto ID {product_id} debe ser mayor a 0 (recibido: {quantity}).",
                None,
            )

    # Validar existencia de productos y acumular pedidos
    pedido_por_producto: dict[int, Decimal] = {}
    productos_db: dict[int, Product] = {}

    for product_id, quantity in items:
        if product_id not in productos_db:
            product = db.query(Product).filter(Product.id == product_id).first()
            if not product:
                return (
                    False,
                    f"El producto con ID {product_id} no existe en el catálogo local.",
                    None,
                )
            productos_db[product_id] = product

        pedido_por_producto[product_id] = (
            pedido_por_producto.get(product_id, Decimal(0)) + quantity
        )

    # Validar stock local disponible para cada producto pedido
    for product_id, total_pedido in pedido_por_producto.items():
        product = productos_db[product_id]
        stock_actual = to_decimal(product.stock)
        if total_pedido > stock_actual:
            return (
                False,
                f"Stock insuficiente para '{product.name}' (ID {product_id}): "
                f"disponible {stock_actual}, solicitado {total_pedido}.",
                None,
            )

    # Descontar stock local
    for product_id, total_pedido in pedido_por_producto.items():
        product = productos_db[product_id]
        stock_actual = to_decimal(product.stock)
        nuevo_stock = stock_actual - total_pedido
        product.stock = to_text(nuevo_stock)

    # Armar el payload para el servidor (cantidades como strings para evitar pérdida de precisión)
    payload_data = {
        "user_id": USER_ID,
        "items": [
            {"product_id": pid, "quantity": to_text(qty)}
            for pid, qty in items
        ],
    }
    payload_json = json.dumps(payload_data)

    # Crear la operación en la cola
    operation = PendingOperation(
        operation_uuid=str(uuid.uuid4()),
        cash_register_id=CASH_REGISTER_ID,
        occurred_at=datetime.now(timezone.utc).isoformat(),
        payload=payload_json,
        status="pending",
    )
    db.add(operation)

    # Único commit con rollback si algo falla
    try:
        db.commit()
        db.refresh(operation)
        return True, "Venta registrada con éxito.", operation
    except Exception as e:
        db.rollback()
        return False, f"Error al registrar la venta en la base de datos: {e}", None
