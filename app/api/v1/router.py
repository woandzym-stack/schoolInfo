from fastapi import APIRouter

from app.api.v1.endpoints import auth, schools, subscriptions
from app.core.config import settings

api_router = APIRouter()

api_router.include_router(
    schools.router,
    prefix="/schools",
    tags=["schools"]
)

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["auth"]
)

api_router.include_router(
    subscriptions.router,
    prefix="/subscriptions",
    tags=["subscriptions"]
)


if settings.RUN_MODE in ("local"):
    from app.api.v1.endpoints import code_generate

    api_router.include_router(
        code_generate.router, 
        prefix="/code_generate",
        tags=["code_generate"]
    )
