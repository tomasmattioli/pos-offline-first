"""
conftest.py — fixtures compartidas para los tests del servidor.

Estrategia de aislamiento:
  - Usamos PostgreSQL (pos_central_test) en lugar de SQLite porque el modelo
    PendingOperation usa UUID(as_uuid=True) de sqlalchemy.dialects.postgresql,
    que SQLite no soporta de forma nativa.
  - create_all() crea las tablas al iniciar la sesión de tests.
  - Cada test recibe una transacción que se revierte (ROLLBACK) al terminar,
    así la DB queda limpia sin necesidad de DROP TABLE entre tests.
  - El cliente HTTP de FastAPI reemplaza get_db con la dependencia override
    que apunta a esa transacción de test.
"""

import pytest
from decimal import Decimal
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from app.models.user import User
from app.models.cash_register import CashRegister
from app.models.product import Product
# Importar todos los modelos garantiza que Base.metadata los registre
# antes de que create_all() intente crear las tablas.
from app.models.sale import Sale
from app.models.sale_detail import SaleDetail
from app.models.pendig_operation import PendingOperation  # typo original conservado

TEST_DB_URL = "postgresql://postgres:usuario@localhost:5432/pos_central_test"

engine_test = create_engine(TEST_DB_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(scope="session", autouse=True)
def crear_tablas():
    """Crea todas las tablas una vez por sesión de tests y las elimina al terminar."""
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture()
def db():
    """
    Transacción de test con rollback automático usando SAVEPOINT.

    Por qué SAVEPOINT y no una transacción plana:
    Los endpoints llaman a db.commit(). Con una transacción plana, ese commit
    cierra la transacción externa y el rollback posterior lanza SAWarning.
    Con begin_nested() (SAVEPOINT), el commit() del endpoint solo libera el
    SAVEPOINT interno; la transacción externa sigue abierta y el rollback al
    finalizar el test revierte todo sin advertencias.
    """
    connection = engine_test.connect()
    transaction = connection.begin()          # transacción externa
    nested = connection.begin_nested()        # SAVEPOINT interno
    session = TestingSessionLocal(bind=connection)

    # Cada vez que el endpoint llama a session.commit(), SQLAlchemy libera
    # el SAVEPOINT y abre uno nuevo automáticamente para que los siguientes
    # commits del mismo test también funcionen.
    from sqlalchemy import event

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, trans):
        if trans.nested and not trans._parent.nested:
            session.expire_all()
            nested_new = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    """
    TestClient de FastAPI con get_db reemplazado por la sesión de test.

    app.dependency_overrides reemplaza la función get_db —la dependencia que
    FastAPI inyecta en cada endpoint— por una función que devuelve la sesión
    de test. Así, los endpoints operan sobre la misma transacción que el test
    y el rollback al finalizar limpia todo.
    """
    def override_get_db():
        try:
            yield db
        finally:
            pass  # el fixture db() se encarga del cierre y rollback

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Fixtures de datos base
# ---------------------------------------------------------------------------

@pytest.fixture()
def usuario(db):
    """Usuario válido para asociar a ventas."""
    u = User(name="Test User", username="testuser", password_hash="hash_de_prueba")
    db.add(u)
    db.flush()  # asigna u.id sin commitear
    return u


@pytest.fixture()
def caja(db):
    """Caja registradora válida."""
    c = CashRegister(name="Caja Test")
    db.add(c)
    db.flush()
    return c


@pytest.fixture()
def producto(db):
    """Producto con stock suficiente para la mayoría de los tests.

    Usamos Decimal, no strings, porque SQLAlchemy no convierte atributos en
    memoria al hacer flush(). El router recibe el mismo objeto de la identity
    map y espera encontrar Decimal — igual que lo que devuelve psycopg2 al
    leer columnas Numeric de PostgreSQL.
    """
    p = Product(name="Producto Test", price=Decimal("10.00"), stock=Decimal("100.000"), barcode="TEST001")
    db.add(p)
    db.flush()
    return p


@pytest.fixture()
def producto_sin_stock(db):
    """Producto con stock cero, útil para tests de rechazo por stock."""
    p = Product(name="Sin Stock", price=Decimal("5.00"), stock=Decimal("0.000"), barcode="TEST002")
    db.add(p)
    db.flush()
    return p
