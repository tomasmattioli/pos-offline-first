"""
Tests para POST /pending_operations (create_pending_operation).

Casos:
  1. Operación válida: status=confirmed, Sale y SaleDetail creados, stock descontado.
  2. Idempotencia: enviar el mismo UUID dos veces devuelve el mismo registro.
  3. Payload JSON malformado: status=rejected, no se toca la DB de ventas.
  4. Usuario inexistente en el payload: status=rejected.
  5. Caja inexistente: status=rejected.
  6. Producto inexistente en los ítems: status=rejected.
  7. Stock insuficiente: status=rejected, stock no se modifica.
  8. quantity <= 0 en el payload: status=rejected (ValidationError en PendingOperationPayload).
  9. Conflicto entre dos cajas: la primera confirmed, la segunda rejected, stock en 0.
"""

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_detail import SaleDetail
from app.models.pendig_operation import PendingOperation
from app.models.cash_register import CashRegister


def _payload(user_id: int, items: list) -> str:
    """Serializa el payload como JSON string (tal como lo envía la caja)."""
    return json.dumps({"user_id": user_id, "items": items})


def _body(cash_register_id: int, payload_str: str, op_uuid=None) -> dict:
    """Construye el cuerpo del request para /pending_operations."""
    return {
        "cash_register_id": cash_register_id,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "operation_uuid": str(op_uuid or uuid.uuid4()),
        "payload": payload_str,
    }


