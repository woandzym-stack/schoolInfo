from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import get_async_db
from app.schemas.response import SingleResponse
from app.services import admission_update_service

router = APIRouter()


@router.get("", response_model=SingleResponse, summary="公开插班动态列表")
async def list_updates(
    db: Annotated[AsyncSession, Depends(get_async_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=20),
    keyword: str = Query(default="", max_length=100),
    stage: str = Query(default="", pattern="^(|primary|secondary)$"),
    change_kind: str = Query(default="", max_length=30),
) -> SingleResponse:
    data = await admission_update_service.list_public_updates(
        db, page=page, page_size=page_size, keyword=keyword, stage=stage, change_kind=change_kind
    )
    return SingleResponse(data=data)


@router.get("/{update_id}", response_model=SingleResponse, summary="公开插班动态详情")
async def get_update(
    update_id: int,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SingleResponse:
    data: Optional[dict[str, Any]] = await admission_update_service.get_public_update(db, update_id)
    if data is None:
        raise HTTPException(status_code=404, detail="动态不存在或未公开")
    return SingleResponse(data=data)
