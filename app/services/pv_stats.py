"""页面 PV 统计。

仅 Redis 计数（累计 + 日维度），供后台查看，不落 MySQL。
- key: pv:{page}:total            累计 PV，不过期
- key: pv:{page}:{YYYY-MM-DD}     当日 PV，TTL 40 天，过期自动清理

计数前先做非浏览器流量过滤（UA 黑名单 + Sec-Fetch 导航头校验），
把扫描器/爬虫/脚本请求排除在统计外。过滤是启发式的，目标是把噪声压到可忽略，
不追求 100% 判别——肯用无头浏览器认真伪装的爬虫仍可能漏网。

计数失败只记日志，绝不影响页面正常返回。
"""

import re
from datetime import date, timedelta
from typing import Any

from fastapi import Request
from loguru import logger

from app.core.task_store import redis_async

# 日维度 key 保留天数
DAILY_TTL_SECONDS = 40 * 24 * 3600

# 参与统计的页面标识（与 ui.py 打点处保持一致）
TRACKED_PAGES = ("schools", "subscriptions")

# 非真实访客的 UA 特征（子串匹配，不区分大小写）。
# bot/crawler/spider 覆盖主流搜索引擎爬虫；其余是常见扫描器、脚本客户端与无头浏览器。
_BOT_UA_PATTERN = re.compile(
    r"bot|crawler|spider|slurp|curl|wget|python-requests|python-urllib|httpx|aiohttp|"
    r"go-http-client|java/|okhttp|scrapy|postman|insomnia|"
    r"sqlmap|nikto|masscan|nmap|nuclei|zgrab|acunetix|nessus|"
    r"headlesschrome|phantomjs|selenium|puppeteer|playwright",
    re.IGNORECASE,
)


def should_count(request: Request) -> bool:
    """判断该请求是否为真实浏览器导航，是否计入 PV。

    三层快速判定（任一不满足即排除）：
    1. 必须是 GET——GET 路由会被 Starlette 自动响应 HEAD 探测，扫描器常用 HEAD 探活
    2. UA 存在且不含爬虫/扫描器特征——空 UA 是脚本客户端的典型特征
    3. 若带 Sec-Fetch-Dest 则必须是 document——真实浏览器导航必带且为 document，
       扫描器/脚本一般不带此头（不带不拦，交给前两层与 UA 兜底）
    """
    if request.method != "GET":
        return False
    ua = request.headers.get("user-agent", "")
    if not ua or _BOT_UA_PATTERN.search(ua):
        return False
    dest = request.headers.get("sec-fetch-dest")
    if dest is not None and dest != "document":
        return False
    return True


async def incr_pv(page: str, request: Request) -> None:
    """过滤非浏览器流量后，累计 PV + 当日 PV 各加 1（pipeline 一次往返）。失败静默降级，只记日志。"""
    if not should_count(request):
        return
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
