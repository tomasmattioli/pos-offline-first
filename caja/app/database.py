from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///caja.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    import app.models.product          # noqa: F401  – registra Product en Base.metadata
    import app.models.pending_operation  # noqa: F401  – registra PendingOperation en Base.metadata
    Base.metadata.create_all(bind=engine)