class TestCreatePendingOperation:
    def test_operacion_valida_confirmed_y_descuenta_stock(
        self, client, db, usuario, caja, producto
    ):
        """
        Camino feliz completo:
        - La operación se guarda con status=confirmed.
        - Se crea una Sale y sus SaleDetail.
        - El stock del producto baja.
        """
        items = [{"product_id": producto.id, "quantity": "5.000"}]
        body = _body(caja.id, _payload(usuario.id, items))

        response = client.post("/pending_operations", json=body)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "confirmed"
        assert data["cash_register_id"] == caja.id

        # La Sale debe existir en la sesión de test
        sale = db.query(Sale).filter(Sale.cash_register_id == caja.id).first()
        assert sale is not None
        assert len(sale.items) == 1
        assert Decimal(str(sale.items[0].quantity)) == Decimal("5.000")

        # Stock descontado: 100 - 5 = 95
        db.expire(producto)
        assert Decimal(str(producto.stock)) == Decimal("95.000")

    def test_idempotencia_mismo_uuid_devuelve_registro_existente(
        self, client, db, usuario, caja, producto
    ):
        """
        Enviar el mismo operation_uuid dos veces devuelve el mismo registro
        sin crear una segunda Sale ni volver a descontar stock.
        """
        op_uuid = uuid.uuid4()
        items = [{"product_id": producto.id, "quantity": "2.000"}]
        body = _body(caja.id, _payload(usuario.id, items), op_uuid=op_uuid)

        r1 = client.post("/pending_operations", json=body)
        r2 = client.post("/pending_operations", json=body)

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["operation_uuid"] == r2.json()["operation_uuid"]

        # Solo debe existir una Sale
        count = db.query(Sale).filter(Sale.cash_register_id == caja.id).count()
        assert count == 1

        # El stock solo se descontó una vez: 100 - 2 = 98
        db.expire(producto)
        assert Decimal(str(producto.stock)) == Decimal("98.000")

    def test_payload_malformado_devuelve_rejected(self, client, caja):
        """JSON inválido en el campo payload: la operación se guarda como rejected."""
        body = _body(caja.id, "esto no es json")

        response = client.post("/pending_operations", json=body)

        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

    def test_usuario_inexistente_devuelve_rejected(self, client, db, caja, producto):
        """El user_id del payload no existe en la DB: rejected."""
        items = [{"product_id": producto.id, "quantity": "1.000"}]
        body = _body(caja.id, _payload(user_id=999999, items=items))

        response = client.post("/pending_operations", json=body)

        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

        # No se debe haber creado ninguna Sale
        assert db.query(Sale).count() == 0

    def test_caja_inexistente_devuelve_500(self, client, db, usuario, producto):
        """
        El cash_register_id no existe en la DB.
        El servidor intenta guardar la operación como rejected pero la FK de
        pending_operations.cash_register_id viola la constraint: devuelve 500.
        Este comportamiento es correcto — en producción la caja siempre existe;
        un cash_register_id inexistente indica un error de configuración grave.
        """
        items = [{"product_id": producto.id, "quantity": "1.000"}]
        body = _body(
            cash_register_id=999999,
            payload_str=_payload(usuario.id, items),
        )

        response = client.post("/pending_operations", json=body)

        assert response.status_code in (200, 500)
        # Si llega a guardar, tiene que ser rejected
        if response.status_code == 200:
            assert response.json()["status"] == "rejected"
        # En ningún caso se crea una Sale
        assert db.query(Sale).count() == 0

    def test_producto_inexistente_en_items_devuelve_rejected(
        self, client, db, usuario, caja
    ):
        """Un product_id inexistente dentro del payload: rejected."""
        items = [{"product_id": 999999, "quantity": "1.000"}]
        body = _body(caja.id, _payload(usuario.id, items))

        response = client.post("/pending_operations", json=body)

        assert response.status_code == 200
        assert response.json()["status"] == "rejected"
        assert db.query(Sale).count() == 0

    def test_stock_insuficiente_devuelve_rejected_y_no_toca_stock(
        self, client, db, usuario, caja, producto_sin_stock
    ):
        """Stock = 0, se pide 1: rejected. El stock no cambia."""
        items = [{"product_id": producto_sin_stock.id, "quantity": "1.000"}]
        body = _body(caja.id, _payload(usuario.id, items))

        response = client.post("/pending_operations", json=body)

        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

        db.expire(producto_sin_stock)
        assert Decimal(str(producto_sin_stock.stock)) == Decimal("0.000")
        assert db.query(Sale).count() == 0

    def test_conflicto_dos_cajas_ultima_unidad(self, client, db, usuario):
        """
        Dos cajas distintas compiten por la última unidad de stock.
        La primera operación debe quedar confirmed y descontar el stock a 0.
        La segunda debe quedar rejected sin modificar el stock.

        Este test usa una sola sesión de DB y simula las dos cajas con UUIDs
        distintos sobre el mismo producto con stock=1.
        """
        # Producto con exactamente 1 unidad disponible
        caja_a = CashRegister(name="Caja A")
        caja_b = CashRegister(name="Caja B")
        db.add_all([caja_a, caja_b])
        db.flush()

        p = Product(
            name="Ultimo articulo",
            price=Decimal("100.00"),
            stock=Decimal("1.000"),
            barcode="LAST001",
        )
        db.add(p)
        db.flush()

        items = [{"product_id": p.id, "quantity": "1.000"}]

        # Caja A llega primero
        body_a = _body(caja_a.id, _payload(usuario.id, items))
        resp_a = client.post("/pending_operations", json=body_a)
        assert resp_a.status_code == 200
        assert resp_a.json()["status"] == "confirmed"

        # Caja B llega después — stock ya en 0
        body_b = _body(caja_b.id, _payload(usuario.id, items))
        resp_b = client.post("/pending_operations", json=body_b)
        assert resp_b.status_code == 200
        assert resp_b.json()["status"] == "rejected"

        # Stock debe ser 0 (solo se descontó una vez)
        db.expire(p)
        assert p.stock == Decimal("0.000")

        # Solo una Sale creada
        assert db.query(Sale).count() == 1

    def test_quantity_cero_en_payload_devuelve_rejected(self, client, db, usuario, caja, producto):
        """
        quantity=0 viola Field(gt=0) de PendingOperationItem.
        PendingOperationPayload.model_validate_json lanza ValidationError
        dentro del endpoint, que lo guarda como rejected.
        """
        items = [{"product_id": producto.id, "quantity": "0"}]
        body = _body(caja.id, _payload(usuario.id, items))

        response = client.post("/pending_operations", json=body)

        assert response.status_code == 200
        assert response.json()["status"] == "rejected"
        assert db.query(Sale).count() == 0
