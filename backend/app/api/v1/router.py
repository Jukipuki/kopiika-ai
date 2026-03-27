from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.uploads import router as uploads_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(uploads_router)
