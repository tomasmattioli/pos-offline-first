from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.cash_register import CashRegister
from app.schemas.cash_register import CashRegisterCreate, CashRegisterOut

router = APIRouter()

@router.post("/cash_registers", response_model=CashRegisterOut)
def create_cash_register(cash: CashRegisterCreate, db:Session = Depends(get_db)):
    new_cash_register = CashRegister(**cash.dict())
    db.add(new_cash_register)
    db.commit()
    db.refresh(new_cash_register)
    return new_cash_register

@router.get("/cash_registers/{cash_register_id}", response_model=CashRegisterOut)
def get_cash_register(cash_register_id: int, db: Session= Depends(get_db)):
    cash_register = db.query(CashRegister).filter(CashRegister.id == cash_register_id).first()
    if not cash_register:
        raise HTTPException(
            status_code=404,
            detail=f"Caja con ID {cash_register_id} no encontrado"
        )

    return cash_register


@router.put("/cash_registers/{cash_register_id}", response_model=CashRegisterOut)
def update_cash_register(cash_register_id: int,update_data:CashRegisterCreate, db: Session = Depends(get_db)):
    cash_register = db.query(CashRegister).filter(CashRegister.id == cash_register_id).first()
    if not cash_register:
        raise HTTPException(
            status_code=404,
            detail=f"Caja con ID {cash_register_id} no encontrado"
        )
    cash_register.name = update_data.name
    db.commit()
    db.refresh(cash_register)
    return cash_register

@router.delete("/cash_registers/{cash_register_id}", response_model=CashRegisterOut)
def delete_cash_register(cash_register_id: int, db: Session = Depends(get_db)):
    cash_register = db.query(CashRegister).filter(CashRegister.id == cash_register_id).first()
    if not cash_register:
        raise HTTPException(
            status_code=404,
            detail=f"Caja con ID {cash_register_id} no encontrado"
        )
    db.delete(cash_register)
    db.commit()
    return cash_register