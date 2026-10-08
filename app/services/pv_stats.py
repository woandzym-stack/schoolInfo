"""页面 PV 统计。

仅 Redis 计数（累计 + 日维度），供后台查看，不落 MySQL。
- key: pv:{page}:total            累计 PV，不过期
- key: pv:{page}:{YYYY-MM-DD}     当日 PV，TTL 40 天，过期自动清理

计数失败只记日志，绝不影响页面正常返回。
"""

from datetime import date, timedelta
from typing import Any

from loguru import logger

from app.core.task_store import redis_async

# 日维度 key 保留天数
DAILY_TTL_SECONDS = 40 * 24 * 3600

# 参与统计的页面标识（与 ui.py 打点处保持一致）
TRACKED_PAGES = ("schools", "subscriptions")


async def incr_pv(page: str) -> None:
    """累计 PV + 当日 PV 各加 1（pipeline 一次往返）。失败静默降级，只记日志。"""
    try:
        daily_key = f"pv:{page}:{date.today().isoformat()}"
        async with redis_async.pipeline(transaction=False) as pipe:
            pipe.incr(f"pv:{page}:total")
            pipe.incr(daily_key)
            pipe.expire(daily_key, DAILY_TTL_SECONDS)
            await pipe.execute()
    except Exception as e:
        logger.error(f"PV incr error for page={page}: {e}")


async def get_pv_overview(days: int = 7) -> dict[str, dict[str, Any]]:
    """返回各页面累计 PV 与最近 N 天的日 PV。

    返回结构: {page: {"total": int, "daily": {"2026-10-08": 12, ...}}}
    """
    days = max(1, min(days, 40))  # 日 key 只保留 40 天，超出无意义
    today = date.today()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(days)]
    dates.reverse()  # 按日期升序，方便前端直接画图

    keys = [f"pv:{page}:total" for page in TRACKED_PAGES]
    keys += [f"pv:{page}:{d}" for page in TRACKED_PAGES for d in dates]
    values = await redis_async.mget(keys)

    overview: dict[str, dict[str, Any]] = {}
    for idx, page in enumerate(TRACKED_PAGES):
        total = int(values[idx] or 0)
        daily_values = values[len(TRACKED_PAGES) + idx * days : len(TRACKED_PAGES) + (idx + 1) * days]
        overview[page] = {
            "total": total,
            "daily": {d: int(v or 0) for d, v in zip(dates, daily_values)},
        }
    return overview
