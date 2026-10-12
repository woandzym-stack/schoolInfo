"""页面 PV / 来源 / 核心事件统计。

仅 Redis 计数（累计 + 日维度），供后台查看，不落 MySQL。
- key: pv:{page}:total              累计 PV，不过期
- key: pv:{page}:{YYYY-MM-DD}       当日 PV，TTL 40 天
- key: pv:src:{page}:{YYYY-MM-DD}   当日来源分布 hash（field=来源，value=次数），TTL 40 天
- key: ev:{event}:total             事件累计次数，不过期
- key: ev:{event}:{YYYY-MM-DD}      事件当日次数，TTL 40 天

PV 计数前先做非浏览器流量过滤（UA 黑名单 + Sec-Fetch 导航头校验），
把扫描器/爬虫/脚本请求排除在统计外。过滤是启发式的，目标是把噪声压到可忽略，
不追求 100% 判别——肯用无头浏览器认真伪装的爬虫仍可能漏网。

计数失败只记日志，绝不影响页面正常返回。
"""

import re
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlparse

from fastapi import Request
from loguru import logger

from app.core.task_store import redis_async

# 日维度 key 保留天数
DAILY_TTL_SECONDS = 40 * 24 * 3600

# 参与统计的页面标识（与 ui.py / main.py 打点处保持一致）
TRACKED_PAGES = ("schools", "subscriptions")

# 参与统计的核心事件（与 schools.py 打点处保持一致）：
# search=搜索学校，adm_link=查看插班链接。衡量访客使用深度（真在用 vs 瞄一眼就走）。
TRACKED_EVENTS = ("search", "adm_link")

# 非真实访客的 UA 特征（子串匹配，不区分大小写）。
# bot/crawler/spider 覆盖主流搜索引擎爬虫；其余是常见扫描器、脚本客户端与无头浏览器。
_BOT_UA_PATTERN = re.compile(
    r"bot|crawler|spider|slurp|curl|wget|python-requests|python-urllib|httpx|aiohttp|"
    r"go-http-client|java/|okhttp|scrapy|postman|insomnia|"
    r"sqlmap|nikto|masscan|nmap|nuclei|zgrab|acunetix|nessus|"
    r"headlesschrome|phantomjs|selenium|puppeteer|playwright",
    re.IGNORECASE,
)

# Referer 域名中的搜索引擎归桶（子串匹配，命中的 host 统一记为右侧桶名）。
# 未命中的外链按域名原名记录；基数由站点体量自然约束，暂不需要额外截断。
_SEARCH_ENGINE_HOSTS = (
    ("google.", "google"),
    ("bing.com", "bing"),
    ("baidu.com", "baidu"),
    ("sogou.com", "sogou"),
    ("so.com", "360"),
    ("duckduckgo.com", "duckduckgo"),
    ("yahoo.", "yahoo"),
)


def _is_bot_request(request: Request) -> bool:
    """UA 黑名单判定：空 UA（脚本客户端特征）或命中爬虫/扫描器特征即为机器人。"""
    ua = request.headers.get("user-agent", "")
    return not ua or bool(_BOT_UA_PATTERN.search(ua))


def should_count(request: Request) -> bool:
    """判断该请求是否为真实浏览器导航，是否计入 PV。

    三层快速判定（任一不满足即排除）：
    1. 必须是 GET——GET 路由会被 Starlette 自动响应 HEAD 探测，扫描器常用 HEAD 探活
    2. UA 存在且不含爬虫/扫描器特征
    3. 若带 Sec-Fetch-Dest 则必须是 document——真实浏览器导航必带且为 document，
       扫描器/脚本一般不带此头（不带不拦，交给前两层兜底）
    """
    if request.method != "GET":
        return False
    if _is_bot_request(request):
        return False
    dest = request.headers.get("sec-fetch-dest")
    if dest is not None and dest != "document":
        return False
    return True


def resolve_source(request: Request) -> str:
    """解析访问来源：utm_source 优先，其次 Referer 归桶，都没有记 direct。

    - utm_source：推广链接自标注，最可靠；清洗非法字符并截断，控制 hash field 基数
    - Referer：搜索引擎映射到固定桶名；站内跳转（Referer 即本站）记 direct；
      其余外链按域名原名记录
    - 微信内置浏览器等场景不带 Referer，会落入 direct（已知偏差，看趋势够用）
    """
    utm = request.query_params.get("utm_source", "").strip().lower()
    if utm:
        utm = re.sub(r"[^a-z0-9._-]", "", utm)[:32]
        if utm:
            return utm

    referer = request.headers.get("referer", "")
    host = (urlparse(referer).hostname or "").lower() if referer else ""
    if not host:
        return "direct"

    own_host = request.headers.get("host", "").split(":")[0].lower()
    if own_host and host == own_host:
        return "direct"

    for marker, bucket in _SEARCH_ENGINE_HOSTS:
        if marker in host:
            return bucket
    return host.removeprefix("www.")


