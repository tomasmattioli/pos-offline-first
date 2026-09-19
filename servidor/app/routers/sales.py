from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.sale import Sale
from app.schemas.sale import SaleCreate, SaleDetailCreate, SaleDetailOut, SaleOut
from app.models.product import Product
from app.models.sale_detail import SaleDetail 
from datetime import datetime

router = APIRouter()

@router.post("/sales", response_model=SaleOut)
def create_sale(sale: SaleCreate, db:Session = Depends(get_db)):
    total = 0
    detalles_validados = []
    for item in sale.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Producto con id {item.product_id} no encontrado")
        if item.quantity > product.stock:
            raise HTTPException(status_code=400, detail="Stock insuficiente")
        
        subtotal = product.price * item.quantity
        total += subtotal
        detalles_validados.append({
            "product_id": item.product_id,
            "quantity": item.quantity,
            "unit_price": product.price
        })

    new_sale = Sale(user_id = sale.user_id, cash_register_id= sale.cash_register_id, total= total, time= datetime.now())
    db.add(new_sale)
    db.commit()
    db.refresh(new_sale)
    for detalle in detalles_validados:
        nuevo_detalle = SaleDetail(
            sale_id = new_sale.id,
            product_id = detalle["product_id"],
            quantity = detalle["quantity"],
            unit_price = detalle["unit_price"]
        )

        db.add(nuevo_detalle)

        product = db.query(Product).filter(Product.id == detalle["product_id"]).first()

        product.stock -= detalle["quantity"]


    db.commit()
    return new_sale
    


