import uuid
from sqlalchemy import Column, Integer, String
from app.database import Base


class PendingOperation(Base):
    __tablename__ = "pending_operations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    operation_uuid = Column(String(36), nullable=False, unique=True, default=lambda: str(uuid.uuid4()))
    cash_register_id = Column(Integer, nullable=False)
    occurred_at = Column(String, nullable=False)
    payload = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
