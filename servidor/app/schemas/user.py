from pydantic import BaseModel

class UserCreate(BaseModel):
    password: str
    name: str
    username: str


class UserOut(BaseModel):
    id: int
    name: str
    username: str
    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    username: str
    password: str
    