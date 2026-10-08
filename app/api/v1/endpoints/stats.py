from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.auth import get_current_user
from app.models.users import Users
from app.schemas.response import SingleResponse
from app.services.pv_stats import get_pv_overview

router = APIRouter()


@router.get("/visits", summary="页面访问量(PV)统计", response_model=SingleResponse)
async def visits(
    user: Annotated[Users, Depends(get_current_user)],
    days: Annotated[int, Query(ge=1, le=40, description="返回最近几天的日PV")] = 7,
) -> SingleResponse:
    """各页面累计 PV + 最近 N 天日 PV。需登录，仅作后台查看。"""
    return SingleResponse(errCode=200, data=await get_pv_overview(days))
