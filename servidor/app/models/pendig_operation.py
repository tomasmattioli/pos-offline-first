from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID 
import uuid
from app.database import Base


class PendingOperation(Base):
    __tablename__ = "pending_operations"

    id = Column(Integer, primary_key=True, nullable=False)
    occurred_at= Column(DateTime, nullable=False)
    operation_uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    status = Column(String(20), nullable=False, default="pending")
    cash_register_id = Column(Integer, ForeignKey("cash_registers.id"), nullable=False)
    payload = Column(String(500), nullable=False)
