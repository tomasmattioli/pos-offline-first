from fastapi import FastAPI
from app.routers import products, cash_register, user, sales, pending_operations
app = FastAPI()

app.include_router(products.router)
app.include_router(cash_register.router)
app.include_router(user.router)
app.include_router(sales.router)
app.include_router(pending_operations.router)