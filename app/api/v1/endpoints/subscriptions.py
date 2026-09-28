from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.auth import get_current_user
from app.core.db import get_async_db
from app.models.users import Users
from app.schemas.response import SingleResponse
from app.schemas.subscription import SubscribeIn
from app.services.db import subscriptions_service

router = APIRouter()


@router.get("", response_model=SingleResponse, summary="我的订阅列表（按学校聚合）")
async def list_subscriptions(
    user: Annotated[Users, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SingleResponse:
    """按学校聚合返回：[{school_id, name, stage, district, grades[], subscribed_at}]，按订阅时间倒序。"""
    return SingleResponse(data=await subscriptions_service.list_mine(db, user.id))


@router.post("", response_model=SingleResponse, summary="订阅学校（幂等）")
async def subscribe(
    body: SubscribeIn,
    user: Annotated[Users, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SingleResponse:
    """
    订阅一所学校：grades 为年级数组（P1-P6/S1-S6），空数组 = 订阅全部年级。

    - 年级必须与学校学段一致，否则 422
    - 覆盖合并：已订 all 再订具体年级静默吞掉；已订具体年级再订 all 先删后插
    - 每用户最多订阅 20 所学校（仅新学校占名额），重复订阅幂等返回成功
    - 返回该校最终订阅状态，前端直接刷新该行
    """
    data = await subscriptions_service.subscribe(db, user.id, body.school_id, body.grades)
    return SingleResponse(data=data)


@router.delete("/{school_id}", response_model=SingleResponse, summary="整校取消订阅")
async def unsubscribe_school(
    school_id: int,
    user: Annotated[Users, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SingleResponse:
    """删除该校所有订阅行（幂等，不存在也返回成功）。"""
    await subscriptions_service.unsubscribe_school(db, user.id, school_id)
    return SingleResponse(data=None)


@router.delete("/{school_id}/grades/{grade}", response_model=SingleResponse, summary="取消单个年级的订阅")
async def unsubscribe_grade(
    school_id: int,
    grade: str,
    user: Annotated[Users, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SingleResponse:
    """逐年级取消（幂等）。"""
    await subscriptions_service.unsubscribe_grade(db, user.id, school_id, grade)
    return SingleResponse(data=None)


@router.get("/links", response_model=SingleResponse, summary="我的订阅学校的插班链接（聚合）")
async def subscription_links(
    user: Annotated[Users, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SingleResponse:
    """
    一次返回当前用户所有订阅学校的插班链接：{school_id: [{url, link_text, grades}]}。

    登录态聚合接口：订阅上限 20 校天然限定数据范围，不占用访客按 IP 限流的额度；
    批量小号爬取路径由注册接口 5 次/天/IP 限流封堵。
    """
    return SingleResponse(data=await subscriptions_service.links_for_subscriptions(db, user.id))