async def incr_pv(page: str, request: Request) -> None:
    """过滤非浏览器流量后，累计 PV + 当日 PV + 来源分布（pipeline 一次往返）。失败静默降级，只记日志。"""
    if not should_count(request):
        return
    try:
        today = date.today().isoformat()
        daily_key = f"pv:{page}:{today}"
        src_key = f"pv:src:{page}:{today}"
        async with redis_async.pipeline(transaction=False) as pipe:
            pipe.incr(f"pv:{page}:total")
            pipe.incr(daily_key)
            pipe.expire(daily_key, DAILY_TTL_SECONDS)
            pipe.hincrby(src_key, resolve_source(request), 1)
            pipe.expire(src_key, DAILY_TTL_SECONDS)
            await pipe.execute()
    except Exception as e:
        logger.error(f"PV incr error for page={page}: {e}")


async def incr_event(name: str, request: Request) -> None:
    """核心事件计数（搜索/查看插班链接等）。

    事件由前端 XHR 触发，sec-fetch-dest 是 empty 而非 document，
    因此只做 UA 黑名单过滤，不套用 PV 的 Sec-Fetch 导航校验。
    """
    if _is_bot_request(request):
        return
    try:
        daily_key = f"ev:{name}:{date.today().isoformat()}"
        async with redis_async.pipeline(transaction=False) as pipe:
            pipe.incr(f"ev:{name}:total")
            pipe.incr(daily_key)
            pipe.expire(daily_key, DAILY_TTL_SECONDS)
            await pipe.execute()
    except Exception as e:
        logger.error(f"event incr error for event={name}: {e}")


def _window_dates(days: int) -> list[str]:
    """最近 N 天日期列表（升序，含今天），N 截断到日 key 保留上限 40 天。"""
    days = max(1, min(days, 40))
    today = date.today()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(days)]
    dates.reverse()
    return dates


async def _counter_overview(prefix: str, names: tuple[str, ...], dates: list[str]) -> dict[str, dict[str, Any]]:
    """通用计数概览：{name: {"total": int, "daily": {date: int}}}（mget 一次往返）。"""
    days = len(dates)
    keys = [f"{prefix}:{name}:total" for name in names]
    keys += [f"{prefix}:{name}:{d}" for name in names for d in dates]
    values = await redis_async.mget(keys)

    overview: dict[str, dict[str, Any]] = {}
    for idx, name in enumerate(names):
        total = int(values[idx] or 0)
        daily_values = values[len(names) + idx * days : len(names) + (idx + 1) * days]
        overview[name] = {
            "total": total,
            "daily": {d: int(v or 0) for d, v in zip(dates, daily_values)},
        }
    return overview


async def _source_overview(dates: list[str]) -> dict[str, dict[str, int]]:
    """各页面在所选窗口内的来源汇总：{page: {source: count}}（pipeline 一次往返）。"""
    async with redis_async.pipeline(transaction=False) as pipe:
        for page in TRACKED_PAGES:
            for d in dates:
                pipe.hgetall(f"pv:src:{page}:{d}")
        results = await pipe.execute()

    merged: dict[str, dict[str, int]] = {page: {} for page in TRACKED_PAGES}
    i = 0
    for page in TRACKED_PAGES:
        for _ in dates:
            for src, n in results[i].items():
                merged[page][src] = merged[page].get(src, 0) + int(n)
            i += 1
    return merged


async def get_pv_overview(days: int = 7) -> dict[str, dict[str, Any]]:
    """各页面累计 PV + 最近 N 天日 PV + 窗口内来源分布。

    返回结构: {page: {"total": int, "daily": {"2026-10-08": 12, ...}, "sources": {"google": 5, ...}}}
    """
    dates = _window_dates(days)
    overview = await _counter_overview("pv", TRACKED_PAGES, dates)
    sources = await _source_overview(dates)
    for page in TRACKED_PAGES:
        overview[page]["sources"] = sources[page]
    return overview


async def get_event_overview(days: int = 7) -> dict[str, dict[str, Any]]:
    """各核心事件累计次数 + 最近 N 天日次数。返回结构与 PV 概览一致。"""
    return await _counter_overview("ev", TRACKED_EVENTS, _window_dates(days))
