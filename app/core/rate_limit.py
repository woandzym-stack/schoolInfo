"""
固定窗口限流与客户端 IP 提取（auth 与 schools 端点共用）。

- IP 提取：优先 X-Forwarded-For 首跳（部署在 Nginx 之后时由反代覆写），无代理头时退回直连地址
- 限流：Redis 固定窗口计数（INCR + EXPIRE），Redis 抖动时放行（fail-open）——
  可用性优先，正常用户不应被基础设施故障阻断
"""
from typing import List, Tuple

from fastapi import HTTPException, Request
from loguru import logger

from app.core.task_store import redis_async


def get_client_ip(request: Request) -> str:
    """取客户端 IP：XFF 首跳优先，无代理头退回直连地址。"""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def check_rate_limit(
    windows: List[Tuple[str, int, int]],
    scene: str,
) -> None:
    """
    固定窗口限流：任一窗口超限即抛 429；Redis 异常时放行并记录。

    windows: [(redis_key, ttl_seconds, limit), ...]，调用方负责拼好带时间片的 key
    scene: 日志与错误提示用的场景名（如 "插班链接接口"、"登录接口"）
    """
    try:
        for key, ttl, limit in windows:
            n = await redis_async.incr(key)
            if n == 1:
                await redis_async.expire(key, ttl)
            if n > limit:
                logger.warning(f"{scene}触发限流 | key={key} | count={n}")
                raise HTTPException(status_code=429, detail="操作过于频繁，请稍后再试")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"限流计数失败（放行本次请求）: {e}")
