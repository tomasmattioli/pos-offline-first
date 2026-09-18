from fastapi import FastAPI
from app.routers import products
from app.routers import cash_register
from app.routers import user

app = FastAPI()

app.include_router(products.router)
app.include_router(cash_register.router)
app.include_router(user.router)