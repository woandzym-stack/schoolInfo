from fastapi import APIRouter

from app.api.v1.endpoints import admin_updates, auth, schools, stats, subscriptions, updates
from app.core.config import settings

api_router = APIRouter()

api_router.include_router(schools.router, prefix="/schools", tags=["schools"])

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])

api_router.include_router(stats.router, prefix="/stats", tags=["stats"])

api_router.include_router(updates.router, prefix="/updates", tags=["updates"])

api_router.include_router(admin_updates.router, prefix="/admin", tags=["admin-updates"])


if settings.RUN_MODE in ("local"):
    from app.api.v1.endpoints import code_generate

    api_router.include_router(code_generate.router, prefix="/code_generate", tags=["code_generate"])
