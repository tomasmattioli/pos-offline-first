from pydantic import BaseModel

class CashRegisterCreate(BaseModel):
    name: str

class CashRegisterOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


        