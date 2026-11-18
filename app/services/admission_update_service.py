"""插班动态与抓取候选的轻量业务流：候选生成草稿，人工编辑后发布。"""
from datetime import date, datetime, timedelta, timezone
from math import ceil
from typing import Any, Optional
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.admission_change_reviews import AdmissionChangeReviews
from app.models.admission_changes import AdmissionChanges
from app.models.admission_updates import AdmissionUpdates
from app.models.schools import Schools
from app.schemas.admission_update import AdmissionUpdateContent, AdmissionUpdateCreate

HK_TZ = timezone(timedelta(hours=8))
# 公开动态页学校筛选维度：与学校名录一致，按学段联动（全部学段仅公共维度）
PUBLIC_FILTER_LABELS = {
    "district": "地区",
    "type": "学校类型",
    "gender": "性别",
    "banding": "组别",
    "language": "教学语言",
    "school_net": "校网",
    "religion": "宗教",
}
PUBLIC_FILTER_KEYS = {
    "": ("district", "type", "gender", "religion"),
    "secondary": ("district", "banding", "type", "gender", "language", "religion"),
    "primary": ("district", "type", "gender", "school_net", "religion"),
}
CHANGE_KIND_LABELS = {
    "announcement": "安排公布",
    "opened": "开放申请",
    "deadline_changed": "日期调整",
    "requirements_changed": "条件或材料调整",
    "grades_changed": "年级调整",
    "assessment_changed": "笔试／面试安排",
    "closed": "停止接受申请",
    "entry_updated": "入口调整",
    "other": "其他变化",
}
# 候选生成草稿时的预填标题短语：学校名 + 变化描述（公开站点统一简体，校名保留数据库原文）
CANDIDATE_TITLE_PHRASES = {
    "added": "新增申请入口",
    "removed": "移除申请入口",
    "text_changed": "申请页面文字更新",
    "grades_changed": "申请年级调整",
    "content_changed": "申请页面内容更新",
}


def hk_now() -> datetime:
    """数据库沿用东八区 naive datetime，不依赖服务器本地时区。"""
    return datetime.now(HK_TZ).replace(tzinfo=None)


def _hk_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=HK_TZ).isoformat()
    return value.astimezone(HK_TZ).isoformat()


