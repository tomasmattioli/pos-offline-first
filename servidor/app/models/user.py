from sqlalchemy import Column, Integer, String
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key= True)
    name = Column(String(50), nullable = False)
    username = Column(String(50), unique=True,nullable = False)
    password_hash = Column(String(60), nullable=False,)

def __repr__(self):
    return f"<User {self.name} ({self.username})>"

