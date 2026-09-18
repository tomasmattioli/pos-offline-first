from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut
from app.security import hash_password

router = APIRouter()


@router.post("/users/", response_model = UserOut)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    new_user = User(name = user.name , username = user.username , password_hash = hash_password(user.password))    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session= Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"Usuario con ID {user_id} no encontrado"
        )

    return user


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, update_data: UserCreate, db: Session= Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"Usuario con ID {user_id} no encontrado"
        )
    user.name = update_data.name
    user.username = update_data.username
    user.password_hash = hash_password(update_data.password)
    db.commit()
    db.refresh(user)
    return user

@router.delete("/users/{user_id}", response_model=UserOut)
def delete_user(user_id: int, db: Session= Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"Usuario con ID {user_id} no encontrado"
        )
    db.delete(user)
    db.commit()
    return user

