from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.auth import get_admin_user
from app.core.db import get_async_db
from app.models.users import Users
from app.schemas.admission_update import AdmissionUpdateContent, AdmissionUpdateCreate, AdmissionUpdateDelete
from app.schemas.response import SingleResponse
from app.services import admission_update_service

router = APIRouter()


@router.get("/updates", response_model=SingleResponse, summary="管理快讯列表")
async def list_updates(
    _: Annotated[Users, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str = Query(default="", pattern="^(|draft|published|deleted)$"),
    keyword: str = Query(default="", max_length=100),
) -> SingleResponse:
    data = await admission_update_service.list_admin_updates(
        db, page=page, page_size=page_size, status=status, keyword=keyword
    )
    return SingleResponse(data=data)


@router.post("/updates", response_model=SingleResponse, summary="手动新建或从候选生成草稿")
async def create_update(
    payload: AdmissionUpdateCreate,
    user: Annotated[Users, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SingleResponse:
    return SingleResponse(data=await admission_update_service.create_update(db, payload, user.id))


@router.get("/updates/{update_id}", response_model=SingleResponse, summary="管理快讯详情")
async def get_update(
    update_id: int,
    _: Annotated[Users, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SingleResponse:
    return SingleResponse(data=await admission_update_service.get_admin_update(db, update_id))


@router.put("/updates/{update_id}", response_model=SingleResponse, summary="保存草稿或保存并公开")
async def update_content(
    update_id: int,
    payload: AdmissionUpdateContent,
    user: Annotated[Users, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SingleResponse:
    return SingleResponse(data=await admission_update_service.update_content(db, update_id, payload, user.id))


@router.post("/updates/{update_id}/publish", response_model=SingleResponse, summary="发布草稿")
async def publish_update(
    update_id: int,
    user: Annotated[Users, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SingleResponse:
    return SingleResponse(data=await admission_update_service.publish_update(db, update_id, user.id))


@router.post("/updates/{update_id}/delete", response_model=SingleResponse, summary="软删除快讯")
async def delete_update(
    update_id: int,
    payload: AdmissionUpdateDelete,
    user: Annotated[Users, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SingleResponse:
    return SingleResponse(data=await admission_update_service.delete_update(db, update_id, payload.reason, user.id))


@router.post("/updates/{update_id}/restore", response_model=SingleResponse, summary="恢复已删除快讯为草稿")
async def restore_update(
    update_id: int,
    user: Annotated[Users, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SingleResponse:
    return SingleResponse(data=await admission_update_service.restore_update(db, update_id, user.id))


@router.get("/admission-changes", response_model=SingleResponse, summary="申请变化候选分页")
async def list_candidates(
    _: Annotated[Users, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str = Query(default="pending", pattern="^(pending|adopted|ignored|all)$"),
    school_id: Optional[int] = None,
    detected_on: Optional[date] = None,
) -> SingleResponse:
    data = await admission_update_service.list_candidates(
        db,
        page=page,
        page_size=page_size,
        status=status,
        school_id=school_id,
        detected_on=detected_on,
    )
    return SingleResponse(data=data)


@router.post("/admission-changes/{change_id}/ignore", response_model=SingleResponse, summary="忽略候选")
async def ignore_candidate(
    change_id: int,
    user: Annotated[Users, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SingleResponse:
    return SingleResponse(data=await admission_update_service.ignore_candidate(db, change_id, user.id))


@router.post("/admission-changes/{change_id}/restore", response_model=SingleResponse, summary="恢复候选为待处理")
async def restore_candidate(
    change_id: int,
    _: Annotated[Users, Depends(get_admin_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SingleResponse:
    return SingleResponse(data=await admission_update_service.restore_candidate(db, change_id))
