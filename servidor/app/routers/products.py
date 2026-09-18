from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductOut

router = APIRouter()

@router.post("/products", response_model=ProductOut)
def create_product(product: ProductCreate, db:Session = Depends(get_db)):
    new_product = Product(**product.dict())
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product

@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session= Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Producto con ID {product_id} no encontrado"
        )

    return product


@router.put("/product/{product_id}", response_model=ProductOut)
def update_product(product_id: int,update_data:ProductCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Prodcuto con ID {product_id} no encontrado"
        )
    product.name = update_data.name
    product.price = update_data.price
    product.stock = update_data.stock
    product.barcode = update_data.barcode
    db.commit()
    db.refresh(product)
    return product

@router.delete("/product/{product_id}", response_model=ProductOut)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Prodcuto con ID {product_id} no encontrado"
        )
    db.delete(product)
    db.commit()
    return product