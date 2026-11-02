"""
Tests para POST /sales (create_sale).

Casos:
  1. Venta válida: devuelve 200, crea la Sale con sus SaleDetail, descuenta stock.
  2. Dos ítems del mismo producto: la cantidad se acumula correctamente.
  3. Producto inexistente: 404.
  4. Cantidad <= 0: 422 (validación Pydantic en el schema).
  5. Stock insuficiente: 400.
  6. Stock insuficiente acumulado (mismo producto en dos líneas): 400.
"""

import pytest
from decimal import Decimal
from app.models.product import Product


class TestCreateSale:
    def test_venta_valida_devuelve_200_y_descuenta_stock(self, client, db, usuario, caja, producto):
        """
        Camino feliz: una línea, cantidad menor al stock.
        Verifica que el endpoint devuelva 200, que los campos del JSON
        coincidan con los valores enviados, y que el stock en la DB
        se haya descontado.
        """
        payload = {
            "user_id": usuario.id,
            "cash_register_id": caja.id,
            "items": [{"product_id": producto.id, "quantity": "3.000"}],
        }

        response = client.post("/sales", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == usuario.id
        assert data["cash_register_id"] == caja.id
        assert len(data["items"]) == 1
        assert Decimal(data["items"][0]["quantity"]) == Decimal("3.000")
        assert Decimal(data["items"][0]["unit_price"]) == Decimal("10.00")
        assert Decimal(data["total"]) == Decimal("30.00")

        # El stock debe haber bajado: 100 - 3 = 97
        db.expire(producto)  # fuerza re-lectura desde la DB
        assert Decimal(str(producto.stock)) == Decimal("97.000")

    def test_dos_items_mismo_producto_acumula_stock(self, client, db, usuario, caja, producto):
        """
        Dos líneas del mismo producto en la misma venta.
        La acumulación debe sumar las cantidades y comparar contra el stock total.
        Stock inicial = 100. Pedimos 30 + 20 = 50. Debe pasar.
        """
        payload = {
            "user_id": usuario.id,
            "cash_register_id": caja.id,
            "items": [
                {"product_id": producto.id, "quantity": "30.000"},
                {"product_id": producto.id, "quantity": "20.000"},
            ],
        }

        response = client.post("/sales", json=payload)

        assert response.status_code == 200
        db.expire(producto)
        assert Decimal(str(producto.stock)) == Decimal("50.000")

    def test_producto_inexistente_devuelve_404(self, client, usuario, caja):
        """Un product_id que no existe en la DB devuelve 404."""
        payload = {
            "user_id": usuario.id,
            "cash_register_id": caja.id,
            "items": [{"product_id": 999999, "quantity": "1.000"}],
        }

        response = client.post("/sales", json=payload)

        assert response.status_code == 404

    def test_cantidad_cero_devuelve_422(self, client, usuario, caja, producto):
        """
        quantity=0 viola el Field(gt=0) del schema SaleDetailCreate.
        Pydantic rechaza el request antes de que llegue al endpoint: 422.
        """
        payload = {
            "user_id": usuario.id,
            "cash_register_id": caja.id,
            "items": [{"product_id": producto.id, "quantity": "0"}],
        }

        response = client.post("/sales", json=payload)

        assert response.status_code == 422

    def test_stock_insuficiente_devuelve_400(self, client, usuario, caja, producto_sin_stock):
        """Stock = 0, se pide 1. El endpoint devuelve 400."""
        payload = {
            "user_id": usuario.id,
            "cash_register_id": caja.id,
            "items": [{"product_id": producto_sin_stock.id, "quantity": "1.000"}],
        }

        response = client.post("/sales", json=payload)

        assert response.status_code == 400

    def test_stock_insuficiente_acumulado_devuelve_400(self, client, db, usuario, caja):
        """
        Dos líneas del mismo producto cuya suma supera el stock.
        Stock = 5. Pedimos 3 + 3 = 6. Debe devolver 400.
        """
        p = Product(name="Stock Justo", price=Decimal("1.00"), stock=Decimal("5.000"), barcode="JUST001")
        db.add(p)
        db.flush()

        payload = {
            "user_id": usuario.id,
            "cash_register_id": caja.id,
            "items": [
                {"product_id": p.id, "quantity": "3.000"},
                {"product_id": p.id, "quantity": "3.000"},
            ],
        }

        response = client.post("/sales", json=payload)

        assert response.status_code == 400
        # El stock no debe haberse modificado
        db.expire(p)
        assert Decimal(str(p.stock)) == Decimal("5.000")
