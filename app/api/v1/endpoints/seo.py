"""SEO 基础设施：robots.txt 与动态 sitemap.xml。"""
from typing import Annotated
from xml.etree import ElementTree

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.db import get_async_db
from app.services import admission_update_service

seo_router = APIRouter(tags=["SEO"])

ROBOTS_TEMPLATE = """User-agent: *
Allow: /

Sitemap: {base}/sitemap.xml
"""
SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"
ElementTree.register_namespace("", SITEMAP_NAMESPACE)


@seo_router.get("/robots.txt", include_in_schema=False)
async def robots_txt() -> PlainTextResponse:
    return PlainTextResponse(ROBOTS_TEMPLATE.format(base=settings.SITE_BASE_URL))


@seo_router.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml(db: Annotated[AsyncSession, Depends(get_async_db)]) -> Response:
    """每次读取公开快讯；数据库失败时由全局异常处理器返回 500，而非空 sitemap。"""
    updates = await admission_update_service.list_public_sitemap_updates(db)
    root = ElementTree.Element(f"{{{SITEMAP_NAMESPACE}}}urlset")

    def add_url(path: str, lastmod: str | None = None) -> None:
        node = ElementTree.SubElement(root, f"{{{SITEMAP_NAMESPACE}}}url")
        ElementTree.SubElement(node, f"{{{SITEMAP_NAMESPACE}}}loc").text = f"{settings.SITE_BASE_URL}{path}"
        if lastmod:
            ElementTree.SubElement(node, f"{{{SITEMAP_NAMESPACE}}}lastmod").text = lastmod

    add_url("/")
    if updates:
        add_url("/updates")
        for update in updates:
            add_url(f"/updates/{update['id']}", update["lastmod"])
    content = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
    return Response(content=content, media_type="application/xml")
