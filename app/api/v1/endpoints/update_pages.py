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
    stage: str = Query(default="secondary", pattern="^(primary|secondary)$"),
    district: str = Query(default="", max_length=50),
    school_type: str = Query(default="", max_length=50, alias="type"),
    gender: str = Query(default="", max_length=20),
    banding: str = Query(default="", max_length=20),
    language: str = Query(default="", max_length=50),
    religion: str = Query(default="", max_length=100),
    school_net: str = Query(default="", max_length=20),
) -> HTMLResponse:
    filters = {
        "district": district,
        "type": school_type,
        "gender": gender,
        "banding": banding,
        "language": language,
        "religion": religion,
        "school_net": school_net,
    }
    try:
        data = await admission_update_service.list_public_updates(
            db,
            page=page,
            page_size=20,
            keyword=keyword,
            stage=stage,
            district=district,
            school_type=school_type,
            gender=gender,
            banding=banding,
            language=language,
            religion=religion,
            school_net=school_net,
        )
    except HTTPException as exc:
        if exc.status_code == 404:
            return _not_found(request)
        raise
    filter_defs, filter_options = await admission_update_service.list_public_filter_options(db, stage)
    # 学段是常态视图（中学/小学两个基础列表均可索引），仅其他筛选条件触发 noindex
    filtered = bool(keyword or any(filters.values()))
    canonical_path = "/updates"
    canonical_query = []
    if stage == "primary":
        canonical_query.append("stage=primary")
    if page > 1 and not filtered:
        canonical_query.append(f"page={page}")
    if canonical_query:
        canonical_path += "?" + "&".join(canonical_query)
    canonical = f"{settings.SITE_BASE_URL}{canonical_path}"
    robots = "noindex,follow" if filtered or not data["total"] else "index,follow"
    return templates.TemplateResponse(
        request=request,
        name="updates/list.html",
        context={
            "title": "申请快讯｜香港插班",
            "description": "了解香港学校插班申请的具体变化与官方来源。",
            "canonical": canonical,
            "robots": robots,
            "data": data,
            "keyword": keyword,
            "stage": stage,
            "filters": filters,
            "filter_defs": filter_defs,
            "filter_options": filter_options,
            "filtered": filtered,
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
        "author": {"@type": "Organization", "name": "香港插班编辑组"},
        "publisher": {"@type": "Organization", "name": "香港插班"},
        "inLanguage": "zh-Hans",
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
