"""
订阅业务逻辑（规则见 docs/注册订阅功能实现方案.md §2）。

- 粒度：（用户 × 学校 × 年级）一行一条；年级多选展开，不选存 all
- 覆盖合并：已订 all 再订具体年级 → 静默吞掉；已订具体年级再订 all → 先删后插
- 幂等：重复订阅返回成功；唯一约束 uk_sub_user_school_grade 物理兜底
- 上限：每用户最多订阅 20 所学校（COUNT(DISTINCT school_id) 判定）
"""
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List

from fastapi import HTTPException
from sqlalchemy import delete, func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.admission_links import AdmissionLinks
from app.models.schools import Schools
from app.models.subscriptions import Subscriptions

MAX_SCHOOLS_PER_USER = 20

VALID_GRADES = {
    "primary": {f"P{i}" for i in range(1, 7)},
    "secondary": {f"S{i}" for i in range(1, 7)},
}


async def _get_school_or_404(db: AsyncSession, school_id: int) -> Schools:
    school = (await db.exec(select(Schools).where(Schools.id == school_id))).first()
    if school is None:
        raise HTTPException(status_code=404, detail="学校不存在")
    return school


def _validate_grades(stage: str, grades: List[str]) -> None:
    """订阅年级必须与学校学段一致（小学 P1-P6 / 中学 S1-S6）。"""
    valid = VALID_GRADES.get(stage, set())
    invalid = [g for g in grades if g != "all" and g not in valid]
    if invalid:
        raise HTTPException(status_code=422, detail=f"年级与学校学段不符: {', '.join(invalid)}")


async def _subscribed_school_count(db: AsyncSession, user_id: int) -> int:
    stmt = select(func.count(func.distinct(Subscriptions.school_id))).where(Subscriptions.user_id == user_id)
    return (await db.exec(stmt)).one()


async def list_mine(db: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
    """我的订阅列表：按学校聚合，带学校基本信息，按订阅时间倒序。"""
    stmt = (
        select(Subscriptions, Schools)
        .join(Schools, col(Schools.id) == col(Subscriptions.school_id))
        .where(Subscriptions.user_id == user_id)
        .order_by(col(Subscriptions.created_at).desc())
    )
    rows = (await db.exec(stmt)).all()

    grouped: Dict[int, Dict[str, Any]] = {}
    for sub, school in rows:
        g = grouped.get(school.id)
        if g is None:
            g = grouped[school.id] = {
                "school_id": school.id,
                "name": school.name,
                "stage": school.stage,
                "district": school.district,
                "grades": [],
                "subscribed_at": sub.created_at.isoformat(),
            }
        g["grades"].append(sub.grade)
    return list(grouped.values())


async def subscribe(db: AsyncSession, user_id: int, school_id: int, grades: List[str]) -> Dict[str, Any]:
    """
    订阅（幂等）：校验学校与年级 → 上限检查 → 覆盖合并 → 返回该校最终订阅状态。
    grades 为空或含 'all' 均视为订阅全部年级。
    """
    school = await _get_school_or_404(db, school_id)
    _validate_grades(school.stage, grades)

    existing_stmt = select(Subscriptions).where(
        Subscriptions.user_id == user_id, Subscriptions.school_id == school_id
    )
    existing = (await db.exec(existing_stmt)).all()
    existing_grades = {s.grade for s in existing}

    want_all = not grades or "all" in grades

    # 新学校才占订阅名额（两个分支共用，必须在任何插入之前检查）
    if not existing:
        count = await _subscribed_school_count(db, user_id)
        if count >= MAX_SCHOOLS_PER_USER:
            raise HTTPException(status_code=400, detail=f"最多订阅 {MAX_SCHOOLS_PER_USER} 所学校")

    if want_all:
        if existing_grades != {"all"}:
            # 语义扩大到全校：先删该校已有行，改存 all
            for row in existing:
                await db.delete(row)
            db.add(Subscriptions(user_id=user_id, school_id=school_id, grade="all", created_at=datetime.now()))
    else:
        if "all" in existing_grades:
            pass  # all 已覆盖具体年级，静默吞掉
        else:
            new_grades = [g for g in dict.fromkeys(grades) if g not in existing_grades]
            now = datetime.now()
            for g in new_grades:
                db.add(Subscriptions(user_id=user_id, school_id=school_id, grade=g, created_at=now))

    await db.flush()
    state = await _school_subscription_state(db, user_id, school)
    # 显式提交后才允许端点返回成功：依赖 teardown 的 commit 发生在响应发送之后，
    # 不能作为「已保存」的依据（已用 commit 故障注入验证）
    await db.commit()
    return state


async def _school_subscription_state(db: AsyncSession, user_id: int, school: Schools) -> Dict[str, Any]:
    stmt = (
        select(Subscriptions)
        .where(Subscriptions.user_id == user_id, Subscriptions.school_id == school.id)
        .order_by(col(Subscriptions.id))
    )
    rows = (await db.exec(stmt)).all()
    return {
        "school_id": school.id,
        "name": school.name,
        "stage": school.stage,
        "district": school.district,
        "grades": [r.grade for r in rows],
        "subscribed_at": rows[0].created_at.isoformat() if rows else None,
    }


async def unsubscribe_school(db: AsyncSession, user_id: int, school_id: int) -> None:
    """整校取消：删除该校所有订阅行（幂等，不存在也成功）。"""
    stmt = delete(Subscriptions).where(
        col(Subscriptions.user_id) == user_id, col(Subscriptions.school_id) == school_id
    )
    await db.exec(stmt)  # type: ignore[call-overload]
    await db.commit()  # 显式提交后才允许端点返回成功


async def unsubscribe_grade(db: AsyncSession, user_id: int, school_id: int, grade: str) -> None:
    """逐年级取消（幂等）。"""
    stmt = delete(Subscriptions).where(
        col(Subscriptions.user_id) == user_id,
        col(Subscriptions.school_id) == school_id,
        col(Subscriptions.grade) == grade,
    )
    await db.exec(stmt)  # type: ignore[call-overload]
    await db.commit()  # 显式提交后才允许端点返回成功


async def links_for_subscriptions(db: AsyncSession, user_id: int) -> Dict[int, List[Dict[str, Any]]]:
    """
    当前用户所有订阅学校的插班链接（登录态聚合接口）。
    订阅上限 20 校天然限定数据范围，不占用访客按 IP 限流的额度。
    """
    school_ids_stmt = select(func.distinct(Subscriptions.school_id)).where(Subscriptions.user_id == user_id)
    school_ids = list((await db.exec(school_ids_stmt)).all())
    if not school_ids:
        return {}

    links_stmt = (
        select(AdmissionLinks.school_id, AdmissionLinks.url, AdmissionLinks.link_text, AdmissionLinks.grades)
        .where(col(AdmissionLinks.school_id).in_(school_ids))
        .order_by(col(AdmissionLinks.id))
    )
    rows = (await db.exec(links_stmt)).all()

    result: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for school_id, url, link_text, grades in rows:
        result[school_id].append({"url": url, "link_text": link_text, "grades": grades})
    return dict(result)
