"""SEO 基础设施：robots.txt 与 sitemap.xml。

挂在站点根路径（不带 /api/v1 前缀），由 main.py 直接注册。
注意：不要屏蔽 /api/ 或 /static/，名录页渲染依赖 API 与 JS/CSS。
"""
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response

from app.core.config import settings

seo_router = APIRouter(tags=["SEO"])

ROBOTS_TEMPLATE = """User-agent: *
Allow: /

Sitemap: {base}/sitemap.xml
"""

# 初期仅列已上线、返回 200、允许索引的规范页面；
# 学校页 / 地区页上线后在此追加。不列 API、登录、订阅、统计与重定向页。
SITEMAP_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{base}/</loc></url>
</urlset>
"""


@seo_router.get("/robots.txt", include_in_schema=False)
async def robots_txt() -> PlainTextResponse:
    return PlainTextResponse(ROBOTS_TEMPLATE.format(base=settings.SITE_BASE_URL))


@seo_router.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml() -> Response:
    return Response(content=SITEMAP_TEMPLATE.format(base=settings.SITE_BASE_URL), media_type="application/xml")
