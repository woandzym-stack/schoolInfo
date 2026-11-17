from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.db import get_async_db
from app.core.templates import templates
from app.services import admission_update_service

page_router = APIRouter(include_in_schema=False)


def _not_found(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="updates/404.html",
        context={
            "title": "快讯不存在｜香港插班",
            "description": "快讯不存在或尚未公开。",
            "canonical": None,
            "robots": "noindex",
        },
        status_code=404,
    )


@page_router.get("/updates", response_class=HTMLResponse)
async def updates_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_db)],
    page: int = Query(default=1, ge=1),
    keyword: str = Query(default="", max_length=100),
    stage: str = Query(default="", pattern="^(|primary|secondary)$"),
    change_kind: str = Query(default="", max_length=30),
) -> HTMLResponse:
    try:
        data = await admission_update_service.list_public_updates(
            db,
            page=page,
            page_size=20,
            keyword=keyword,
            stage=stage,
            change_kind=change_kind,
        )
    except HTTPException as exc:
        if exc.status_code == 404:
            return _not_found(request)
        raise
    filtered = bool(keyword or stage or change_kind)
    canonical = f"{settings.SITE_BASE_URL}/updates"
    if page > 1 and not filtered:
        canonical += f"?page={page}"
    robots = "noindex,follow" if filtered or not data["total"] else "index,follow"
    return templates.TemplateResponse(
        request=request,
        name="updates/list.html",
        context={
            "title": "申請快訊｜香港插班",
            "description": "了解香港學校插班申請的具體變化、適用對象、下一步與官方來源。",
            "canonical": canonical,
            "robots": robots,
            "data": data,
            "keyword": keyword,
            "stage": stage,
            "change_kind": change_kind,
            "kind_labels": admission_update_service.CHANGE_KIND_LABELS,
            "page_numbers": list(range(max(1, page - 2), min(data["pages"], page + 2) + 1)),
        },
    )


@page_router.get("/updates/{update_id}", response_class=HTMLResponse)
async def update_detail_page(
    update_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> HTMLResponse:
    data = await admission_update_service.get_public_update(db, update_id)
    if data is None:
        return _not_found(request)
    canonical = f"{settings.SITE_BASE_URL}/updates/{update_id}"
    json_ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": data["title"],
        "description": data["summary"],
        "datePublished": data["first_published_at"],
        "dateModified": data["content_modified_at"] or data["first_published_at"],
        "mainEntityOfPage": canonical,
        "author": {"@type": "Organization", "name": "香港插班編輯組"},
        "publisher": {"@type": "Organization", "name": "香港插班"},
        "inLanguage": "zh-Hant",
    }
    return templates.TemplateResponse(
        request=request,
        name="updates/detail.html",
        context={
            "title": f"{data['title']}｜香港插班",
            "description": data["summary"],
            "canonical": canonical,
            "robots": "index,follow",
            "update": data,
            "json_ld": json_ld,
        },
    )
