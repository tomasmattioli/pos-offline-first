"""
seed.py — Carga inicial de datos para pos_central.

Uso (desde la raíz de servidor/, con el venv activo):
    python scripts/seed.py

Crea un usuario, una terminal de caja y cuatro productos de ejemplo.
Falla ruidosamente si ya existe un usuario con el mismo username,
evitando duplicar datos en corridas repetidas.
"""

import sys
import os

# Permite importar los módulos de la app desde cualquier directorio de trabajo.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from app.database import SessionLocal
from app.models.user import User
from app.models.cash_register import CashRegister
from app.models.product import Product


def seed():
    db = SessionLocal()
    try:
        # 1. Usuario cajero
        u = User(
            name="Tomas",
            username="tomas",
            password_hash="hash_demo",  # reemplazar con bcrypt en producción
        )
        db.add(u)

        # 2. Terminal de caja
        c = CashRegister(name="Caja Principal")
        db.add(c)

        db.flush()  # asigna IDs antes de los productos

        # 3. Productos de ejemplo
        productos = [
            Product(
                name="Leche Entera 1L",
                price=Decimal("150.00"),
                stock=Decimal("50.000"),
                barcode="779123456789",
            ),
            Product(
                name="Galletitas Chocolate 250g",
                price=Decimal("120.00"),
                stock=Decimal("30.000"),
                barcode="779987654321",
            ),
            Product(
                name="Yerba Mate 500g",
                price=Decimal("280.00"),
                stock=Decimal("25.000"),
                barcode="779555123456",
            ),
            Product(
                name="Pan Criollo (kg)",
                price=Decimal("90.00"),
                stock=Decimal("15.000"),
                barcode=None,  # artículo sin código → buscar por #ID
            ),
        ]
        db.add_all(productos)
        db.commit()

        print(f"Usuario creado:  ID={u.id}  username='{u.username}'")
        print(f"Caja creada:     ID={c.id}  nombre='{c.name}'")
        print("Productos creados:")
        for p in productos:
            cod = p.barcode if p.barcode else "S/C"
            print(f"  ID={p.id}  {p.name:<30}  ${p.price}  stock={p.stock}  barcode={cod}")

    except IntegrityError as e:
        db.rollback()
        print(f"Error: ya existen datos en la base. {e.orig}")
        print("Si querés empezar de cero, vaciá las tablas primero:")
        print("  TRUNCATE TABLE sale_details, sales, pending_operations, products, cash_registers, users RESTART IDENTITY CASCADE;")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed()

