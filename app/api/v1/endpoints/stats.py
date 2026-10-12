from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_async_db
from app.models.users import Users
from app.schemas.response import SingleResponse
from app.services.stats_service import get_stats_overview

router = APIRouter()


@router.get("/visits", summary="访问统计总览（PV/来源/事件/转化）", response_model=SingleResponse)
async def visits(
    user: Annotated[Users, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
    days: Annotated[int, Query(ge=1, le=40, description="返回最近几天的日数据")] = 7,
) -> SingleResponse:
    """页面 PV（含来源分布）+ 核心事件 + 注册/订阅实数。需登录，仅作后台查看。"""
    return SingleResponse(errCode=200, data=await get_stats_overview(db, days))