def _normalize_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(HK_TZ).replace(tzinfo=None)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _safe_http_url(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        return None
    if parsed.username or parsed.password:
        return None
    return value


async def _school_or_404(db: AsyncSession, school_id: int) -> Schools:
    school: Optional[Schools] = (await db.exec(select(Schools).where(Schools.id == school_id))).first()
    if school is None:
        raise HTTPException(status_code=404, detail="学校不存在")
    return school


async def _update_or_none(db: AsyncSession, update_id: int) -> Optional[AdmissionUpdates]:
    return (await db.exec(select(AdmissionUpdates).where(AdmissionUpdates.id == update_id))).first()


def _school_brief(school: Schools) -> dict[str, Any]:
    return {
        "id": school.id,
        "name": school.name,
        "simple_name": school.simple_name,
        "stage": school.stage,
        "district": school.district,
        "url": _safe_http_url(school.url),
    }


def _public_list_item(update: AdmissionUpdates, school: Schools) -> dict[str, Any]:
    return {
        "id": update.id,
        "change_kind": update.change_kind,
        "change_kind_label": CHANGE_KIND_LABELS.get(update.change_kind, "其他变化"),
        "title": update.title,
        "summary": update.summary,
        "verified_at": _hk_iso(update.verified_at),
        "first_published_at": _hk_iso(update.first_published_at),
        "content_modified_at": _hk_iso(update.content_modified_at),
        "school": _school_brief(school),
    }


def _public_detail(update: AdmissionUpdates, school: Schools) -> dict[str, Any]:
    data = _public_list_item(update, school)
    data["sources"] = update.sources_json
    return data


async def list_public_updates(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    keyword: str = "",
    stage: str = "",
    change_kind: str = "",
    district: str = "",
    school_type: str = "",
    gender: str = "",
    banding: str = "",
    language: str = "",
    religion: str = "",
    school_net: str = "",
) -> dict[str, Any]:
    """公开 API 与 SSR 共用的可见性和筛选规则。"""
    conditions: list[Any] = [AdmissionUpdates.status == "published"]
    if stage:
        conditions.append(Schools.stage == stage)
    if change_kind:
        conditions.append(AdmissionUpdates.change_kind == change_kind)
    if district:
        conditions.append(Schools.district == district)
    if school_type:
        conditions.append(Schools.type == school_type)
    if gender:
        conditions.append(Schools.gender == gender)
    if language:
        conditions.append(Schools.language == language)
    if religion:
        conditions.append(Schools.religion == religion)
    if school_net:
        conditions.append(Schools.school_net == school_net)
    if banding:
        # 与名录一致：组别统一前缀匹配，选 '1' 即整档（1A/1B/1C…）
        conditions.append(col(Schools.banding).like(f"{_escape_like(banding)}%", escape="\\"))
    keyword = keyword.strip()
    if keyword:
        escaped = _escape_like(keyword)
        conditions.append(
            (col(Schools.name).like(f"%{escaped}%", escape="\\"))
            | (col(Schools.simple_name).like(f"%{escaped}%", escape="\\"))
        )

    count_stmt = (
        select(func.count(col(AdmissionUpdates.id)))
        .select_from(AdmissionUpdates)
        .join(Schools, col(Schools.id) == col(AdmissionUpdates.school_id))
        .where(*conditions)
    )
    total = int((await db.exec(count_stmt)).one())
    pages = ceil(total / page_size) if total else 0
    if page < 1 or (pages and page > pages) or (not pages and page != 1):
        raise HTTPException(status_code=404, detail="分页不存在")

    stmt = (
        select(AdmissionUpdates, Schools)
        .join(Schools, col(Schools.id) == col(AdmissionUpdates.school_id))
        .where(*conditions)
        .order_by(col(AdmissionUpdates.first_published_at).desc(), col(AdmissionUpdates.id).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.exec(stmt)).all()
    return {
        "items": [_public_list_item(update, school) for update, school in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": pages,
    }


async def list_public_filter_options(
    db: AsyncSession, stage: str = ""
) -> tuple[list[dict[str, str]], dict[str, list[str]]]:
    """动态页学校筛选字段与选项：与名录同源按学段 distinct；校网排除 '0' 按编号排序，组别插入整档。"""
    keys = PUBLIC_FILTER_KEYS.get(stage, PUBLIC_FILTER_KEYS[""])
    defs = [{"key": key, "label": PUBLIC_FILTER_LABELS[key]} for key in keys]
    options: dict[str, list[str]] = {}
    for key in keys:
        column = getattr(Schools, key)
        stmt = select(column).where(col(column).is_not(None), column != "").distinct()
        if stage:
            stmt = stmt.where(Schools.stage == stage)
        values = sorted(value for value in (await db.exec(stmt)).all() if value)
        if key == "school_net":
            values = sorted(
                (value for value in values if value != "0"),
                key=lambda value: int(value) if value.isdigit() else 0,
            )
        if key == "banding":
            tiered: list[str] = []
            seen: set[str] = set()
            for value in values:
                tier = value[0]
                if tier not in seen:
                    seen.add(tier)
                    if len(value) > 1:
                        tiered.append(tier)
                tiered.append(value)
            values = tiered
        options[key] = values
    return defs, options


async def get_public_update(db: AsyncSession, update_id: int) -> Optional[dict[str, Any]]:
    stmt = (
        select(AdmissionUpdates, Schools)
        .join(Schools, col(Schools.id) == col(AdmissionUpdates.school_id))
        .where(AdmissionUpdates.id == update_id, AdmissionUpdates.status == "published")
    )
    row = (await db.exec(stmt)).first()
    return _public_detail(row[0], row[1]) if row else None


async def list_public_sitemap_updates(db: AsyncSession) -> list[dict[str, Any]]:
    stmt = select(AdmissionUpdates.id, AdmissionUpdates.content_modified_at, AdmissionUpdates.first_published_at).where(
        AdmissionUpdates.status == "published"
    )
    rows = (await db.exec(stmt)).all()
    return [
        {
            "id": update_id,
            "lastmod": _hk_iso(content_modified_at or first_published_at),
        }
        for update_id, content_modified_at, first_published_at in rows
    ]


def _admin_detail(update: AdmissionUpdates, school: Schools, candidate_ids: list[int]) -> dict[str, Any]:
    return {
        **_public_detail(update, school),
        # 编辑器学校下拉绑定 school_id；候选生成的草稿学校已关联且不可改，需随详情返回用于回显与保存校验
        "school_id": update.school_id,
        "status": update.status,
        "deleted_reason": update.deleted_reason,
        "created_by": update.created_by,
        "updated_by": update.updated_by,
        "created_at": _hk_iso(update.created_at),
        "updated_at": _hk_iso(update.updated_at),
        "candidate_ids": candidate_ids,
    }


async def get_admin_update(db: AsyncSession, update_id: int) -> dict[str, Any]:
    stmt = (
        select(AdmissionUpdates, Schools)
        .join(Schools, col(Schools.id) == col(AdmissionUpdates.school_id))
        .where(AdmissionUpdates.id == update_id)
    )
    row = (await db.exec(stmt)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="动态不存在")
    candidate_ids = list(
        (
            await db.exec(
                select(AdmissionChangeReviews.change_id).where(AdmissionChangeReviews.update_id == update_id)
            )
        ).all()
    )
    return _admin_detail(row[0], row[1], candidate_ids)


async def list_admin_updates(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status: str = "",
    keyword: str = "",
    change_kind: str = "",
    school_id: Optional[int] = None,
    district: str = "",
    stage: str = "",
) -> dict[str, Any]:
    conditions: list[Any] = []
    if status:
        conditions.append(AdmissionUpdates.status == status)
    else:
        # 默认列表不含已删除记录；查看已删除需显式选择状态筛选
        conditions.append(AdmissionUpdates.status != "deleted")
    if change_kind:
        conditions.append(AdmissionUpdates.change_kind == change_kind)
    if school_id is not None:
        conditions.append(AdmissionUpdates.school_id == school_id)
    if district:
        conditions.append(Schools.district == district)
    if stage:
        conditions.append(Schools.stage == stage)
    keyword = keyword.strip()
    if keyword:
        escaped = _escape_like(keyword)
        conditions.append(
            (col(Schools.name).like(f"%{escaped}%", escape="\\"))
            | (col(Schools.simple_name).like(f"%{escaped}%", escape="\\"))
        )
    count_stmt = (
        select(func.count(col(AdmissionUpdates.id)))
        .select_from(AdmissionUpdates)
        .join(Schools, col(Schools.id) == col(AdmissionUpdates.school_id))
        .where(*conditions)
    )
    total = int((await db.exec(count_stmt)).one())
    pages = ceil(total / page_size) if total else 0
    if page < 1 or (pages and page > pages) or (not pages and page != 1):
        raise HTTPException(status_code=404, detail="分页不存在")
    stmt = (
        select(AdmissionUpdates, Schools)
        .join(Schools, col(Schools.id) == col(AdmissionUpdates.school_id))
        .where(*conditions)
        .order_by(col(AdmissionUpdates.updated_at).desc(), col(AdmissionUpdates.id).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.exec(stmt)).all()
    items = []
    for update, school in rows:
        items.append(
            {
                **_public_list_item(update, school),
                "status": update.status,
                "updated_at": _hk_iso(update.updated_at),
            }
        )
    return {"items": items, "page": page, "page_size": page_size, "total": total, "pages": pages}


async def list_candidates(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status: str = "pending",
    school_id: Optional[int] = None,
    detected_on: Optional[date] = None,
    change_type: str = "",
    district: str = "",
    stage: str = "",
) -> dict[str, Any]:
    conditions: list[Any] = []
    if status == "pending":
        conditions.append(col(AdmissionChangeReviews.change_id).is_(None))
        # 与已采用变化同键（同校同 URL 同类型同新值）的重复上报不再出现在待处理；
        # 原始记录仍可在"全部"视图查看并手动忽略
        adopted = aliased(AdmissionChanges)
        duplicate_of_adopted = (
            select(adopted.id)
            .join(AdmissionChangeReviews, col(AdmissionChangeReviews.change_id) == col(adopted.id))
            .where(
                adopted.school_id == AdmissionChanges.school_id,
                adopted.url == AdmissionChanges.url,
                adopted.change_type == AdmissionChanges.change_type,
                func.coalesce(adopted.new_value, "") == func.coalesce(AdmissionChanges.new_value, ""),
            )
        )
        conditions.append(~duplicate_of_adopted.exists())
    elif status in ("adopted", "ignored"):
        conditions.append(AdmissionChangeReviews.status == status)
    if school_id is not None:
        conditions.append(AdmissionChanges.school_id == school_id)
    if detected_on is not None:
        conditions.append(func.date(AdmissionChanges.detected_at) == detected_on)
    if change_type:
        conditions.append(AdmissionChanges.change_type == change_type)
    if district:
        conditions.append(Schools.district == district)
    if stage:
        conditions.append(Schools.stage == stage)

    join_condition = col(AdmissionChangeReviews.change_id) == col(AdmissionChanges.id)
    count_stmt = (
        select(func.count(col(AdmissionChanges.id)))
        .select_from(AdmissionChanges)
        .join(Schools, col(Schools.id) == col(AdmissionChanges.school_id))
        .outerjoin(AdmissionChangeReviews, join_condition)
        .where(*conditions)
    )
    total = int((await db.exec(count_stmt)).one())
    pages = ceil(total / page_size) if total else 0
    if page < 1 or (pages and page > pages) or (not pages and page != 1):
        raise HTTPException(status_code=404, detail="分页不存在")

    stmt = (
        select(AdmissionChanges, Schools, AdmissionChangeReviews)
        .join(Schools, col(Schools.id) == col(AdmissionChanges.school_id))
        .outerjoin(AdmissionChangeReviews, join_condition)
        .where(*conditions)
        .order_by(col(AdmissionChanges.detected_at).desc(), col(AdmissionChanges.id).desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.exec(stmt)).all()
    items = []
    for change, school, review in rows:
        items.append(
            {
                "id": change.id,
                "school": _school_brief(school),
                "url": _safe_http_url(change.url),
                "change_type": change.change_type,
                "old_value": change.old_value,
                "new_value": change.new_value,
                "source": change.source,
                "detected_at": _hk_iso(change.detected_at),
                "status": review.status if review else "pending",
                "update_id": review.update_id if review else None,
            }
        )
    return {"items": items, "page": page, "page_size": page_size, "total": total, "pages": pages}


async def list_school_districts(db: AsyncSession) -> list[str]:
    """地区筛选选项：schools 表 distinct 非空地区，与名录数据保持一致。"""
    stmt = (
        select(Schools.district)
        .where(col(Schools.district).is_not(None), Schools.district != "")
        .distinct()
        .order_by(col(Schools.district))
    )
    return [district for district in (await db.exec(stmt)).all() if district]


def _apply_content(update: AdmissionUpdates, payload: AdmissionUpdateContent) -> None:
    update.change_kind = payload.change_kind
    update.title = payload.title
    update.summary = payload.summary
    update.sources_json = payload.sources_for_storage()
    update.verified_at = _normalize_datetime(payload.verified_at)


async def create_update(db: AsyncSession, payload: AdmissionUpdateCreate, user_id: int) -> dict[str, Any]:
    change: Optional[AdmissionChanges] = None
    if payload.candidate_id is not None:
        change = (
            await db.exec(select(AdmissionChanges).where(AdmissionChanges.id == payload.candidate_id))
        ).first()
        if change is None:
            raise HTTPException(status_code=404, detail="候选变化不存在")
        if payload.school_id != change.school_id:
            raise HTTPException(status_code=422, detail="候选与学校不匹配")
        if _safe_http_url(change.url) is None:
            raise HTTPException(status_code=422, detail="候选 URL 不是合法的 HTTP(S) 地址，不能生成草稿")
        review = (
            await db.exec(select(AdmissionChangeReviews).where(AdmissionChangeReviews.change_id == change.id))
        ).first()
        if review and review.status == "adopted" and review.update_id is not None:
            return await get_admin_update(db, review.update_id)
        if review and review.status == "ignored":
            raise HTTPException(status_code=409, detail="候选已忽略，请先恢复待处理")

    school = await _school_or_404(db, payload.school_id)
    now = hk_now()
    update = AdmissionUpdates(
        school_id=school.id,
        created_by=user_id,
        updated_by=user_id,
        created_at=now,
        updated_at=now,
    )
    _apply_content(update, payload)
    if change is not None:
        if not update.title:
            phrase = CANDIDATE_TITLE_PHRASES.get(change.change_type, "申请页面更新")
            update.title = f"{school.name}{phrase}"[:120]
        if not update.sources_json:
            update.sources_json = [{"name": "学校申请页面", "url": change.url, "support": ""}]

    try:
        db.add(update)
        await db.flush()
        if change is not None:
            db.add(
                AdmissionChangeReviews(
                    change_id=change.id,
                    status="adopted",
                    update_id=update.id,
                    reviewed_by=user_id,
                    reviewed_at=now,
                )
            )
            # 同键（同校同 URL 同类型同新值）的重复检测记录一并关联到本草稿，待处理池不再重复出现
            duplicates = (
                await db.exec(
                    select(AdmissionChanges)
                    .outerjoin(
                        AdmissionChangeReviews, col(AdmissionChangeReviews.change_id) == col(AdmissionChanges.id)
                    )
                    .where(
                        AdmissionChanges.id != change.id,
                        AdmissionChanges.school_id == change.school_id,
                        AdmissionChanges.url == change.url,
                        AdmissionChanges.change_type == change.change_type,
                        func.coalesce(AdmissionChanges.new_value, "") == func.coalesce(change.new_value or "", ""),
                        col(AdmissionChangeReviews.change_id).is_(None),
                    )
                )
            ).all()
            for duplicate in duplicates:
                db.add(
                    AdmissionChangeReviews(
                        change_id=duplicate.id,
                        status="adopted",
                        update_id=update.id,
                        reviewed_by=user_id,
                        reviewed_at=now,
                    )
                )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if change is not None:
            raise HTTPException(status_code=409, detail="候选已被其他编辑采用，请刷新候选池") from exc
        raise
    except Exception:
        await db.rollback()
        raise
    return await get_admin_update(db, update.id)


async def update_content(
    db: AsyncSession, update_id: int, payload: AdmissionUpdateContent, user_id: int
) -> dict[str, Any]:
    update = await _update_or_none(db, update_id)
    if update is None:
        raise HTTPException(status_code=404, detail="动态不存在")
    if update.status == "deleted":
        raise HTTPException(status_code=409, detail="已删除动态不能直接编辑，请先恢复为草稿")
    if update.status == "published":
        errors = payload.publish_errors()
        if errors:
            raise HTTPException(status_code=422, detail="；".join(errors))
    now = hk_now()
    _apply_content(update, payload)
    update.updated_by = user_id
    update.updated_at = now
    if update.status == "published":
        update.content_modified_at = now
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return await get_admin_update(db, update.id)


async def publish_update(db: AsyncSession, update_id: int, user_id: int) -> dict[str, Any]:
    update = await _update_or_none(db, update_id)
    if update is None:
        raise HTTPException(status_code=404, detail="动态不存在")
    if update.status == "deleted":
        raise HTTPException(status_code=409, detail="已删除动态不能发布，请先恢复为草稿")
    if update.status == "published":
        return await get_admin_update(db, update.id)
    payload = AdmissionUpdateContent.model_validate(
        {
            "change_kind": update.change_kind,
            "title": update.title,
            "summary": update.summary,
            "sources": update.sources_json,
            "verified_at": update.verified_at,
        }
    )
    errors = payload.publish_errors()
    if errors:
        raise HTTPException(status_code=422, detail="；".join(errors))
    now = hk_now()
    update.status = "published"
    update.first_published_at = update.first_published_at or now
    update.content_modified_at = now
    update.updated_by = user_id
    update.updated_at = now
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return await get_admin_update(db, update.id)


async def delete_update(db: AsyncSession, update_id: int, reason: str, user_id: int) -> dict[str, Any]:
    update = await _update_or_none(db, update_id)
    if update is None:
        raise HTTPException(status_code=404, detail="动态不存在")
    if update.status != "deleted":
        if update.status == "published" and not reason:
            raise HTTPException(status_code=422, detail="已发布动态删除需填写原因")
        update.status = "deleted"
        update.deleted_reason = reason or None
        if update.first_published_at is None:
            # 从未发布的草稿：删除即放弃本次编辑，释放候选关联，候选恢复待处理可重新生成
            reviews = (
                await db.exec(select(AdmissionChangeReviews).where(AdmissionChangeReviews.update_id == update_id))
            ).all()
            for review in reviews:
                await db.delete(review)
        update.updated_by = user_id
        update.updated_at = hk_now()
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return await get_admin_update(db, update.id)


async def restore_update(db: AsyncSession, update_id: int, user_id: int) -> dict[str, Any]:
    update = await _update_or_none(db, update_id)
    if update is None:
        raise HTTPException(status_code=404, detail="动态不存在")
    if update.status != "deleted":
        return await get_admin_update(db, update.id)
    update.status = "draft"
    update.deleted_reason = None
    update.updated_by = user_id
    update.updated_at = hk_now()
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return await get_admin_update(db, update.id)


async def ignore_candidate(db: AsyncSession, change_id: int, user_id: int) -> dict[str, Any]:
    change = (await db.exec(select(AdmissionChanges).where(AdmissionChanges.id == change_id))).first()
    if change is None:
        raise HTTPException(status_code=404, detail="候选变化不存在")
    review = (
        await db.exec(select(AdmissionChangeReviews).where(AdmissionChangeReviews.change_id == change_id))
    ).first()
    if review and review.status == "adopted":
        raise HTTPException(status_code=409, detail="候选已采用，不能忽略")
    if review is None:
        review = AdmissionChangeReviews(
            change_id=change_id,
            status="ignored",
            reviewed_by=user_id,
            reviewed_at=hk_now(),
        )
        db.add(review)
    else:
        review.status = "ignored"
        review.reviewed_by = user_id
        review.reviewed_at = hk_now()
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="候选状态已变化，请刷新后重试") from exc
    except Exception:
        await db.rollback()
        raise
    return {"change_id": change_id, "status": "ignored"}


async def restore_candidate(db: AsyncSession, change_id: int) -> dict[str, Any]:
    review = (
        await db.exec(select(AdmissionChangeReviews).where(AdmissionChangeReviews.change_id == change_id))
    ).first()
    if review and review.status == "adopted":
        raise HTTPException(status_code=409, detail="已采用候选不能恢复待处理")
    if review is not None:
        await db.delete(review)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return {"change_id": change_id, "status": "pending"}
