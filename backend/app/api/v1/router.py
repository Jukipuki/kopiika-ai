from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.insights import router as insights_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.profile import router as profile_router
from app.api.v1.transactions import router as transactions_router
from app.api.v1.uploads import router as uploads_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(insights_router)
v1_router.include_router(jobs_router)
v1_router.include_router(profile_router)
v1_router.include_router(transactions_router)
v1_router.include_router(uploads_router)
