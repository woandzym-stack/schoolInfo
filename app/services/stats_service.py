"""统计后台聚合：Redis 计数（PV/来源/事件）+ MySQL 转化实数（注册/订阅）。

注册与订阅以数据库为准直接 COUNT——数据本就落库，另写一套计数器只会造成双写不一致。
"""

from datetime import date, datetime, time
from typing import Any

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.subscriptions import Subscriptions
from app.models.users import Users
from app.services.pv_stats import get_event_overview, get_pv_overview


async def _conversion_stats(db: AsyncSession) -> dict[str, dict[str, int]]:
    """注册/订阅的累计与今日新增（created_at 为本地时间，与 Redis 日维度口径一致）。"""
    today_start = datetime.combine(date.today(), time.min)

    users_total = (await db.exec(select(func.count()).select_from(Users))).one()
    users_today = (await db.exec(select(func.count()).select_from(Users).where(Users.created_at >= today_start))).one()
    subs_total = (await db.exec(select(func.count()).select_from(Subscriptions))).one()
    subs_today = (
        await db.exec(select(func.count()).select_from(Subscriptions).where(Subscriptions.created_at >= today_start))
    ).one()

    return {
        "users": {"total": users_total, "today": users_today},
        "subscriptions": {"total": subs_total, "today": subs_today},
    }


async def get_stats_overview(db: AsyncSession, days: int = 7) -> dict[str, Any]:
    """统计后台总览：页面 PV（含来源）+ 核心事件 + 转化实数。"""
    return {
        "pages": await get_pv_overview(days),
        "events": await get_event_overview(days),
        "conversions": await _conversion_stats(db),
    }
