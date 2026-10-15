from fastapi import APIRouter
from routes.create_card import router as create_card_router

app = APIRouter(prefix="/api")

app.include_router(create_card_router)